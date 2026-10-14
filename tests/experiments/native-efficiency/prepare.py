#!/usr/bin/env python3
"""Build original fixture apps inside an explicitly selected disposable guest."""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--disposable-guest',action='store_true',required=True)
    args=parser.parse_args();os.umask(0o077)
    args.root.mkdir(parents=True,exist_ok=False)
    for pattern in ('*.py','*.swift'):
        for source in Path(__file__).parent.glob(pattern):shutil.copy2(source,args.root/source.name)
    binary=args.root/'Fixture'
    subprocess.run(['swiftc',str(args.root/'Fixture.swift'),'-o',str(binary)],check=True)
    for kind in ('target','sentinel'):
        app=args.root/(kind+'.app');mac=app/'Contents/MacOS';mac.mkdir(parents=True)
        shutil.copy2(binary,mac/'Fixture')
        info={'CFBundleIdentifier':'org.machine-control.efficiency.'+kind,
              'CFBundleName':'Efficiency '+kind.title(),'CFBundleExecutable':'Fixture',
              'CFBundlePackageType':'APPL','NSHighResolutionCapable':True}
        (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        subprocess.run(['codesign','--force','--sign','-',str(app)],check=True)
        state=args.root/kind;state.mkdir()
        subprocess.run(['open','-n',str(app),'--args',str(state),
                        *(['--sentinel'] if kind=='sentinel' else [])],check=True)


if __name__=='__main__':main()
