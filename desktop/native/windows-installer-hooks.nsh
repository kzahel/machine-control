; Remove browser registration only when its manifest still names this exact
; installation. Scratch installs must preserve another installation's host.
!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode <> 1
    IfFileExists "$INSTDIR\runtime\machine-control-windows.exe" 0 +2
      nsExec::ExecToLog '"$INSTDIR\runtime\machine-control-windows.exe" browser-unregister'
  ${EndIf}
!macroend

; Startup belongs to an explicit operator preference. Remove only our own
; per-user entry during uninstall; never stop an appliance/component service.
!macro NSIS_HOOK_POSTUNINSTALL
  ${If} $UpdateMode <> 1
    ReadRegStr $R0 HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Machine Control"
    ${If} $R0 == "$INSTDIR\machine-control.exe --background"
    ${OrIf} $R0 == '"$INSTDIR\machine-control.exe" --background'
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Machine Control"
    ${EndIf}
  ${EndIf}
!macroend
