"""System GTK process boundary for the independent nonactivating notice."""

def prepare(source):
    environment=dict(source)
    for name in ('NO_AT_BRIDGE','DESKTOP_STARTUP_ID','XDG_ACTIVATION_TOKEN'):
        environment.pop(name,None)
    # Mutter honors the Xwayland notification/input hints for this GTK3
    # toplevel. Image surfaces avoid a blank accelerated X11 backing surface
    # on the qualified virtual-GPU profile; this small panel needs no GL.
    environment.update(GDK_BACKEND='x11',GDK_RENDERING='image',GDK_GL='disable')
    return environment
