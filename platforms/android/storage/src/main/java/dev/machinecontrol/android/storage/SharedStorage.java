package dev.machinecontrol.android.storage;

import android.content.Context;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import java.io.File;
import java.io.IOException;

/** Raw primary shared storage, independently of SAF folder grants.
 * Copyright (c) 2026 Kyle Graehl. Licensed under the repository MIT license.
 */
public final class SharedStorage {
    private SharedStorage() { }

    public static File primary(Context context) throws IOException {
        if (!Environment.isExternalStorageManager())
            throw new IOException("Enable optional all-files access for /sdcard");
        StorageVolume volume = context.getSystemService(StorageManager.class).getPrimaryStorageVolume();
        if (!Environment.MEDIA_MOUNTED.equals(volume.getState()))
            throw new IOException("Primary shared storage is not mounted for writing");
        File directory = volume.getDirectory();
        if (directory == null) throw new IOException("Primary shared storage is unavailable");
        File root = directory.getCanonicalFile();
        if (!root.isDirectory() || !root.canRead() || !root.canWrite())
            throw new IOException("Primary shared storage is not accessible");
        return root;
    }
}
