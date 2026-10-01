; Remove browser registration only when its manifest still names this exact
; installation. Scratch installs must preserve another installation's host.
!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
    Push $R0
    IfFileExists "$INSTDIR\runtime\machine-control-windows.exe" 0 +3
      nsExec::ExecToLog '"$INSTDIR\runtime\machine-control-windows.exe" browser-unregister'
      Pop $R0
    Pop $R0
  ${EndIf}
!macroend

; Startup belongs to an explicit operator preference. Remove only our own
; per-user entry during uninstall; never stop an appliance/component service.
!macro NSIS_HOOK_POSTUNINSTALL
  ${If} $UpdateMode <> 1
    Push $R0
    ReadRegStr $R0 HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Machine Control"
    ${If} $R0 == "$INSTDIR\machine-control.exe --background"
    ${OrIf} $R0 == '"$INSTDIR\machine-control.exe" --background'
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Machine Control"
    ${EndIf}
    Pop $R0
  ${EndIf}
!macroend
; Chrome reconnects while the sender is stopped. Hide only the owning host's
; manifest before extraction and wait for its existing images to close. Use
; the incoming signed companion from the NSIS temporary directory, so this
; also fixes updates sent by previews that do not know this protocol.
!define MC_BROWSER_HELPER_SOURCE "${__FILEDIR__}\..\src-tauri\native\runtime\machine-control-windows.exe"
!macro NSIS_HOOK_PREINSTALL
  ${If} $UpdateMode = 1
    Push $R0
    Push $OUTDIR
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File /oname=machine-control-install.exe "${MC_BROWSER_HELPER_SOURCE}"
    nsExec::ExecToLog '"$PLUGINSDIR\machine-control-install.exe" browser-install-prepare "$INSTDIR"'
    Pop $R0
    ${If} $R0 <> 0
      Pop $R0
      SetOutPath "$R0"
      Pop $R0
      Abort "Browser host did not stop for update."
    ${EndIf}
    Pop $R0
    SetOutPath "$R0"
    Pop $R0
  ${EndIf}
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ${If} $UpdateMode = 1
    Push $R0
    nsExec::ExecToLog '"$PLUGINSDIR\machine-control-install.exe" browser-install-finish "$INSTDIR"'
    Pop $R0
    ${If} $R0 <> 0
      Pop $R0
      Abort "Browser registration changed during update."
    ${EndIf}
    Pop $R0
  ${EndIf}
!macroend
