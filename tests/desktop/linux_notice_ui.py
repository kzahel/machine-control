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
    # GNOME St controls expose geometry but no AT-SPI action on the qualified
    # session. This is the independent fixture's explicit human-side input,
    # never an ordinary provider fallback or a product approval endpoint.
    bounds=info['bounds']
    reply=operator('input.click',x=bounds['x']+bounds['width']//2,
        y=bounds['y']+bounds['height']//2,button='left')
    return reply.get('accepted') is True
