"""Human-side fixture actions on actual GTK or GNOME notification controls."""
import contextlib


def visible_nodes(linuxui,root):
    # Shell's hidden overview and notification history can contain thousands
    # of actors. Do not walk those trees while a live warning expires.
    pending=[(root,(),0)];rows=[]
    while pending and len(rows)<1000:
        node,path,depth=pending.pop()
        states=linuxui.state_names(node)
        if depth>1 and 'showing' not in states:continue
        name=linuxui.safe(node.get_name,'');role=linuxui.safe(node.get_role_name,'')
        rows.append((node,path,name,role,states))
        if depth<25:
            pending.extend((child,path+(index,),depth+1) for index,child in linuxui.children(node))
    return rows


def find(linuxui,label):
    roots=linuxui.application_roots(linuxui.desktop());matches=[]
    for root in roots:
        name=linuxui.safe(root.get_name,'')
        if name not in ('machine-control-safety','gnome-shell'):continue
        root.clear_cache();rows=visible_nodes(linuxui,root)
        titles=[path for _,path,title,role,states in rows if title.startswith('Machine Control — ') and role=='label' and 'showing' in states]
        for node,path,title,role,states in rows:
            wanted=role=='push button' and title==label
            if not wanted or 'showing' not in states:continue
            if name=='gnome-shell':
                ours=any(path[:-count] and any(title_path[:len(path)-count]==path[:-count] for title_path in titles)
                    for count in range(1,min(5,len(path))))
                if not ours:continue
            bounds=linuxui.bounds(node)
            if not bounds or bounds['width']<=0 or bounds['height']<=0:continue
            info=dict(name=title,role=role,states=states,bounds=bounds,path='/'.join(map(str,path)))
            matches.append((name,node,info))
    selected=[(node,info) for name,node,info in matches if name=='machine-control-safety']
    if not selected:selected=[(node,info) for _,node,info in matches]
    return selected[0] if len(selected)==1 else None


def press(linuxui,control,operator):
    node,info=control
    info['fixtureRoute']='none';info['fixtureReason']='unadvertised_action'
    with contextlib.suppress(Exception):
        info['fixtureAdvertisedActions']=node.get_n_actions()
        if info['fixtureAdvertisedActions']>0 and node.do_action(0):
            info['fixtureRoute']='atspi-action';info['fixtureReason']='delivered';return True
    # GNOME St controls expose focus/geometry but no AT-SPI action on this
    # session. Use the configured native focus shortcut and the exact focused
    # control through the independent fixture operator, never an app endpoint.
    from gi.repository import Gio
    import re,time
    info['fixtureRoute']='native-keyboard'
    bindings=Gio.Settings.new('org.gnome.shell.keybindings').get_strv('focus-active-notification')
    if not bindings:return False
    binding=bindings[0];modifiers=re.findall(r'<([^>]+)>',binding)
    names={'Super':'super','Control':'ctrl','Primary':'ctrl','Alt':'alt','Shift':'shift'}
    if any(value not in names for value in modifiers):return False
    key=re.sub(r'<[^>]+>','',binding).lower()
    if not re.fullmatch('[a-z0-9]+',key):return False
    shortcut='+'.join([*(names[value] for value in modifiers),key])
    info['fixtureReason']='focus_shortcut'
    if operator('input.key',key=shortcut).get('accepted') is not True:return False
    time.sleep(.15)
    if info['role']=='push button':
        fresh=control
        info['fixtureReason']='fresh_control_missing'
        if fresh is None:return False
        info['fixtureReason']='grab_focus_refused'
        if not fresh[0].grab_focus():return False
        deadline=time.monotonic()+1
        from gi.repository import GLib
        while time.monotonic()<deadline:
            context=GLib.MainContext.default()
            for _ in range(32):
                if not context.pending():break
                context.iteration(False)
            fresh[0].clear_cache()
            if 'focused' in linuxui.state_names(fresh[0]):break
            time.sleep(.05)
        else:
            info['fixtureReason']='focus_not_observed';return False
    info['fixtureReason']='enter_refused'
    delivered=operator('input.key',key='enter').get('accepted') is True
    if delivered:info['fixtureReason']='delivered'
    return delivered
