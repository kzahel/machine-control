Machine Control desktop and command-line automation

Start here from PowerShell in this folder:
  .\machine-control.exe --help
  .\machine-control.exe agent instructions
  .\machine-control.exe agent identity --paths

This installation includes its own Python runtime; no separate Python
installation or source checkout is needed. The runtime folder contains the
resident companion, not the public automation entry point.

With the installer's "Add to user PATH" option, use machine-control from a
new terminal. Restart an already-running agent host to inherit the new PATH.
An absolute path works immediately, including in PowerShell:
  & 'C:\path\to\Machine Control\machine-control.exe' agent instructions

Running the bare command in a terminal starts the app if necessary and prints
next steps. Use --start to request that behavior explicitly or --gui to open
the operator window. Starting the app does not enable desktop access.
Explicit help, agent instructions and identity work with the app stopped.
Ordinary control commands require the existing doctor, claims and access flow.

agent identity preserves the signed package metadata used by existing clients.
Add --paths for resolved installation details. These paths identify this
client's bundle, not necessarily the resident answering a live request.

Silent installer: /ADDTOPATH=1 enables registration; /ADDTOPATH=0 disables it.
Without either option, the previous preference is retained, defaulting to on
for a first install. Repair and updates preserve the preference; uninstall
removes only the PATH entry this installation added.
