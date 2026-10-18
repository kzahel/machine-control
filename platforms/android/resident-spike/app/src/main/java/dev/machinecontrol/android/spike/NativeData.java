package dev.machinecontrol.android.spike;

import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.util.Base64;
import android.util.Size;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;

/** Read-only Android provider boundary. No paths or caller-supplied URIs. */
final class NativeData {
    static final int MAX_BYTES = 4 * 1024 * 1024;
    private final Context context;
    private String epoch = "";
    private final Map<String, Entry> handles = new HashMap<>();
    private static final class Entry {
        final Uri uri, grant;
        final String kind;
        Entry(Uri uri, Uri grant, String kind) { this.uri = uri; this.grant = grant; this.kind = kind; }
    }
    static final class Failure extends Exception {
        final String code;
        Failure(String code, String message) { super(message); this.code = code; }
    }
    NativeData(Context context) { this.context = context; }
    private synchronized void refreshEpoch() {
        String selected = DataSelections.store(context).getString("epoch", "empty");
        if (!epoch.equals(selected)) { handles.clear(); epoch = selected; }
    }
    private synchronized String handle(Entry entry) throws Failure {
        refreshEpoch();
        for (Map.Entry<String, Entry> old : handles.entrySet()) {
            Entry value = old.getValue();
            if (value.uri.equals(entry.uri) && value.grant.equals(entry.grant) && value.kind.equals(entry.kind)) return old.getKey();
        }
        if (handles.size() >= 1024) throw new Failure("handle_limit", "Restart data access to refresh bounded handles");
        String id = UUID.randomUUID().toString(); handles.put(id, entry); return id;
    }
    private synchronized Entry resolve(String id) throws Failure {
        refreshEpoch();
        Entry entry = handles.get(id);
        if (entry == null) throw new Failure("stale_data_reference", "List selected data again; opaque handle is unknown");
        requireGrant(entry);
        return entry;
    }
    private void requireGrant(Entry entry) throws Failure {
        Uri selected = DataSelections.selected(context, entry.kind.equals("photo") ? "photo" : "tree");
        if (!entry.grant.equals(selected)) throw new Failure("stale_data_reference", "Selected data identity changed; list again");
        if (!DataSelections.available(context, entry.grant))
            throw new Failure("permission_revoked", "Selected Android read grant is unavailable; select it again");
    }
    JSONObject dispatch(JSONObject request, CancellationSignal cancellation) throws Exception {
        switch (request.getString("operation")) {
            case "open": return new JSONObject().put("plane", "data").put("uiClaim", false)
                .put("concurrentReaders", true).put("readOnly", true).put("maxReadBytes", MAX_BYTES);
            case "data.photos": return selections("photo", cancellation);
            case "data.roots": return selections("tree", cancellation);
            case "data.list": {
                Entry parent = resolve(request.getString("id"));
                if (!parent.kind.equals("tree") && !parent.kind.equals("directory"))
                    throw new Failure("not_directory", "Select a directory handle");
                String documentId = parent.kind.equals("tree") ? DocumentsContract.getTreeDocumentId(parent.uri) :
                    DocumentsContract.getDocumentId(parent.uri);
                Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(parent.grant, documentId);
                JSONArray items = new JSONArray();
                String[] columns = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                    DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_SIZE};
                boolean truncated = false;
                try (Cursor cursor = context.getContentResolver().query(children, columns, null, null, null, cancellation)) {
                    if (cursor == null) throw new Failure("provider_unavailable", "Provider returned no document listing");
                    while (cursor.moveToNext()) {
                        if (items.length() >= 100) { truncated = true; break; }
                        String mime = cursor.getString(2);
                        Uri document = DocumentsContract.buildDocumentUriUsingTree(parent.grant, cursor.getString(0));
                        Entry child = new Entry(document, parent.grant,
                            DocumentsContract.Document.MIME_TYPE_DIR.equals(mime) ? "directory" : "document");
                        items.put(new JSONObject().put("id", handle(child)).put("name", cursor.getString(1))
                            .put("mime", mime).put("kind", child.kind).put("size", cursor.isNull(3) ? JSONObject.NULL : cursor.getLong(3)));
                    }
                }
                requireGrant(parent);
                return new JSONObject().put("items", items).put("truncated", truncated);
            }
            case "data.read": {
                Entry entry = resolve(request.getString("id"));
                if (entry.kind.equals("tree") || entry.kind.equals("directory"))
                    throw new Failure("not_file", "Choose a file handle");
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                ParcelFileDescriptor descriptor = context.getContentResolver().openFileDescriptor(entry.uri, "r", cancellation);
                if (descriptor == null) throw new Failure("provider_unavailable", "Provider refused a read descriptor");
                try (InputStream input = new ParcelFileDescriptor.AutoCloseInputStream(descriptor)) {
                    byte[] buffer = new byte[65536]; int count;
                    while ((count = input.read(buffer)) != -1) {
                        cancellation.throwIfCanceled();
                        if (bytes.size() + count > MAX_BYTES) throw new Failure("read_limit", "File exceeds the 4 MiB spike read bound");
                        bytes.write(buffer, 0, count);
                    }
                }
                requireGrant(entry);
                return new JSONObject().put("base64", Base64.encodeToString(bytes.toByteArray(), Base64.NO_WRAP))
                    .put("size", bytes.size());
            }
            case "data.thumbnail": {
                Entry entry = resolve(request.getString("id"));
                if (!entry.kind.equals("photo")) throw new Failure("not_photo", "Choose a selected photo handle");
                Bitmap bitmap = context.getContentResolver().loadThumbnail(entry.uri, new Size(512, 512), cancellation);
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes); bitmap.recycle();
                requireGrant(entry);
                return new JSONObject().put("png", Base64.encodeToString(bytes.toByteArray(), Base64.NO_WRAP));
            }
            default: throw new Failure("unsupported_operation", "Only selected-photo and document read operations are implemented");
        }
    }
    private JSONObject selections(String kind, CancellationSignal cancellation) throws Exception {
        Uri uri = DataSelections.selected(context, kind);
        JSONArray items = new JSONArray();
        if (uri != null) {
            Entry entry = new Entry(uri, uri, kind);
            boolean available = DataSelections.available(context, uri);
            JSONObject item = new JSONObject().put("id", handle(entry)).put("kind", kind).put("available", available);
            if (available) {
                Uri metadata = kind.equals("tree") ? DocumentsContract.buildDocumentUriUsingTree(uri, DocumentsContract.getTreeDocumentId(uri)) : uri;
                try (Cursor cursor = context.getContentResolver().query(metadata,
                        new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null, cancellation)) {
                    if (cursor != null && cursor.moveToFirst()) item.put("name", cursor.getString(0))
                        .put("size", cursor.isNull(1) ? JSONObject.NULL : cursor.getLong(1));
                }
                item.put("mime", context.getContentResolver().getType(metadata));
                requireGrant(entry);
            }
            items.put(item);
        }
        return new JSONObject().put("items", items);
    }
}
