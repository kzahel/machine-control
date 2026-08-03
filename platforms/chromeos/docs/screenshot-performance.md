# Screenshot Performance Optimization

The EGL screenshot pipeline was optimized from **~2.0s to ~0.3s** (raw capture) by reducing transfer size, eliminating encoding overhead, and reusing SSH connections.

## Before / After

| Stage | Before | After | How |
|-------|--------|-------|-----|
| SSH connect | 0.16s | ~0s | ControlMaster connection reuse |
| Python startup | 0.15s | 0.15s | — |
| EGL capture | 0.14s | 0.14s | — |
| Image encode | 0.16s (Python zlib PNG) | ~0.02s (libturbojpeg) | C library via ctypes |
| Transfer | 1.3s (~1MB base64) | ~0.1s (~100KB raw) | JPEG + no base64 |
| Local decode | 0.05s (python3 JSON) | ~0s (direct file write) | Binary stdout pipe |
| **Total** | **~2.0s** | **~0.3s** | |

Via `bin/chromeos` the total is ~0.9s due to bash startup overhead on macOS (~0.4s) and the deploy hash check.

## Optimizations

### 1. JPEG encoding via libturbojpeg (biggest win)

ChromeOS ships with libjpeg-turbo at `/usr/lib64/libturbojpeg.so` (used by Chrome for JPEG decoding). We use it for encoding via ctypes:

```python
# drm_screenshot.py
encode_jpeg(width, height, rgb_rows, quality=80)  # returns JPEG bytes or None
```

- Uses `tjCompress2` API with `TJPF_RGB` pixel format and `TJSAMP_420` subsampling
- Quality 80 at 3840x2160: ~100-450KB depending on content (vs ~400-750KB PNG)
- Encoding time: ~0.02s (C) vs ~0.16s (Python zlib level 6)
- Falls back to PNG if libturbojpeg is not available

### 2. Direct binary stdout (eliminates base64 + JSON)

Old path:
```
EGL capture -> PNG encode -> base64 encode (+33%) -> JSON wrap -> SSH stdout
-> local python3 JSON parse -> base64 decode -> write file
```

New path:
```
EGL capture -> JPEG encode -> SSH stdout -> write file
```

The `--stdout` flag on `drm_screenshot.py` writes raw image bytes to stdout. `bin/chromeos` pipes SSH output directly to a file — no base64, no JSON, no local python3 invocation.

### 3. SSH ControlMaster (connection reuse)

```bash
SSH_OPTS=(-o ControlMaster=auto -o "ControlPath=/tmp/chromeos-ssh-%C" -o ControlPersist=300)
```

The first SSH command establishes a master connection. Subsequent commands within 5 minutes multiplex over it, eliminating the TCP+SSH handshake (~0.16s per command).

### 4. Deploy caching

`ensure_client` hashes local files with `shasum -a 256` and skips `scp` when unchanged. Saves ~0.9s on repeat runs (4 SSH/scp round trips avoided).

## CLI Usage

```bash
chromeos screenshot                      # JPEG (default), ~0.9s
chromeos screenshot output.png           # PNG (inferred from .png extension)
chromeos screenshot --jpeg -q 50         # JPEG quality 50 (smaller file)
chromeos screenshot --png                # Explicit PNG
chromeos screenshot --method egl         # Force EGL capture
```

## File size comparison (3840x2160 UI screenshot)

| Format | Size | Notes |
|--------|------|-------|
| PNG (zlib level 6) | 95-750KB | Great for flat UI, larger for photos |
| JPEG q80 | 100-450KB | Consistent, fast encode |
| JPEG q50 | 70-330KB | Slightly visible artifacts on text |
| Base64 of any above | +33% | Eliminated in direct path |

PNG can actually be smaller than JPEG for text-heavy UI content. JPEG wins on encoding speed regardless.

## Architecture

```
bin/chromeos screenshot output.jpg
  |
  |-- ensure_client (hash check, skip if unchanged)
  |
  |-- wake display with modifier-only input
  |
  |-- ssh chromeos-testbed "python3 drm_screenshot.py --stdout --jpeg"
  |     |
  |     |-- EGL capture: DRM fd -> EGLImage -> glReadPixels (RGBA)
  |     |-- RGBA -> RGB row conversion (drop alpha)
  |     |-- libturbojpeg tjCompress2 -> JPEG bytes
  |     |-- sys.stdout.buffer.write(jpeg_bytes)
  |     |
  |   [raw bytes flow through SSH pipe]
  |
  |-- > output.jpg  (direct file write, no parsing)
```

Keyboard screenshots (`--method keyboard`) still use the client.py JSON/base64 path since they go through Chrome's screenshot UI.
Direct DRM capture retries briefly after waking because display scanout can take
longer to expose an active CRTC than input delivery itself.
