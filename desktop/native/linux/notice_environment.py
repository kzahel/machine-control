"""System GTK process boundary for explicit native task controls."""

def prepare(source):
    environment=dict(source)
    for name in ('NO_AT_BRIDGE','DESKTOP_STARTUP_ID','XDG_ACTIVATION_TOKEN','GDK_RENDERING','GDK_GL'):
        environment.pop(name,None)
    environment['GDK_BACKEND']='wayland'
    return environment
