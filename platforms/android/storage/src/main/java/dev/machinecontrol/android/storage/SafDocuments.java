package dev.machinecontrol.android.storage;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import java.io.*;
import org.json.JSONArray;
import org.json.JSONObject;

/** Bounded SAF operations. No raw paths, retained handles or private fallback.
 * Copyright (c) 2026 Kyle Graehl. Licensed under the repository MIT license.
 */
public final class SafDocuments {
    public static final long MAX_BYTES = 64L * 1024 * 1024;
    private static final int MAX_CHILDREN = 2048;
    private final Context context;
    private final Uri tree;
    private final CancellationSignal cancel;
    public SafDocuments(Context context, Uri tree, CancellationSignal cancel) throws IOException {
        this.context = context; this.tree = tree; this.cancel = cancel;
        if (!DocumentsContract.isTreeUri(tree)) throw new IOException("Select a document tree");
        boolean granted = context.getContentResolver().getPersistedUriPermissions().stream()
            .anyMatch(p -> p.getUri().equals(tree) && p.isReadPermission() && p.isWritePermission());
        if (!granted) throw new IOException("Folder permission unavailable; reselect this shortcut");
    }
    private static String[] components(String path) throws IOException {
        if (path.isEmpty()) return new String[0];
        String[] parts = path.split("/", -1);
        if (parts.length > 32 || path.length() > 4096) throw new IOException("Document path exceeds limit");
        for (String part : parts) if (part.isEmpty() || part.equals(".") || part.equals("..") ||
            part.indexOf('\\') >= 0 || part.indexOf('\0') >= 0) throw new IOException("Invalid relative document path");
        return parts;
    }
    private JSONArray children(Uri parent) throws Exception {
        Uri uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getDocumentId(parent));
        JSONArray rows = new JSONArray();
        try (Cursor cursor = context.getContentResolver().query(uri, new String[] {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_FLAGS }, null, null, null, cancel)) {
            if (cursor == null) throw new IOException("Document provider unavailable");
            while (cursor.moveToNext()) {
                cancel.throwIfCanceled();
                if (rows.length() >= MAX_CHILDREN) throw new IOException("Directory exceeds 2048 entries; narrow the selected root");
                rows.put(new JSONObject().put("id", cursor.getString(0)).put("name", cursor.getString(1))
                    .put("directory", DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2)))
                    .put("size", cursor.isNull(3) ? JSONObject.NULL : cursor.getLong(3)).put("flags", cursor.getLong(4)));
            }
        }
        return rows;
    }
    private Uri child(Uri parent, String name) throws Exception {
        JSONArray rows = children(parent); Uri match = null;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.getJSONObject(i);
            if (name.equals(row.getString("name"))) {
                if (match != null) throw new IOException("Ambiguous duplicate document name: " + name);
                match = DocumentsContract.buildDocumentUriUsingTree(tree, row.getString("id"));
            }
        }
        return match;
    }
    private Uri resolve(String path) throws Exception {
        Uri uri = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
        for (String part : components(path)) {
            uri = child(uri, part);
            if (uri == null) throw new FileNotFoundException("Document not found: " + path);
        }
        return uri;
    }
    private JSONObject metadata(Uri uri) throws Exception {
        try (Cursor cursor = context.getContentResolver().query(uri, new String[] {
            DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE }, null, null, null, cancel)) {
            if (cursor == null || !cursor.moveToFirst()) throw new FileNotFoundException("Document unavailable");
            return new JSONObject().put("name", cursor.getString(0))
                .put("directory", DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(1)))
                .put("size", cursor.isNull(2) ? JSONObject.NULL : cursor.getLong(2));
        }
    }
    public JSONObject stat(String path) throws Exception { return metadata(resolve(path)); }
    public JSONObject list(String path) throws Exception {
        JSONArray rows = children(resolve(path));
        // Document IDs remain inside the native boundary.
        for (int i = 0; i < rows.length(); i++) rows.getJSONObject(i).remove("id");
        return new JSONObject().put("entries", rows).put("limit", MAX_CHILDREN);
    }
    private String[] destination(String path) throws IOException {
        components(path);
        if (path.isEmpty()) throw new IOException("The selected root cannot be mutated");
        int slash = path.lastIndexOf('/'); return new String[] { slash < 0 ? "" : path.substring(0, slash), path.substring(slash + 1) };
    }
    public JSONObject mkdir(String path) throws Exception {
        cancel.throwIfCanceled(); String[] dest = destination(path); Uri parent = resolve(dest[0]);
        if (child(parent, dest[1]) != null) throw new IOException("Document already exists");
        Uri uri = DocumentsContract.createDocument(context.getContentResolver(), parent, DocumentsContract.Document.MIME_TYPE_DIR, dest[1]);
        if (uri == null) throw new IOException("Provider did not create directory");
        JSONObject result = metadata(uri);
        if (!dest[1].equals(result.getString("name"))) throw new IOException("Provider changed requested name; created document may remain");
        return result;
    }
    public JSONObject remove(String path, boolean recursive) throws Exception {
        cancel.throwIfCanceled(); destination(path);
        if (stat(path).getBoolean("directory") && !recursive) throw new IOException("Directory deletion requires explicit --recursive");
        if (!DocumentsContract.deleteDocument(context.getContentResolver(), resolve(path))) throw new IOException("Provider refused deletion");
        return new JSONObject().put("deleted", true);
    }
    public JSONObject rename(String path, String name) throws Exception {
        destination(path); String[] parts = components(name);
        if (parts.length != 1) throw new IOException("Rename takes a single new name");
        cancel.throwIfCanceled(); String[] dest = destination(path);
        if (child(resolve(dest[0]), name) != null) throw new IOException("Destination already exists");
        Uri uri = DocumentsContract.renameDocument(context.getContentResolver(), resolve(path), name);
        if (uri == null) throw new IOException("Provider refused rename");
        JSONObject result = metadata(uri);
        if (!name.equals(result.getString("name"))) throw new IOException("Provider changed requested name; rename may have occurred");
        return result;
    }
    public long read(String path, OutputStream output) throws Exception {
        Uri uri = resolve(path);
        try (ParcelFileDescriptor descriptor = context.getContentResolver().openFileDescriptor(uri, "r", cancel)) {
            if (descriptor == null) throw new IOException("Provider returned no descriptor");
            // AutoClose owns the descriptor; never retain or duplicate it beyond this request.
            try (InputStream input = new ParcelFileDescriptor.AutoCloseInputStream(descriptor)) {
                long bytes = copy(input, output, MAX_BYTES, cancel); descriptor.checkError(); return bytes;
            }
        }
    }
    public JSONObject write(String path, File source, boolean replace) throws Exception {
        cancel.throwIfCanceled(); String[] dest = destination(path); Uri parent = resolve(dest[0]); Uri uri = child(parent, dest[1]);
        if (uri != null && !replace) throw new IOException("Document exists; explicit --replace required");
        if (uri == null) {
            uri = DocumentsContract.createDocument(context.getContentResolver(), parent, "application/octet-stream", dest[1]);
            if (uri == null) throw new IOException("Provider did not create document");
        }
        JSONObject result = metadata(uri);
        if (!dest[1].equals(result.getString("name")) || result.getBoolean("directory"))
            throw new IOException("Provider changed requested name/type; created document may remain");
        try (InputStream input = new FileInputStream(source);
             ParcelFileDescriptor descriptor = context.getContentResolver().openFileDescriptor(uri, "rwt", cancel)) {
            if (descriptor == null) throw new IOException("Provider returned no writable descriptor");
            try (OutputStream output = new ParcelFileDescriptor.AutoCloseOutputStream(descriptor)) {
                long count = copy(input, output, MAX_BYTES, cancel); output.flush(); descriptor.checkError();
                result.put("bytes", count).put("providerWriteCompleted", true);
            }
        } catch (Exception error) {
            throw new IOException("Write did not complete; destination may be partial: " + error.getMessage(), error);
        }
        return result;
    }
    public static long copy(InputStream input, OutputStream output, long limit, CancellationSignal cancel) throws Exception {
        byte[] buffer = new byte[64 * 1024]; long total = 0; int n;
        while ((n = input.read(buffer)) != -1) {
            cancel.throwIfCanceled(); total += n;
            if (total > limit) throw new IOException("Transfer exceeds limit: " + limit);
            output.write(buffer, 0, n);
        }
        return total;
    }
}
