"""Human-side fixture actions on actual GTK or GNOME notification controls."""
import contextlib


def find(linuxui,label):
    roots=linuxui.application_roots(linuxui.desktop());matches=[]
    for root in roots:
        name=linuxui.safe(root.get_name,'')
        if name not in ('machine-control-safety','gnome-shell'):continue
        root.clear_cache()
        for node,info in linuxui.walk(root,30,3000):
            bounds=info.get('bounds') or {}
            if 'showing' not in info['states'] or bounds.get('width',0)<=0 or bounds.get('height',0)<=0:continue
            wanted=(info['role']=='label' and info['name'].startswith('Machine Control — ')) if label=='Open task controls' else info['role']=='push button' and info['name']==label
            if not wanted:continue
            if name=='gnome-shell':
                ancestor=node;ours=False
                for _ in range(5):
                    ancestor=linuxui.safe(ancestor.get_parent,None)
                    if ancestor is None:break
                    if any(i['name'].startswith('Machine Control — ') for _,i in linuxui.walk(ancestor,7,250)):
                        ours=True;break
                if not ours:continue
            matches.append((name,node,info))
    selected=[(node,info) for name,node,info in matches if name=='machine-control-safety']
    if not selected:selected=[(node,info) for _,node,info in matches]
    return selected[0] if len(selected)==1 else None


def press(linuxui,control,operator):
    node,info=control
    with contextlib.suppress(Exception):
        if node.do_action(0):return True
    # GNOME St controls expose focus/geometry but no AT-SPI action on this
    # session. Use the configured native focus shortcut and the exact focused
    # control through the independent fixture operator, never an app endpoint.
    from gi.repository import Gio
    import re,time
    bindings=Gio.Settings.new('org.gnome.shell.keybindings').get_strv('focus-active-notification')
    if not bindings:return False
    binding=bindings[0];modifiers=re.findall(r'<([^>]+)>',binding)
    names={'Super':'super','Control':'ctrl','Primary':'ctrl','Alt':'alt','Shift':'shift'}
    if any(value not in names for value in modifiers):return False
    key=re.sub(r'<[^>]+>','',binding).lower()
    if not re.fullmatch('[a-z0-9]+',key):return False
    shortcut='+'.join([*(names[value] for value in modifiers),key])
    if operator('input.key',key=shortcut).get('accepted') is not True:return False
    time.sleep(.15)
    if info['role']=='push button':
        fresh=find(linuxui,info['name'])
        if fresh is None or not fresh[0].grab_focus():return False
        fresh[0].clear_cache()
        if 'focused' not in linuxui.state_names(fresh[0]):return False
    delivered=operator('input.key',key='enter').get('accepted') is True
    # Explicit fixture selection releases Shell's keyboard grab. Opening the
    # full controls intentionally focuses that window instead.
    if info['role']=='push button' and delivered:operator('input.key',key='alt+tab')
    return delivered
