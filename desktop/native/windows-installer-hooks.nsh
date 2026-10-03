; Remove browser registration only when its manifest still names this exact
; installation. Scratch installs must preserve another installation's host.
!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
    ; Tauri normally stops the operator after this hook. Stop it first using
    ; the same installer policy, so its job closes the resident/provider pipe.
    !insertmacro CheckIfAppIsRunning "$INSTDIR\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"
    Push $R0
    ${If} ${FileExists} "$INSTDIR\runtime\machine-control-windows.exe"
      nsExec::ExecToLog '"$INSTDIR\runtime\machine-control-windows.exe" browser-unregister'
      Pop $R0
      ${If} $R0 <> 0
        Pop $R0
        SetErrorLevel 1
        Abort "Browser registration could not be removed."
      ${EndIf}
      ; Chrome's host exits asynchronously after the provider pipe closes.
      ; Retry only our payload image before the other files are removed.
      ; Never kill Chrome, user apps or appliance/component services.
      StrCpy $R0 0
      ${Do}
        Delete "$INSTDIR\runtime\machine-control-windows.exe"
        ${IfNot} ${FileExists} "$INSTDIR\runtime\machine-control-windows.exe"
          ${ExitDo}
        ${EndIf}
        ${If} $R0 >= 100
          Pop $R0
          SetErrorLevel 1
          Abort "Browser host is still running. Close Chrome and retry uninstall."
        ${EndIf}
        Sleep 100
        IntOp $R0 $R0 + 1
      ${Loop}
    ${EndIf}
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
    RMDir "$INSTDIR\runtime"
    RMDir "$INSTDIR"
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
