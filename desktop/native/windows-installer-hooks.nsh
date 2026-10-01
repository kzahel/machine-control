; Startup belongs to an explicit operator preference. Remove only our own
; per-user entry during uninstall; never stop an appliance/component service.
!macro NSIS_HOOK_POSTUNINSTALL
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Machine Control"
!macroend
