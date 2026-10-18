package dev.machinecontrol.android.storage;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.provider.DocumentsContract;
import java.io.File;
import java.io.IOException;

/** Local primary-volume qualification, not a general SAF-to-path conversion.
 * Copyright (c) 2026 Kyle Graehl. Licensed under the repository MIT license.
 */
public final class LocalWorkspace {
    private LocalWorkspace() { }

    public static File resolve(Context context, Uri tree) throws IOException {
        if (!"content".equals(tree.getScheme()) ||
                !"com.android.externalstorage.documents".equals(tree.getAuthority()) ||
                !DocumentsContract.isTreeUri(tree)) {
            throw new IOException("Only the built-in local shared-storage provider is supported");
        }
        boolean granted = context.getContentResolver().getPersistedUriPermissions().stream()
            .anyMatch(p -> p.getUri().equals(tree) && p.isReadPermission() && p.isWritePermission());
        if (!granted) throw new IOException("Folder read/write permission is unavailable; select it again");
        if (!Environment.isExternalStorageManager()) {
            throw new IOException("All-files access is unavailable; enable it separately");
        }
        String id = DocumentsContract.getTreeDocumentId(tree);
        if (!id.startsWith("primary:")) throw new IOException("Only the primary shared-storage volume is qualified");
        String relative = id.substring("primary:".length());
        if (relative.isEmpty()) throw new IOException("Select a child folder, not the volume root");
        for (String component : relative.split("/", -1)) {
            if (component.isEmpty() || component.equals(".") || component.equals("..") ||
                    component.indexOf('\\') >= 0 || component.indexOf('\u0000') >= 0) {
                throw new IOException("Invalid local folder component");
            }
        }
        // Shared storage can be case-insensitive; do not admit a casing alias.
        if (relative.split("/", 2)[0].equalsIgnoreCase("Android")) {
            throw new IOException("App-specific Android storage is not a durable workspace");
        }
        File volume = context.getSystemService(StorageManager.class).getPrimaryStorageVolume().getDirectory();
        if (volume == null) throw new IOException("Primary storage is not mounted");
        volume = volume.getCanonicalFile();
        File root = new File(volume, relative).getCanonicalFile();
        if (!root.toPath().startsWith(volume.toPath()) || root.equals(volume) ||
                !root.isDirectory() || !root.canRead() || !root.canWrite()) {
            throw new IOException("Selected local folder is unavailable");
        }
        Uri document = DocumentsContract.buildDocumentUriUsingTree(tree, id);
        try (Cursor cursor = context.getContentResolver().query(document, new String[] {
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE }, null, null, null)) {
            if (cursor == null || !cursor.moveToFirst() || !id.equals(cursor.getString(0)) ||
                    !root.getName().equals(cursor.getString(1)) ||
                    !DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2)) || cursor.moveToNext()) {
                throw new IOException("Selected document does not match the local directory");
            }
        }
        return root;
    }
}
