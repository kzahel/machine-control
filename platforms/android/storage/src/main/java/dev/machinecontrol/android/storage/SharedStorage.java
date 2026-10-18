package dev.machinecontrol.android.storage;

import android.content.Context;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import java.io.File;
import java.io.IOException;
import java.util.*;

/** Raw primary and removable shared storage, independently of SAF grants.
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

    /** A public removable volume; unavailable entries retain their stable identity. */
    public static final class Volume {
        public final String id, label, state, reason;
        public final File directory;
        private Volume(String id, String label, String state, File directory, String reason) {
            this.id = id; this.label = label; this.state = state; this.directory = directory; this.reason = reason;
        }
    }

    public static boolean validVolumeId(String id) {
        return id != null && id.matches("[A-Za-z0-9][A-Za-z0-9-]{0,79}");
    }

    /** No authority is inferred from a label, directory name or SAF URI. */
    public static List<Volume> removableVolumes(Context context) {
        List<StorageVolume> volumes = context.getSystemService(StorageManager.class).getStorageVolumes();
        List<Volume> result = new ArrayList<>();
        for (StorageVolume volume : volumes) {
            if (volume.isPrimary() || !volume.isRemovable()) continue;
            String id = volume.getUuid(), reason = null; File directory = null;
            if (!validVolumeId(id)) reason = "No safe, stable volume ID";
            else if (volumes.stream().filter(v -> id.equalsIgnoreCase(v.getUuid())).count() != 1)
                reason = "Ambiguous duplicate volume ID";
            else if (!Environment.isExternalStorageManager()) reason = "Enable optional all-files access";
            else if (!Environment.MEDIA_MOUNTED.equals(volume.getState())) reason = "Volume is not mounted for writing: " + volume.getState();
            else try {
                File source = volume.getDirectory();
                if (source == null) throw new IOException("Volume directory is unavailable");
                directory = source.getCanonicalFile();
                if (!directory.isDirectory() || !directory.canRead() || !directory.canWrite()) throw new IOException("Volume is not accessible");
            } catch (IOException error) { directory = null; reason = error.getMessage(); }
            result.add(new Volume(id, volume.getDescription(context), volume.getState(), directory, reason));
        }
        return result;
    }

    public static File removable(Context context, String id) throws IOException {
        if (!validVolumeId(id)) throw new IOException("Invalid removable volume ID");
        for (Volume volume : removableVolumes(context)) if (id.equals(volume.id)) {
            if (volume.reason != null) throw new IOException(volume.reason);
            return volume.directory;
        }
        throw new IOException("Removable volume is absent; insert it and restart host");
    }
}
