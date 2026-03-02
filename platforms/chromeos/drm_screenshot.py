#!/usr/bin/env python3
"""
DRM/GBM/EGL screenshot capture for ChromeOS.

Captures the framebuffer directly via DRM, bypassing the need for a user
session. Works on the login screen. No PIL/Pillow dependency — uses pure
Python PNG encoding (zlib + struct).

Two capture backends:
  1. EGL (preferred): Imports the DRM FB as an EGLImage and reads via
     glReadPixels. Handles GPU-tiled buffers transparently.
  2. GBM map (fallback): Maps the buffer object directly. May produce
     garbled output on devices with tiled framebuffers.

Based on Chromium's screen-capture-utils (C++ EGL approach).

Usage:
    python3 drm_screenshot.py [output.png]           # save PNG
    python3 drm_screenshot.py --jpeg [output.jpg]    # save JPEG (smaller, faster)
    python3 drm_screenshot.py --stdout --jpeg        # raw JPEG bytes to stdout
    python3 drm_screenshot.py --base64               # base64 PNG to stdout
    python3 drm_screenshot.py --diag                 # diagnostic info

Requires: libdrm.so, libgbm.so (both present on ChromeOS)
Optional: libEGL.so, libGLESv2.so (for EGL capture, present on ChromeOS)
"""

import base64
import os
import struct
import sys
import zlib
from ctypes import (
    CDLL, CFUNCTYPE, POINTER, Structure, byref, c_char, c_char_p, c_float,
    c_int, c_size_t, c_uint, c_ulong, c_ulonglong, c_ushort, c_void_p,
    c_voidp, cast, create_string_buffer, string_at,
)

# ── DRM constants ──

DRM_CLOEXEC = 0o2000000
DRM_IOCTL_MODE_GETFB2 = 0xC06464CE

# DRM plane enumeration
DRM_CLIENT_CAP_ATOMIC = 3  # implies UNIVERSAL_PLANES
DRM_MODE_OBJECT_PLANE = 0xeeeeeeee

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

# ── EGL constants ──

EGL_NONE = 0x3038
EGL_SURFACE_TYPE = 0x3033
EGL_RENDERABLE_TYPE = 0x3040
EGL_OPENGL_ES2_BIT = 0x0004
EGL_CONTEXT_CLIENT_VERSION = 0x3098
EGL_EXTENSIONS = 0x3055
EGL_WIDTH = 0x3057
EGL_HEIGHT = 0x3056
EGL_LINUX_DRM_FOURCC_EXT = 0x3271
EGL_LINUX_DMA_BUF_EXT = 0x3270
EGL_DMA_BUF_PLANE0_FD_EXT = 0x3272
EGL_DMA_BUF_PLANE0_OFFSET_EXT = 0x3273
EGL_DMA_BUF_PLANE0_PITCH_EXT = 0x3274
EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT = 0x3443
EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT = 0x3444
EGL_DONT_CARE = -1

# EGL YUV color space hints (for video overlay planes)
EGL_YUV_COLOR_SPACE_HINT_EXT = 0x327B
EGL_SAMPLE_RANGE_HINT_EXT = 0x327C
EGL_YUV_NARROW_RANGE_EXT = 0x327E
EGL_ITU_REC601_EXT = 0x327F
EGL_ITU_REC709_EXT = 0x3280
EGL_ITU_REC2020_EXT = 0x3281
EGL_YUV_FULL_RANGE_EXT = 0x3282

# ── GLES constants ──

GL_EXTENSIONS = 0x1F03
GL_TRUE = 1
GL_VERTEX_SHADER = 0x8B31
GL_FRAGMENT_SHADER = 0x8B30
GL_COMPILE_STATUS = 0x8B81
GL_LINK_STATUS = 0x8B82
GL_INFO_LOG_LENGTH = 0x8B84
GL_TEXTURE_2D = 0x0DE1
GL_TEXTURE_EXTERNAL_OES = 0x8D65
GL_RGBA = 0x1908
GL_UNSIGNED_BYTE = 0x1401
GL_LINEAR = 0x2601
GL_CLAMP_TO_EDGE = 0x812F
GL_TEXTURE_WRAP_S = 0x2802
GL_TEXTURE_WRAP_T = 0x2803
GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_MAG_FILTER = 0x2800
GL_FRAMEBUFFER = 0x8D40
GL_COLOR_ATTACHMENT0 = 0x8CE0
GL_FRAMEBUFFER_COMPLETE = 0x8CD5
GL_TRIANGLE_STRIP = 0x0005
GL_PACK_ALIGNMENT = 0x0D05
GL_BLEND = 0x0BE2
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303


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


class DrmModePlaneRes(Structure):
    _fields_ = [
        ("count_planes", c_uint),
        ("planes", POINTER(c_uint)),
    ]


class DrmModePlane(Structure):
    _fields_ = [
        ("count_formats", c_uint),
        ("formats", POINTER(c_uint)),
        ("plane_id", c_uint),
        ("crtc_id", c_uint),
        ("fb_id", c_uint),
        ("crtc_x", c_uint), ("crtc_y", c_uint),
        ("x", c_uint), ("y", c_uint),
        ("possible_crtcs", c_uint),
        ("gamma_size", c_uint),
    ]


class DrmModePropertyEnum(Structure):
    _fields_ = [
        ("value", c_ulonglong),
        ("name", c_char * 32),
    ]


class DrmModePropertyRes(Structure):
    _fields_ = [
        ("prop_id", c_uint),
        ("flags", c_uint),
        ("name", c_char * 32),
        ("count_values", c_int),
        ("values", POINTER(c_ulonglong)),
        ("count_enums", c_int),
        ("enums", POINTER(DrmModePropertyEnum)),
        ("count_blobs", c_int),
        ("blob_ids", POINTER(c_uint)),
    ]


class DrmModeObjectProperties(Structure):
    _fields_ = [
        ("count_props", c_uint),
        ("props", POINTER(c_uint)),
        ("prop_values", POINTER(c_ulonglong)),
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

    # Plane enumeration
    lib.drmSetClientCap.argtypes = [c_int, c_ulonglong, c_ulonglong]
    lib.drmSetClientCap.restype = c_int

    lib.drmModeGetPlaneResources.argtypes = [c_int]
    lib.drmModeGetPlaneResources.restype = POINTER(DrmModePlaneRes)
    lib.drmModeFreePlaneResources.argtypes = [POINTER(DrmModePlaneRes)]
    lib.drmModeFreePlaneResources.restype = None

    lib.drmModeGetPlane.argtypes = [c_int, c_uint]
    lib.drmModeGetPlane.restype = POINTER(DrmModePlane)
    lib.drmModeFreePlane.argtypes = [POINTER(DrmModePlane)]
    lib.drmModeFreePlane.restype = None

    lib.drmModeObjectGetProperties.argtypes = [c_int, c_uint, c_uint]
    lib.drmModeObjectGetProperties.restype = POINTER(DrmModeObjectProperties)
    lib.drmModeFreeObjectProperties.argtypes = [POINTER(DrmModeObjectProperties)]
    lib.drmModeFreeObjectProperties.restype = None

    lib.drmModeGetProperty.argtypes = [c_int, c_uint]
    lib.drmModeGetProperty.restype = POINTER(DrmModePropertyRes)
    lib.drmModeFreeProperty.argtypes = [POINTER(DrmModePropertyRes)]
    lib.drmModeFreeProperty.restype = None


def _load_egl():
    for name in ("libEGL.so", "libEGL.so.1"):
        try:
            lib = CDLL(name)
            break
        except OSError:
            continue
    else:
        return None

    lib.eglGetDisplay.argtypes = [c_void_p]
    lib.eglGetDisplay.restype = c_void_p
    lib.eglInitialize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
    lib.eglInitialize.restype = c_int
    lib.eglChooseConfig.argtypes = [c_void_p, POINTER(c_int), POINTER(c_void_p),
                                     c_int, POINTER(c_int)]
    lib.eglChooseConfig.restype = c_int
    lib.eglCreateContext.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_int)]
    lib.eglCreateContext.restype = c_void_p
    lib.eglMakeCurrent.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p]
    lib.eglMakeCurrent.restype = c_int
    lib.eglDestroyContext.argtypes = [c_void_p, c_void_p]
    lib.eglDestroyContext.restype = c_int
    lib.eglTerminate.argtypes = [c_void_p]
    lib.eglTerminate.restype = c_int
    lib.eglQueryString.argtypes = [c_void_p, c_int]
    lib.eglQueryString.restype = c_char_p
    lib.eglGetProcAddress.argtypes = [c_char_p]
    lib.eglGetProcAddress.restype = c_void_p
    lib.eglGetError.argtypes = []
    lib.eglGetError.restype = c_int

    return lib


def _load_glesv2():
    for name in ("libGLESv2.so", "libGLESv2.so.2"):
        try:
            lib = CDLL(name)
            break
        except OSError:
            continue
    else:
        return None

    lib.glGetString.argtypes = [c_uint]
    lib.glGetString.restype = c_char_p
    lib.glGetError.argtypes = []
    lib.glGetError.restype = c_uint

    lib.glCreateShader.argtypes = [c_uint]
    lib.glCreateShader.restype = c_uint
    lib.glShaderSource.argtypes = [c_uint, c_int, POINTER(c_char_p), POINTER(c_int)]
    lib.glShaderSource.restype = None
    lib.glCompileShader.argtypes = [c_uint]
    lib.glCompileShader.restype = None
    lib.glGetShaderiv.argtypes = [c_uint, c_uint, POINTER(c_int)]
    lib.glGetShaderiv.restype = None
    lib.glGetShaderInfoLog.argtypes = [c_uint, c_int, POINTER(c_int), c_char_p]
    lib.glGetShaderInfoLog.restype = None
    lib.glDeleteShader.argtypes = [c_uint]
    lib.glDeleteShader.restype = None

    lib.glCreateProgram.argtypes = []
    lib.glCreateProgram.restype = c_uint
    lib.glAttachShader.argtypes = [c_uint, c_uint]
    lib.glAttachShader.restype = None
    lib.glLinkProgram.argtypes = [c_uint]
    lib.glLinkProgram.restype = None
    lib.glGetProgramiv.argtypes = [c_uint, c_uint, POINTER(c_int)]
    lib.glGetProgramiv.restype = None
    lib.glGetProgramInfoLog.argtypes = [c_uint, c_int, POINTER(c_int), c_char_p]
    lib.glGetProgramInfoLog.restype = None
    lib.glUseProgram.argtypes = [c_uint]
    lib.glUseProgram.restype = None
    lib.glDeleteProgram.argtypes = [c_uint]
    lib.glDeleteProgram.restype = None

    lib.glGetUniformLocation.argtypes = [c_uint, c_char_p]
    lib.glGetUniformLocation.restype = c_int
    lib.glUniform1i.argtypes = [c_int, c_int]
    lib.glUniform1i.restype = None
    lib.glUniform2fv.argtypes = [c_int, c_int, POINTER(c_float)]
    lib.glUniform2fv.restype = None

    lib.glGenTextures.argtypes = [c_int, POINTER(c_uint)]
    lib.glGenTextures.restype = None
    lib.glBindTexture.argtypes = [c_uint, c_uint]
    lib.glBindTexture.restype = None
    lib.glTexImage2D.argtypes = [c_uint, c_int, c_int, c_int, c_int, c_int,
                                  c_uint, c_uint, c_void_p]
    lib.glTexImage2D.restype = None
    lib.glTexParameteri.argtypes = [c_uint, c_uint, c_int]
    lib.glTexParameteri.restype = None
    lib.glDeleteTextures.argtypes = [c_int, POINTER(c_uint)]
    lib.glDeleteTextures.restype = None

    lib.glGenFramebuffers.argtypes = [c_int, POINTER(c_uint)]
    lib.glGenFramebuffers.restype = None
    lib.glBindFramebuffer.argtypes = [c_uint, c_uint]
    lib.glBindFramebuffer.restype = None
    lib.glFramebufferTexture2D.argtypes = [c_uint, c_uint, c_uint, c_uint, c_int]
    lib.glFramebufferTexture2D.restype = None
    lib.glCheckFramebufferStatus.argtypes = [c_uint]
    lib.glCheckFramebufferStatus.restype = c_uint
    lib.glDeleteFramebuffers.argtypes = [c_int, POINTER(c_uint)]
    lib.glDeleteFramebuffers.restype = None

    lib.glViewport.argtypes = [c_int, c_int, c_int, c_int]
    lib.glViewport.restype = None
    lib.glDrawArrays.argtypes = [c_uint, c_int, c_int]
    lib.glDrawArrays.restype = None
    lib.glPixelStorei.argtypes = [c_uint, c_int]
    lib.glPixelStorei.restype = None
    lib.glReadPixels.argtypes = [c_int, c_int, c_int, c_int, c_uint, c_uint, c_void_p]
    lib.glReadPixels.restype = None

    # Blending (for multi-plane compositing)
    lib.glEnable.argtypes = [c_uint]
    lib.glEnable.restype = None
    lib.glBlendFunc.argtypes = [c_uint, c_uint]
    lib.glBlendFunc.restype = None

    return lib


# ── EGL capture ──

# Function pointer types for EGL/GL extensions
_CreateImageKHR = CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_uint, c_void_p,
                             POINTER(c_int))
_DestroyImageKHR = CFUNCTYPE(c_int, c_void_p, c_void_p)
_ImageTargetTexture2DOES = CFUNCTYPE(None, c_uint, c_void_p)

VERT_SHADER = b"""#version 300 es
out vec2 tex_pos;
uniform vec2 uvs[4];
void main() {
  vec2 pos[4];
  pos[0] = vec2(-1.0, -1.0);
  pos[1] = vec2(1.0, -1.0);
  pos[2] = vec2(-1.0, 1.0);
  pos[3] = vec2(1.0, 1.0);
  gl_Position.xy = pos[gl_VertexID];
  gl_Position.zw = vec2(0.0, 1.0);
  tex_pos = uvs[gl_VertexID];
}
"""

FRAG_SHADER = b"""#version 300 es
#extension GL_OES_EGL_image_external_essl3 : require
precision highp float;
uniform samplerExternalOES tex;
in vec2 tex_pos;
out vec4 fragColor;
void main() {
  fragColor = texture(tex, tex_pos);
}
"""


def _compile_shader(gl, shader_type, source):
    shader = gl.glCreateShader(shader_type)
    if not shader:
        raise RuntimeError("glCreateShader failed")
    src = c_char_p(source)
    gl.glShaderSource(shader, 1, byref(src), None)
    gl.glCompileShader(shader)
    status = c_int(0)
    gl.glGetShaderiv(shader, GL_COMPILE_STATUS, byref(status))
    if status.value != GL_TRUE:
        log_len = c_int(0)
        gl.glGetShaderiv(shader, GL_INFO_LOG_LENGTH, byref(log_len))
        log = create_string_buffer(max(log_len.value, 1))
        gl.glGetShaderInfoLog(shader, log_len.value, None, log)
        gl.glDeleteShader(shader)
        raise RuntimeError(f"Shader compile failed: {log.value.decode()}")
    return shader


def _link_program(gl, vert_src, frag_src):
    program = gl.glCreateProgram()
    vert = _compile_shader(gl, GL_VERTEX_SHADER, vert_src)
    frag = _compile_shader(gl, GL_FRAGMENT_SHADER, frag_src)
    gl.glAttachShader(program, vert)
    gl.glAttachShader(program, frag)
    gl.glLinkProgram(program)
    status = c_int(0)
    gl.glGetProgramiv(program, GL_LINK_STATUS, byref(status))
    if status.value != GL_TRUE:
        log_len = c_int(0)
        gl.glGetProgramiv(program, GL_INFO_LOG_LENGTH, byref(log_len))
        log = create_string_buffer(max(log_len.value, 1))
        gl.glGetProgramInfoLog(program, log_len.value, None, log)
        gl.glDeleteShader(vert)
        gl.glDeleteShader(frag)
        gl.glDeleteProgram(program)
        raise RuntimeError(f"Program link failed: {log.value.decode()}")
    gl.glUseProgram(program)
    gl.glUniform1i(gl.glGetUniformLocation(program, b"tex"), 0)
    gl.glDeleteShader(vert)
    gl.glDeleteShader(frag)
    return program


def egl_capture_framebuffer(drm_lib, egl, gl, fd, crtc):
    """Capture framebuffer via EGL/GLES. Returns (width, height, rgb_rows)."""
    fb2 = get_fb2(drm_lib, fd, crtc.buffer_id)
    width, height = fb2.width, fb2.height
    has_modifier = (fb2.flags & 0x2) != 0  # DRM_MODE_FB_MODIFIERS

    # Count planes and export each handle as PRIME FD
    # (mirrors CreateImage in egl_capture.cc)
    plane_fds = []
    for plane in range(GBM_MAX_PLANES):
        if fb2.handles[plane] == 0:
            break
        pfd = c_int(0)
        rv = drm_lib.drmPrimeHandleToFD(fd, fb2.handles[plane], 0, byref(pfd))
        if rv:
            # Clean up already-exported fds
            for f in plane_fds:
                os.close(f)
            raise RuntimeError(f"drmPrimeHandleToFD plane {plane} failed: {rv}")
        plane_fds.append(pfd.value)
    num_planes = len(plane_fds)
    if num_planes == 0:
        raise RuntimeError("No planes found in framebuffer")

    # EGL init
    display = egl.eglGetDisplay(c_void_p(0))
    if not display:
        for f in plane_fds:
            os.close(f)
        raise RuntimeError("eglGetDisplay failed")

    maj, mn = c_int(0), c_int(0)
    if not egl.eglInitialize(display, byref(maj), byref(mn)):
        for f in plane_fds:
            os.close(f)
        raise RuntimeError(f"eglInitialize failed: 0x{egl.eglGetError():x}")

    try:
        # Check extensions
        exts = egl.eglQueryString(display, EGL_EXTENSIONS)
        if exts:
            exts = exts.decode()
        else:
            exts = ""
        for req in ("EGL_KHR_image_base", "EGL_EXT_image_dma_buf_import"):
            if req not in exts:
                raise RuntimeError(f"Missing EGL extension: {req}")
        has_import_modifiers = "EGL_EXT_image_dma_buf_import_modifiers" in exts

        # Get extension function pointers
        p = egl.eglGetProcAddress(b"eglCreateImageKHR")
        if not p:
            raise RuntimeError("eglCreateImageKHR not available")
        create_image = _CreateImageKHR(p)

        p = egl.eglGetProcAddress(b"eglDestroyImageKHR")
        if not p:
            raise RuntimeError("eglDestroyImageKHR not available")
        destroy_image = _DestroyImageKHR(p)

        p = egl.eglGetProcAddress(b"glEGLImageTargetTexture2DOES")
        if not p:
            raise RuntimeError("glEGLImageTargetTexture2DOES not available")
        image_target_tex = _ImageTargetTexture2DOES(p)

        # Choose config
        config_attribs = (c_int * 5)(EGL_SURFACE_TYPE, EGL_DONT_CARE,
                                      EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                                      EGL_NONE)
        config = c_void_p()
        num_configs = c_int(0)
        if not egl.eglChooseConfig(display, config_attribs, byref(config), 1,
                                    byref(num_configs)):
            raise RuntimeError("eglChooseConfig failed")
        if num_configs.value == 0:
            raise RuntimeError("No EGL config found")

        # Create context
        ctx_attribs = (c_int * 3)(EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE)
        ctx = egl.eglCreateContext(display, config, None, ctx_attribs)
        if not ctx:
            raise RuntimeError(f"eglCreateContext failed: 0x{egl.eglGetError():x}")

        try:
            if not egl.eglMakeCurrent(display, None, None, ctx):
                raise RuntimeError("eglMakeCurrent failed")

            # Check GL extensions
            gl_exts = gl.glGetString(GL_EXTENSIONS)
            if gl_exts:
                gl_exts = gl_exts.decode()
            else:
                gl_exts = ""
            for req in ("GL_OES_EGL_image", "GL_OES_EGL_image_external"):
                if req not in gl_exts:
                    raise RuntimeError(f"Missing GL extension: {req}")

            # Build EGL image attribute list with ALL planes
            # (mirrors CreateImage in egl_capture.cc lines 115-141)
            attrs = [
                EGL_WIDTH, width,
                EGL_HEIGHT, height,
                EGL_LINUX_DRM_FOURCC_EXT, fb2.pixel_format,
            ]
            for plane in range(num_planes):
                attrs.extend([
                    EGL_DMA_BUF_PLANE0_FD_EXT + plane * 3, plane_fds[plane],
                    EGL_DMA_BUF_PLANE0_OFFSET_EXT + plane * 3, fb2.offsets[plane],
                    EGL_DMA_BUF_PLANE0_PITCH_EXT + plane * 3, fb2.pitches[plane],
                ])
                if has_import_modifiers and has_modifier:
                    mod = fb2.modifier[plane]
                    attrs.extend([
                        EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT + plane * 2,
                        int(mod & 0xFFFFFFFF),
                        EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT + plane * 2,
                        int(mod >> 32),
                    ])
            attrs.append(EGL_NONE)
            attr_array = (c_int * len(attrs))(*attrs)

            # Create EGLImage from DMA-BUF
            image = create_image(display, None, EGL_LINUX_DMA_BUF_EXT, None,
                                  attr_array)
            if not image:
                raise RuntimeError(f"eglCreateImageKHR failed: 0x{egl.eglGetError():x}")

            try:
                # Setup output texture (render target)
                out_tex = c_uint(0)
                gl.glGenTextures(1, byref(out_tex))
                gl.glBindTexture(GL_TEXTURE_2D, out_tex)
                gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                                 GL_RGBA, GL_UNSIGNED_BYTE, None)

                # Setup FBO
                fbo = c_uint(0)
                gl.glGenFramebuffers(1, byref(fbo))
                gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo)
                gl.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                           GL_TEXTURE_2D, out_tex, 0)
                fb_status = gl.glCheckFramebufferStatus(GL_FRAMEBUFFER)
                if fb_status != GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError(f"Framebuffer incomplete: 0x{fb_status:x}")

                # Setup input texture (external)
                in_tex = c_uint(0)
                gl.glGenTextures(1, byref(in_tex))
                gl.glBindTexture(GL_TEXTURE_EXTERNAL_OES, in_tex)
                gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_S,
                                    GL_CLAMP_TO_EDGE)
                gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_T,
                                    GL_CLAMP_TO_EDGE)
                gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MIN_FILTER,
                                    GL_LINEAR)
                gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MAG_FILTER,
                                    GL_LINEAR)

                # Compile and link shaders
                program = _link_program(gl, VERT_SHADER, FRAG_SHADER)
                uvs_loc = gl.glGetUniformLocation(program, b"uvs")

                # Set UV coordinates (full framebuffer, no crop)
                uvs = (c_float * 8)(
                    0.0, 0.0,   # bottom-left
                    1.0, 0.0,   # bottom-right
                    0.0, 1.0,   # top-left
                    1.0, 1.0,   # top-right
                )
                gl.glUniform2fv(uvs_loc, 4, uvs)

                # Bind EGLImage to external texture and render
                gl.glViewport(0, 0, width, height)
                image_target_tex(GL_TEXTURE_EXTERNAL_OES, image)
                gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

                # Read pixels
                gl.glPixelStorei(GL_PACK_ALIGNMENT, 1)
                buf = create_string_buffer(width * height * 4)
                gl.glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE,
                                 buf)

                # Cleanup GL objects
                gl.glDeleteProgram(program)
                gl.glDeleteTextures(1, byref(in_tex))
                gl.glDeleteFramebuffers(1, byref(fbo))
                gl.glDeleteTextures(1, byref(out_tex))

            finally:
                destroy_image(display, image)

        finally:
            egl.eglMakeCurrent(display, None, None, None)
            egl.eglDestroyContext(display, ctx)

    finally:
        egl.eglTerminate(display)
        for f in plane_fds:
            os.close(f)

    # Convert RGBA → RGB rows (top-to-bottom, no flip needed with corrected UVs)
    raw = buf.raw
    rgb_rows = []
    for y in range(height):
        row_off = y * width * 4
        rgba = raw[row_off:row_off + width * 4]
        row = bytearray(width * 3)
        row[0::3] = rgba[0::4]  # R
        row[1::3] = rgba[1::4]  # G
        row[2::3] = rgba[2::4]  # B
        rgb_rows.append(bytes(row))

    return width, height, rgb_rows


def _create_egl_image(egl, drm_lib, display, fd, fb2, create_image,
                      has_import_modifiers):
    """Create an EGLImage from a DRM framebuffer. Returns (image, plane_fds)."""
    has_modifier = (fb2.flags & 0x2) != 0

    plane_fds = []
    for plane in range(GBM_MAX_PLANES):
        if fb2.handles[plane] == 0:
            break
        pfd = c_int(0)
        rv = drm_lib.drmPrimeHandleToFD(fd, fb2.handles[plane], 0, byref(pfd))
        if rv:
            for f in plane_fds:
                os.close(f)
            raise RuntimeError(f"drmPrimeHandleToFD plane {plane} failed: {rv}")
        plane_fds.append(pfd.value)
    num_planes = len(plane_fds)
    if num_planes == 0:
        raise RuntimeError("No planes found in framebuffer")

    attrs = [
        EGL_WIDTH, fb2.width,
        EGL_HEIGHT, fb2.height,
        EGL_LINUX_DRM_FOURCC_EXT, fb2.pixel_format,
    ]
    for plane in range(num_planes):
        attrs.extend([
            EGL_DMA_BUF_PLANE0_FD_EXT + plane * 3, plane_fds[plane],
            EGL_DMA_BUF_PLANE0_OFFSET_EXT + plane * 3, fb2.offsets[plane],
            EGL_DMA_BUF_PLANE0_PITCH_EXT + plane * 3, fb2.pitches[plane],
        ])
        if has_import_modifiers and has_modifier:
            mod = fb2.modifier[plane]
            attrs.extend([
                EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT + plane * 2,
                int(mod & 0xFFFFFFFF),
                EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT + plane * 2,
                int(mod >> 32),
            ])

    # Note: EGL_YUV_COLOR_SPACE_HINT_EXT / EGL_SAMPLE_RANGE_HINT_EXT cause
    # EGL_BAD_PARAMETER on ChromeOS Mesa. The GPU handles YUV→RGB conversion
    # automatically via GL_OES_EGL_image_external without explicit hints.

    attrs.append(EGL_NONE)
    attr_array = (c_int * len(attrs))(*attrs)

    image = create_image(display, None, EGL_LINUX_DMA_BUF_EXT, None, attr_array)
    if not image:
        for f in plane_fds:
            os.close(f)
        raise RuntimeError(f"eglCreateImageKHR failed: 0x{egl.eglGetError():x}")

    return image, plane_fds


def egl_capture_composited(drm_lib, egl, gl, fd, crtc):
    """Capture all DRM planes via EGL compositing. Returns (width, height, rgb_rows).

    Enumerates all planes on the CRTC (primary + overlays) and composites them
    with alpha blending. Falls back to single-FB capture if enumeration fails.
    """
    planes = _get_crtc_planes(drm_lib, fd, crtc)
    if len(planes) <= 1:
        # No overlays or enumeration failed — use simple path
        return egl_capture_framebuffer(drm_lib, egl, gl, fd, crtc)

    width = crtc.width if crtc.width else crtc.mode.hdisplay
    height = crtc.height if crtc.height else crtc.mode.vdisplay

    # EGL init
    display = egl.eglGetDisplay(c_void_p(0))
    if not display:
        raise RuntimeError("eglGetDisplay failed")

    maj, mn = c_int(0), c_int(0)
    if not egl.eglInitialize(display, byref(maj), byref(mn)):
        raise RuntimeError(f"eglInitialize failed: 0x{egl.eglGetError():x}")

    try:
        exts = egl.eglQueryString(display, EGL_EXTENSIONS)
        exts = exts.decode() if exts else ""
        for req in ("EGL_KHR_image_base", "EGL_EXT_image_dma_buf_import"):
            if req not in exts:
                raise RuntimeError(f"Missing EGL extension: {req}")
        has_import_modifiers = "EGL_EXT_image_dma_buf_import_modifiers" in exts

        # Get extension function pointers
        p = egl.eglGetProcAddress(b"eglCreateImageKHR")
        if not p:
            raise RuntimeError("eglCreateImageKHR not available")
        create_image = _CreateImageKHR(p)

        p = egl.eglGetProcAddress(b"eglDestroyImageKHR")
        if not p:
            raise RuntimeError("eglDestroyImageKHR not available")
        destroy_image = _DestroyImageKHR(p)

        p = egl.eglGetProcAddress(b"glEGLImageTargetTexture2DOES")
        if not p:
            raise RuntimeError("glEGLImageTargetTexture2DOES not available")
        image_target_tex = _ImageTargetTexture2DOES(p)

        # Choose config and create context
        config_attribs = (c_int * 5)(EGL_SURFACE_TYPE, EGL_DONT_CARE,
                                      EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                                      EGL_NONE)
        config = c_void_p()
        num_configs = c_int(0)
        if not egl.eglChooseConfig(display, config_attribs, byref(config), 1,
                                    byref(num_configs)) or num_configs.value == 0:
            raise RuntimeError("eglChooseConfig failed")

        ctx_attribs = (c_int * 3)(EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE)
        ctx = egl.eglCreateContext(display, config, None, ctx_attribs)
        if not ctx:
            raise RuntimeError(f"eglCreateContext failed: 0x{egl.eglGetError():x}")

        try:
            if not egl.eglMakeCurrent(display, None, None, ctx):
                raise RuntimeError("eglMakeCurrent failed")

            # Setup output FBO
            out_tex = c_uint(0)
            gl.glGenTextures(1, byref(out_tex))
            gl.glBindTexture(GL_TEXTURE_2D, out_tex)
            gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, None)

            fbo = c_uint(0)
            gl.glGenFramebuffers(1, byref(fbo))
            gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                       GL_TEXTURE_2D, out_tex, 0)
            fb_status = gl.glCheckFramebufferStatus(GL_FRAMEBUFFER)
            if fb_status != GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"Framebuffer incomplete: 0x{fb_status:x}")

            # Setup input texture
            in_tex = c_uint(0)
            gl.glGenTextures(1, byref(in_tex))
            gl.glBindTexture(GL_TEXTURE_EXTERNAL_OES, in_tex)
            gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_S,
                                GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_WRAP_T,
                                GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MIN_FILTER,
                                GL_LINEAR)
            gl.glTexParameteri(GL_TEXTURE_EXTERNAL_OES, GL_TEXTURE_MAG_FILTER,
                                GL_LINEAR)

            # Compile shaders
            program = _link_program(gl, VERT_SHADER, FRAG_SHADER)
            uvs_loc = gl.glGetUniformLocation(program, b"uvs")

            # Enable alpha blending for compositing
            gl.glEnable(GL_BLEND)
            gl.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            # Render each plane bottom-to-top
            for plane_info in planes:
                fb2 = plane_info["fb2"]
                try:
                    image, pfds = _create_egl_image(
                        egl, drm_lib, display, fd, fb2, create_image,
                        has_import_modifiers)
                except RuntimeError:
                    continue  # skip planes we can't import

                try:
                    # UV coordinates from source crop
                    fw = float(fb2.width)
                    fh = float(fb2.height)
                    uv_left = plane_info["src_x"] / fw
                    uv_right = (plane_info["src_x"] + plane_info["src_w"]) / fw
                    uv_top = plane_info["src_y"] / fh
                    uv_bottom = (plane_info["src_y"] + plane_info["src_h"]) / fh
                    uvs = (c_float * 8)(
                        uv_left, uv_top,
                        uv_right, uv_top,
                        uv_left, uv_bottom,
                        uv_right, uv_bottom,
                    )
                    gl.glUniform2fv(uvs_loc, 4, uvs)

                    # Viewport from CRTC destination rect
                    gl.glViewport(plane_info["crtc_x"],
                                  height - plane_info["crtc_y"] - plane_info["crtc_h"],
                                  plane_info["crtc_w"], plane_info["crtc_h"])

                    image_target_tex(GL_TEXTURE_EXTERNAL_OES, image)
                    gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
                finally:
                    destroy_image(display, image)
                    for f in pfds:
                        os.close(f)

            # Read composited result
            gl.glPixelStorei(GL_PACK_ALIGNMENT, 1)
            buf = create_string_buffer(width * height * 4)
            gl.glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, buf)

            # Cleanup
            gl.glDeleteProgram(program)
            gl.glDeleteTextures(1, byref(in_tex))
            gl.glDeleteFramebuffers(1, byref(fbo))
            gl.glDeleteTextures(1, byref(out_tex))

        finally:
            egl.eglMakeCurrent(display, None, None, None)
            egl.eglDestroyContext(display, ctx)

    finally:
        egl.eglTerminate(display)

    # Convert RGBA → RGB rows
    raw = buf.raw
    rgb_rows = []
    for y in range(height):
        row_off = y * width * 4
        rgba = raw[row_off:row_off + width * 4]
        row = bytearray(width * 3)
        row[0::3] = rgba[0::4]
        row[1::3] = rgba[1::4]
        row[2::3] = rgba[2::4]
        rgb_rows.append(bytes(row))

    return width, height, rgb_rows


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


def _get_plane_properties(drm_lib, fd, plane_id):
    """Read DRM properties for a plane. Returns dict of name->value."""
    props_ptr = drm_lib.drmModeObjectGetProperties(fd, plane_id,
                                                     DRM_MODE_OBJECT_PLANE)
    if not props_ptr:
        return {}
    props = props_ptr.contents
    result = {}
    for i in range(props.count_props):
        prop_ptr = drm_lib.drmModeGetProperty(fd, props.props[i])
        if not prop_ptr:
            continue
        name = prop_ptr.contents.name.decode("ascii", errors="replace")
        result[name] = props.prop_values[i]
        drm_lib.drmModeFreeProperty(prop_ptr)
    drm_lib.drmModeFreeObjectProperties(props_ptr)
    return result


def _get_crtc_planes(drm_lib, fd, crtc):
    """Enumerate all active DRM planes on a CRTC.

    Returns list of dicts with keys: fb2, crtc_x, crtc_y, crtc_w, crtc_h,
    src_x, src_y, src_w, src_h, color_encoding, color_range.
    Planes are in enumeration order (z-order by DRM convention).
    Returns empty list if plane enumeration is not available.
    """
    # Enable atomic mode to see all planes (primary + overlay + cursor)
    rv = drm_lib.drmSetClientCap(fd, DRM_CLIENT_CAP_ATOMIC, 1)
    if rv:
        return []

    plane_res_ptr = drm_lib.drmModeGetPlaneResources(fd)
    if not plane_res_ptr:
        return []

    plane_res = plane_res_ptr.contents
    planes = []
    try:
        for i in range(plane_res.count_planes):
            plane_ptr = drm_lib.drmModeGetPlane(fd, plane_res.planes[i])
            if not plane_ptr:
                continue
            plane = plane_ptr.contents
            try:
                # Skip planes not on our CRTC or without a framebuffer
                if plane.crtc_id != crtc.crtc_id or plane.fb_id == 0:
                    continue

                # Read plane properties
                props = _get_plane_properties(drm_lib, fd, plane.plane_id)

                # Get framebuffer info
                try:
                    fb2 = get_fb2(drm_lib, fd, plane.fb_id)
                except RuntimeError:
                    continue

                # SRC_* are in 16.16 fixed-point format
                src_x = (props.get("SRC_X", 0) >> 16) + \
                        (props.get("SRC_X", 0) & 0xFFFF) / 65536.0
                src_y = (props.get("SRC_Y", 0) >> 16) + \
                        (props.get("SRC_Y", 0) & 0xFFFF) / 65536.0
                src_w = (props.get("SRC_W", 0) >> 16) + \
                        (props.get("SRC_W", 0) & 0xFFFF) / 65536.0
                src_h = (props.get("SRC_H", 0) >> 16) + \
                        (props.get("SRC_H", 0) & 0xFFFF) / 65536.0

                # Fall back to full FB dimensions if SRC_W/H are 0
                if src_w == 0:
                    src_w = float(fb2.width)
                if src_h == 0:
                    src_h = float(fb2.height)

                # Map COLOR_ENCODING enum values
                ce = props.get("COLOR_ENCODING")
                color_encoding = {0: "bt601", 1: "bt709", 2: "bt2020"}.get(ce)

                # Map COLOR_RANGE enum values
                cr = props.get("COLOR_RANGE")
                color_range = {0: "limited", 1: "full"}.get(cr)

                planes.append({
                    "fb2": fb2,
                    "plane_id": plane.plane_id,
                    "crtc_x": int(props.get("CRTC_X", 0)),
                    "crtc_y": int(props.get("CRTC_Y", 0)),
                    "crtc_w": int(props.get("CRTC_W", fb2.width)),
                    "crtc_h": int(props.get("CRTC_H", fb2.height)),
                    "src_x": src_x,
                    "src_y": src_y,
                    "src_w": src_w,
                    "src_h": src_h,
                    "color_encoding": color_encoding,
                    "color_range": color_range,
                    "format": _fourcc_str(fb2.pixel_format),
                })
            finally:
                drm_lib.drmModeFreePlane(plane_ptr)
    finally:
        drm_lib.drmModeFreePlaneResources(plane_res_ptr)

    return planes


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


# ── TurboJPEG JPEG encoder ──

_tj_lib = None
_tj_loaded = False

def _load_turbojpeg():
    """Load libturbojpeg.so. Returns CDLL or None."""
    global _tj_lib, _tj_loaded
    if _tj_loaded:
        return _tj_lib
    _tj_loaded = True
    for name in ("libturbojpeg.so", "libturbojpeg.so.0"):
        try:
            lib = CDLL(name)
            lib.tjInitCompress.argtypes = []
            lib.tjInitCompress.restype = c_void_p
            lib.tjCompress2.argtypes = [
                c_void_p, c_void_p, c_int, c_int, c_int, c_int,
                POINTER(c_void_p), POINTER(c_ulong), c_int, c_int, c_int,
            ]
            lib.tjCompress2.restype = c_int
            lib.tjFree.argtypes = [c_void_p]
            lib.tjFree.restype = None
            lib.tjDestroy.argtypes = [c_void_p]
            lib.tjDestroy.restype = c_int
            _tj_lib = lib
            return lib
        except OSError:
            continue
    return None


def encode_jpeg(width, height, rgb_rows, quality=80):
    """Encode RGB row data as JPEG via libturbojpeg. Returns bytes or None."""
    tj = _load_turbojpeg()
    if tj is None:
        return None
    handle = tj.tjInitCompress()
    if not handle:
        return None
    try:
        rgb_data = b"".join(rgb_rows)
        src = (c_char * len(rgb_data)).from_buffer_copy(rgb_data)
        jpeg_buf = c_void_p(0)
        jpeg_size = c_ulong(0)
        TJPF_RGB = 0
        TJSAMP_420 = 2
        rv = tj.tjCompress2(
            handle, src,
            c_int(width), c_int(width * 3), c_int(height),
            c_int(TJPF_RGB),
            byref(jpeg_buf), byref(jpeg_size),
            c_int(TJSAMP_420), c_int(quality), c_int(0),
        )
        if rv != 0:
            return None
        result = bytes(string_at(jpeg_buf, jpeg_size.value))
        return result
    except Exception:
        return None
    finally:
        if jpeg_buf.value:
            tj.tjFree(jpeg_buf)
        tj.tjDestroy(handle)


# ── Diagnostics ──

def run_diag():
    """Print diagnostic info about DRM devices and EGL capability."""
    drm_lib = _load_drm()
    _setup_drm(drm_lib)

    # Check EGL availability
    egl_lib = _load_egl()
    gl_lib = _load_glesv2() if egl_lib else None
    print(f"EGL: {'available' if egl_lib else 'not available'}")
    print(f"GLESv2: {'available' if gl_lib else 'not available'}")

    if egl_lib:
        display = egl_lib.eglGetDisplay(c_void_p(0))
        if display:
            maj, mn = c_int(0), c_int(0)
            if egl_lib.eglInitialize(display, byref(maj), byref(mn)):
                print(f"EGL version: {maj.value}.{mn.value}")
                exts = egl_lib.eglQueryString(display, EGL_EXTENSIONS)
                if exts:
                    for e in exts.decode().split():
                        if "image" in e.lower() or "dma" in e.lower():
                            print(f"  {e}")
                egl_lib.eglTerminate(display)

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

        # Show all planes on this CRTC
        planes = _get_crtc_planes(drm_lib, fd, crtc)
        if planes:
            print(f"  Planes ({len(planes)}):")
            for p in planes:
                print(f"    plane {p['plane_id']}: {p['format']} "
                      f"{p['fb2'].width}x{p['fb2'].height} "
                      f"-> CRTC({p['crtc_x']},{p['crtc_y']} "
                      f"{p['crtc_w']}x{p['crtc_h']})"
                      f"{' ' + p['color_encoding'] if p['color_encoding'] else ''}")
        else:
            print("  Planes: enumeration not available")

        os.close(fd)


# ── Main ──

def _capture_raw(drm_lib, cards, capture_fn):
    """Try capture_fn(drm_lib, fd, crtc) on each card. Returns (w, h, rows)."""
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
                return capture_fn(drm_lib, fd, crtc)
        except Exception as e:
            last_error = e
        finally:
            os.close(fd)
    if last_error:
        raise last_error
    raise RuntimeError("No active CRTC found on any DRM device")


def _capture_with(drm_lib, cards, capture_fn):
    """Try capture_fn(drm_lib, fd, crtc) on each card. Returns PNG bytes."""
    w, h, rows = _capture_raw(drm_lib, cards, capture_fn)
    return encode_png(w, h, rows)


def _drm_setup_and_fns():
    """Common setup: load DRM, enumerate cards, define capture functions."""
    drm_lib = _load_drm()
    _setup_drm(drm_lib)
    cards = sorted(f for f in os.listdir("/dev/dri") if f.startswith("card"))
    if not cards:
        raise RuntimeError("No DRM devices found in /dev/dri/")

    def egl_fn(drm_lib, fd, crtc):
        egl_lib = _load_egl()
        gl_lib = _load_glesv2()
        if not egl_lib or not gl_lib:
            raise RuntimeError("EGL/GLESv2 libraries not available")
        return egl_capture_composited(drm_lib, egl_lib, gl_lib, fd, crtc)

    def gbm_fn(drm_lib, fd, crtc):
        gbm_lib = _load_gbm()
        return capture_framebuffer(drm_lib, gbm_lib, fd, crtc)

    return drm_lib, cards, egl_fn, gbm_fn


def _capture_by_method(method=None):
    """Capture raw RGB rows. Returns (w, h, rows). Raises on failure."""
    drm_lib, cards, egl_fn, gbm_fn = _drm_setup_and_fns()

    if method == "egl":
        return _capture_raw(drm_lib, cards, egl_fn)

    if method == "gbm":
        return _capture_raw(drm_lib, cards, gbm_fn)

    # Auto: try EGL first, fall back to GBM
    try:
        return _capture_raw(drm_lib, cards, egl_fn)
    except Exception:
        pass
    return _capture_raw(drm_lib, cards, gbm_fn)


def drm_screenshot(method=None):
    """Take a DRM screenshot. method: 'egl', 'gbm', or None (try egl then gbm).
    Returns PNG bytes or raises RuntimeError."""
    w, h, rows = _capture_by_method(method)
    return encode_png(w, h, rows)


def drm_screenshot_base64(method=None):
    """Take a DRM screenshot. Returns base64-encoded PNG string."""
    return base64.b64encode(drm_screenshot(method=method)).decode("ascii")


def drm_screenshot_jpeg(method=None, quality=80):
    """Take a DRM screenshot as JPEG (PNG fallback). Returns (bytes, fmt)."""
    w, h, rows = _capture_by_method(method)
    jpeg = encode_jpeg(w, h, rows, quality=quality)
    if jpeg is not None:
        return jpeg, "jpeg"
    return encode_png(w, h, rows), "png"


def drm_screenshot_jpeg_base64(method=None, quality=80):
    """Take a DRM screenshot as JPEG. Returns (base64_string, fmt)."""
    data, fmt = drm_screenshot_jpeg(method=method, quality=quality)
    return base64.b64encode(data).decode("ascii"), fmt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DRM/GBM/EGL screenshot capture")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output file path (default: stdout)")
    parser.add_argument("--method", choices=["egl", "gbm"],
                        help="Capture method (default: try egl then gbm)")
    parser.add_argument("--stdout", action="store_true",
                        help="Write raw image bytes to stdout")
    parser.add_argument("--jpeg", action="store_true",
                        help="Encode as JPEG (default: PNG)")
    parser.add_argument("-q", "--quality", type=int, default=80,
                        help="JPEG quality 1-100 (default: 80)")
    parser.add_argument("--base64", action="store_true",
                        help="Output base64 to stdout")
    parser.add_argument("--diag", action="store_true",
                        help="Print diagnostic info")
    args = parser.parse_args()

    if args.diag:
        run_diag()
        sys.exit(0)

    try:
        if args.jpeg:
            data, fmt = drm_screenshot_jpeg(method=args.method, quality=args.quality)
        else:
            data = drm_screenshot(method=args.method)
            fmt = "png"
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.stdout:
        sys.stdout.buffer.write(data)
    elif args.base64:
        sys.stdout.write(base64.b64encode(data).decode("ascii"))
    elif args.output:
        with open(args.output, "wb") as f:
            f.write(data)
        print(f"{args.output} ({len(data)} bytes, {fmt})")
    else:
        sys.stdout.buffer.write(data)
