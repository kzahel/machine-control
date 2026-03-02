#!/usr/bin/env python3
"""
DRM/GBM screenshot capture for ChromeOS.

Captures the framebuffer directly via DRM + GBM, bypassing the need for a
user session. Works on the login screen. No PIL/Pillow dependency — uses
pure Python PNG encoding (zlib + struct).

Based on Chromium's autotest screenshot code (originally Python 2 + PIL).

Usage:
    python3 drm_screenshot.py [output.png]
    python3 drm_screenshot.py --base64    # output base64 to stdout
    python3 drm_screenshot.py --diag      # print diagnostic info

Requires: libdrm.so, libgbm.so (both present on ChromeOS)
"""

import base64
import os
import struct
import sys
import zlib
from ctypes import (
    CDLL, POINTER, Structure, byref, c_char, c_int, c_size_t,
    c_uint, c_ulonglong, c_ushort, c_void_p, c_voidp, string_at,
)

# ── DRM constants ──

DRM_CLOEXEC = 0o2000000
DRM_IOCTL_MODE_GETFB2 = 0xC06464CE

# ── GBM constants ──

GBM_BO_IMPORT_FD = 0x5503
GBM_BO_IMPORT_FD_MODIFIER = 0x5504
GBM_BO_USE_SCANOUT = c_uint(1)
GBM_BO_TRANSFER_READ = c_uint(1)
GBM_MAX_PLANES = 4


def _fourcc(a, b, c, d):
    return ord(a) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)


def _fourcc_str(v):
    return (chr(v & 0xFF) + chr((v >> 8) & 0xFF) +
            chr((v >> 16) & 0xFF) + chr((v >> 24) & 0xFF))


GBM_FORMAT_XRGB8888 = _fourcc("X", "R", "2", "4")
GBM_FORMAT_ARGB8888 = _fourcc("A", "R", "2", "4")


# ── DRM structures ──

class DrmModeModeInfo(Structure):
    _fields_ = [
        ("clock", c_uint),
        ("hdisplay", c_ushort), ("hsync_start", c_ushort),
        ("hsync_end", c_ushort), ("htotal", c_ushort), ("hskew", c_ushort),
        ("vdisplay", c_ushort), ("vsync_start", c_ushort),
        ("vsync_end", c_ushort), ("vtotal", c_ushort), ("vscan", c_ushort),
        ("vrefresh", c_uint),
        ("flags", c_uint), ("type", c_uint),
        ("name", c_char * 32),
    ]


class DrmModeResources(Structure):
    _fields_ = [
        ("count_fbs", c_int), ("fbs", POINTER(c_uint)),
        ("count_crtcs", c_int), ("crtcs", POINTER(c_uint)),
        ("count_connectors", c_int), ("connectors", POINTER(c_uint)),
        ("count_encoders", c_int), ("encoders", POINTER(c_uint)),
        ("min_width", c_int), ("max_width", c_int),
        ("min_height", c_int), ("max_height", c_int),
    ]


class DrmModeCrtc(Structure):
    _fields_ = [
        ("crtc_id", c_uint), ("buffer_id", c_uint),
        ("x", c_uint), ("y", c_uint),
        ("width", c_uint), ("height", c_uint),
        ("mode_valid", c_int), ("mode", DrmModeModeInfo),
        ("gamma_size", c_int),
    ]


class DrmModeFB2(Structure):
    """struct drm_mode_fb_cmd2 — modern FB info with modifiers."""
    _fields_ = [
        ("fb_id", c_uint),
        ("width", c_uint), ("height", c_uint),
        ("pixel_format", c_uint), ("flags", c_uint),
        ("handles", c_uint * 4), ("pitches", c_uint * 4),
        ("offsets", c_uint * 4), ("modifier", c_ulonglong * 4),
    ]


class GbmImportFdData(Structure):
    _fields_ = [
        ("fd", c_int), ("width", c_uint), ("height", c_uint),
        ("stride", c_uint), ("bo_format", c_uint),
    ]


class GbmImportFdModifierData(Structure):
    _fields_ = [
        ("width", c_uint), ("height", c_uint),
        ("format", c_uint), ("num_fds", c_uint),
        ("fds", c_int * GBM_MAX_PLANES),
        ("strides", c_int * GBM_MAX_PLANES),
        ("offsets", c_int * GBM_MAX_PLANES),
        ("modifier", c_ulonglong),
    ]


class GbmDevice(Structure):
    pass


class GbmBo(Structure):
    pass


# ── Library loading ──

def _load_drm():
    for name in ("libdrm.so", "libdrm.so.2"):
        try:
            return CDLL(name)
        except OSError:
            continue
    raise RuntimeError("Cannot load libdrm")


def _load_gbm():
    for name in ("libgbm.so", "libgbm.so.1"):
        try:
            lib = CDLL(name)
            break
        except OSError:
            continue
    else:
        raise RuntimeError("Cannot load libgbm")

    lib.gbm_create_device.argtypes = [c_int]
    lib.gbm_create_device.restype = POINTER(GbmDevice)
    lib.gbm_device_destroy.argtypes = [POINTER(GbmDevice)]
    lib.gbm_device_destroy.restype = None

    lib.gbm_bo_import.argtypes = [POINTER(GbmDevice), c_uint, c_void_p, c_uint]
    lib.gbm_bo_import.restype = POINTER(GbmBo)

    lib.gbm_bo_map.argtypes = [
        POINTER(GbmBo), c_uint, c_uint, c_uint, c_uint, c_uint,
        POINTER(c_uint), POINTER(c_void_p), c_size_t,
    ]
    lib.gbm_bo_map.restype = c_void_p

    lib.gbm_bo_unmap.argtypes = [POINTER(GbmBo), c_void_p]
    lib.gbm_bo_unmap.restype = None

    lib.gbm_bo_destroy.argtypes = [POINTER(GbmBo)]
    lib.gbm_bo_destroy.restype = None

    return lib


def _setup_drm(lib):
    lib.drmModeGetResources.argtypes = [c_int]
    lib.drmModeGetResources.restype = POINTER(DrmModeResources)
    lib.drmModeFreeResources.argtypes = [POINTER(DrmModeResources)]
    lib.drmModeFreeResources.restype = None

    lib.drmModeGetCrtc.argtypes = [c_int, c_uint]
    lib.drmModeGetCrtc.restype = POINTER(DrmModeCrtc)
    lib.drmModeFreeCrtc.argtypes = [POINTER(DrmModeCrtc)]
    lib.drmModeFreeCrtc.restype = None

    lib.drmIoctl.argtypes = [c_int, c_uint, c_voidp]
    lib.drmIoctl.restype = c_int

    lib.drmPrimeHandleToFD.argtypes = [c_int, c_uint, c_uint, POINTER(c_int)]
    lib.drmPrimeHandleToFD.restype = c_int


# ── Core screenshot logic ──

def find_active_crtc(drm_lib, fd):
    """Find the first CRTC with an active mode and framebuffer."""
    res_ptr = drm_lib.drmModeGetResources(fd)
    if not res_ptr:
        return None
    res = res_ptr.contents
    result = None
    for i in range(res.count_crtcs):
        crtc_id = res.crtcs[i]
        crtc_ptr = drm_lib.drmModeGetCrtc(fd, crtc_id)
        if not crtc_ptr:
            continue
        crtc = crtc_ptr.contents
        if crtc.mode_valid and crtc.buffer_id != 0:
            result = crtc
            break
    drm_lib.drmModeFreeResources(res_ptr)
    return result


def get_fb2(drm_lib, fd, fb_id):
    """Get framebuffer info using the modern GETFB2 ioctl."""
    fb2 = DrmModeFB2()
    fb2.fb_id = fb_id
    rv = drm_lib.drmIoctl(fd, DRM_IOCTL_MODE_GETFB2, byref(fb2))
    if rv:
        raise RuntimeError(f"DRM_IOCTL_MODE_GETFB2 failed (rv={rv})")
    return fb2


def capture_framebuffer(drm_lib, gbm_lib, fd, crtc):
    """Capture framebuffer pixels via GBM. Returns (width, height, rgb_bytes)."""
    fb2 = get_fb2(drm_lib, fd, crtc.buffer_id)
    width, height = fb2.width, fb2.height
    pitch = fb2.pitches[0]
    has_modifier = (fb2.flags & 0x2) != 0  # DRM_MODE_FB_MODIFIERS

    # Export primary handle as PRIME FD
    prime_fd = c_int(0)
    rv = drm_lib.drmPrimeHandleToFD(fd, fb2.handles[0], DRM_CLOEXEC, byref(prime_fd))
    if rv:
        raise RuntimeError(f"drmPrimeHandleToFD failed: {rv}")

    # Count active planes (for multi-plane modifier import)
    num_planes = sum(1 for h in fb2.handles if h != 0)

    # Create GBM device
    gbm_dev = gbm_lib.gbm_create_device(fd)
    if not gbm_dev:
        raise RuntimeError("gbm_create_device failed")

    try:
        bo = None

        # Try modifier-aware import first if FB has modifiers
        if has_modifier:
            import_data = GbmImportFdModifierData()
            import_data.width = width
            import_data.height = height
            import_data.format = fb2.pixel_format
            import_data.num_fds = num_planes
            import_data.modifier = fb2.modifier[0]

            # Export FDs for each plane
            plane_fds = []
            for i in range(num_planes):
                if i == 0:
                    import_data.fds[i] = prime_fd.value
                else:
                    pfd = c_int(0)
                    rv = drm_lib.drmPrimeHandleToFD(fd, fb2.handles[i],
                                                     DRM_CLOEXEC, byref(pfd))
                    if rv:
                        raise RuntimeError(f"drmPrimeHandleToFD plane {i} failed")
                    import_data.fds[i] = pfd.value
                    plane_fds.append(pfd.value)

                import_data.strides[i] = fb2.pitches[i]
                import_data.offsets[i] = fb2.offsets[i]

            bo = gbm_lib.gbm_bo_import(gbm_dev, GBM_BO_IMPORT_FD_MODIFIER,
                                        byref(import_data), GBM_BO_USE_SCANOUT)

            # Clean up extra plane FDs
            for pfd in plane_fds:
                os.close(pfd)

        # Fallback: simple FD import (for linear buffers)
        if not bo:
            import_data = GbmImportFdData()
            import_data.fd = prime_fd.value
            import_data.width = width
            import_data.height = height
            import_data.stride = pitch
            import_data.bo_format = fb2.pixel_format
            bo = gbm_lib.gbm_bo_import(gbm_dev, GBM_BO_IMPORT_FD,
                                        byref(import_data), GBM_BO_USE_SCANOUT)

        if not bo:
            raise RuntimeError("gbm_bo_import failed")

        try:
            map_data = c_void_p(0)
            stride_out = c_uint(0)
            map_ptr = gbm_lib.gbm_bo_map(bo, 0, 0, width, height,
                                          GBM_BO_TRANSFER_READ,
                                          byref(stride_out), byref(map_data), 0)
            if not map_ptr:
                raise RuntimeError("gbm_bo_map failed")

            try:
                stride = stride_out.value
                raw = string_at(map_ptr, stride * height)
            finally:
                gbm_lib.gbm_bo_unmap(bo, map_data)
        finally:
            gbm_lib.gbm_bo_destroy(bo)
    finally:
        gbm_lib.gbm_device_destroy(gbm_dev)

    os.close(prime_fd.value)

    # Convert BGRX → RGB using slice assignment (C-speed in CPython)
    rgb_rows = []
    for y in range(height):
        row_off = y * stride
        bgrx = raw[row_off:row_off + width * 4]
        row = bytearray(width * 3)
        row[0::3] = bgrx[2::4]  # R
        row[1::3] = bgrx[1::4]  # G
        row[2::3] = bgrx[0::4]  # B
        rgb_rows.append(bytes(row))

    return width, height, rgb_rows


# ── Pure Python PNG encoder ──

def encode_png(width, height, rgb_rows):
    """Encode RGB row data as PNG. Returns bytes."""
    def chunk(tag, data):
        raw = tag + data
        return (struct.pack(">I", len(data)) + raw +
                struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    # Stream rows into compressor to avoid building full 24MB buffer
    c = zlib.compressobj(6)
    chunks = []
    for row in rgb_rows:
        chunks.append(c.compress(b"\x00"))  # filter byte
        chunks.append(c.compress(row))
    chunks.append(c.flush())
    compressed = b"".join(chunks)

    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", compressed) +
            chunk(b"IEND", b""))


# ── Diagnostics ──

def run_diag():
    """Print diagnostic info about DRM devices."""
    drm_lib = _load_drm()
    _setup_drm(drm_lib)

    for card in sorted(os.listdir("/dev/dri")):
        if not card.startswith("card"):
            continue
        path = f"/dev/dri/{card}"
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError as e:
            print(f"{path}: cannot open ({e})")
            continue

        print(f"\n{path}:")
        crtc = find_active_crtc(drm_lib, fd)
        if not crtc:
            print("  No active CRTC")
            os.close(fd)
            continue

        print(f"  CRTC {crtc.crtc_id}: {crtc.width}x{crtc.height}, FB {crtc.buffer_id}")

        try:
            fb2 = get_fb2(drm_lib, fd, crtc.buffer_id)
            fmt = _fourcc_str(fb2.pixel_format)
            print(f"  FB2: {fb2.width}x{fb2.height}, format={fmt}, flags=0x{fb2.flags:x}")
            print(f"  pitches={list(fb2.pitches)}, offsets={list(fb2.offsets)}")
            print(f"  handles={list(fb2.handles)}")
            print(f"  modifiers={[hex(m) for m in fb2.modifier]}")
        except Exception as e:
            print(f"  FB2 query failed: {e}")

        os.close(fd)


# ── Main ──

def drm_screenshot():
    """Take a DRM/GBM screenshot. Returns PNG bytes or raises RuntimeError."""
    drm_lib = _load_drm()
    _setup_drm(drm_lib)
    gbm_lib = _load_gbm()

    cards = sorted(f for f in os.listdir("/dev/dri") if f.startswith("card"))
    if not cards:
        raise RuntimeError("No DRM devices found in /dev/dri/")

    last_error = None
    for card in cards:
        path = os.path.join("/dev/dri", card)
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError:
            continue

        try:
            crtc = find_active_crtc(drm_lib, fd)
            if crtc:
                width, height, rgb_rows = capture_framebuffer(drm_lib, gbm_lib, fd, crtc)
                return encode_png(width, height, rgb_rows)
        except Exception as e:
            last_error = e
        finally:
            os.close(fd)

    if last_error:
        raise last_error
    raise RuntimeError("No active CRTC found on any DRM device")


def drm_screenshot_base64():
    """Take a DRM/GBM screenshot. Returns base64-encoded PNG string."""
    return base64.b64encode(drm_screenshot()).decode("ascii")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DRM/GBM screenshot capture")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output PNG file path (default: stdout base64)")
    parser.add_argument("--base64", action="store_true",
                        help="Output base64 to stdout")
    parser.add_argument("--diag", action="store_true",
                        help="Print diagnostic info")
    args = parser.parse_args()

    if args.diag:
        run_diag()
        sys.exit(0)

    try:
        png = drm_screenshot()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output and not args.base64:
        with open(args.output, "wb") as f:
            f.write(png)
        print(f"{args.output} ({len(png)} bytes)")
    else:
        sys.stdout.write(base64.b64encode(png).decode("ascii"))
