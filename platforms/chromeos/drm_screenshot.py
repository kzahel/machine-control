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
    python3 drm_screenshot.py [output.png]
    python3 drm_screenshot.py --base64    # output base64 to stdout
    python3 drm_screenshot.py --diag      # print diagnostic info

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
    c_int, c_size_t, c_uint, c_ulonglong, c_ushort, c_void_p, c_voidp,
    cast, create_string_buffer, string_at,
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

        os.close(fd)


# ── Main ──

def _capture_with(drm_lib, cards, capture_fn):
    """Try capture_fn(drm_lib, fd, crtc) on each card. Returns PNG bytes."""
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
                w, h, rows = capture_fn(drm_lib, fd, crtc)
                return encode_png(w, h, rows)
        except Exception as e:
            last_error = e
        finally:
            os.close(fd)
    if last_error:
        raise last_error
    return None


def drm_screenshot(method=None):
    """Take a DRM screenshot. method: 'egl', 'gbm', or None (try egl then gbm).
    Returns PNG bytes or raises RuntimeError."""
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
        return egl_capture_framebuffer(drm_lib, egl_lib, gl_lib, fd, crtc)

    def gbm_fn(drm_lib, fd, crtc):
        gbm_lib = _load_gbm()
        return capture_framebuffer(drm_lib, gbm_lib, fd, crtc)

    if method == "egl":
        result = _capture_with(drm_lib, cards, egl_fn)
        if result:
            return result
        raise RuntimeError("EGL capture failed on all DRM devices")

    if method == "gbm":
        result = _capture_with(drm_lib, cards, gbm_fn)
        if result:
            return result
        raise RuntimeError("GBM capture failed on all DRM devices")

    # Auto: try EGL first, fall back to GBM
    try:
        result = _capture_with(drm_lib, cards, egl_fn)
        if result:
            return result
    except Exception:
        pass

    result = _capture_with(drm_lib, cards, gbm_fn)
    if result:
        return result
    raise RuntimeError("No active CRTC found on any DRM device")


def drm_screenshot_base64(method=None):
    """Take a DRM screenshot. Returns base64-encoded PNG string."""
    return base64.b64encode(drm_screenshot(method=method)).decode("ascii")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DRM/GBM/EGL screenshot capture")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output PNG file path (default: stdout base64)")
    parser.add_argument("--method", choices=["egl", "gbm"],
                        help="Capture method (default: try egl then gbm)")
    parser.add_argument("--base64", action="store_true",
                        help="Output base64 to stdout")
    parser.add_argument("--diag", action="store_true",
                        help="Print diagnostic info")
    args = parser.parse_args()

    if args.diag:
        run_diag()
        sys.exit(0)

    try:
        png = drm_screenshot(method=args.method)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output and not args.base64:
        with open(args.output, "wb") as f:
            f.write(png)
        print(f"{args.output} ({len(png)} bytes)")
    else:
        sys.stdout.write(base64.b64encode(png).decode("ascii"))
