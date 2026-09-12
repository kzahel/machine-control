// Native, statically linked elevation entry. No payload DLL or script is loaded
// before elevation and catalog verification. Only Windows system imports.
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "unlock_setup_script.h"

static int administrator(void) {
    SID_IDENTIFIER_AUTHORITY authority = SECURITY_NT_AUTHORITY;
    PSID sid = NULL;
    BOOL member = FALSE;
    if (AllocateAndInitializeSid(&authority, 2, SECURITY_BUILTIN_DOMAIN_RID,
        DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &sid)) {
        CheckTokenMembership(NULL, sid, &member);
        FreeSid(sid);
    }
    return member != FALSE;
}

// Quote one argv value according to CommandLineToArgvW backslash rules.
static void argument(wchar_t *out, size_t size, const wchar_t *value) {
    wcscat_s(out, size, out[0] ? L" \"" : L"\"");
    size_t slashes = 0;
    for (const wchar_t *p = value;; ++p) {
        if (*p == L'\\') { ++slashes; continue; }
        size_t copies = (*p == L'"' || *p == 0) ? slashes * 2 : slashes;
        while (copies--) wcscat_s(out, size, L"\\");
        slashes = 0;
        if (*p == L'"') wcscat_s(out, size, L"\\");
        if (*p == 0) break;
        wchar_t letter[2] = {*p, 0};
        wcscat_s(out, size, letter);
    }
    wcscat_s(out, size, L"\"");
}

static void environment(wchar_t *block, size_t *used, const wchar_t *key, const wchar_t *value) {
    int written = swprintf_s(block + *used, 65536 - *used, L"%s=%s", key, value);
    if (written < 0) ExitProcess(2);
    *used += (size_t)written + 1;
    block[*used] = 0;
}

int wmain(int argc, wchar_t **argv) {
    SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (argc < 2 || argc > 5) {
        fwprintf(stderr, L"Usage: unlock-setup Install|Arm|Revoke|Uninstall [instance] [proposal|-] [--allow-unsigned]\n");
        return 2;
    }
    for (int i = 1; i < argc; ++i) if (wcslen(argv[i]) > 4096) return 2;
    wchar_t self[32768], windows[32768], system[32768];
    if (!GetModuleFileNameW(NULL, self, 32768) || !GetWindowsDirectoryW(windows, 32768) ||
        !GetSystemDirectoryW(system, 32768)) return 2;
    if (!administrator()) {
        wchar_t parameters[32768] = L"";
        for (int i = 1; i < argc; ++i) argument(parameters, 32768, argv[i]);
        SHELLEXECUTEINFOW info = {0};
        info.cbSize = sizeof(info); info.fMask = SEE_MASK_NOCLOSEPROCESS;
        info.lpVerb = L"runas"; info.lpFile = self; info.lpParameters = parameters;
        info.lpDirectory = system; info.nShow = SW_SHOWNORMAL;
        if (!ShellExecuteExW(&info)) return (int)GetLastError();
        WaitForSingleObject(info.hProcess, INFINITE);
        DWORD code = 1; GetExitCodeProcess(info.hProcess, &code); CloseHandle(info.hProcess);
        return (int)code;
    }
    // Do not carry caller-controlled CLR startup hooks, PowerShell module paths,
    // PATH entries or profile settings across the elevation boundary.
    wchar_t *env = calloc(65536, sizeof(wchar_t));
    wchar_t *command = calloc(32768, sizeof(wchar_t));
    if (!env || !command) return 2;
    wchar_t powershell[32768], modules[32768], temp[32768];
    swprintf_s(powershell, 32768, L"%s\\WindowsPowerShell\\v1.0\\powershell.exe", system);
    swprintf_s(modules, 32768, L"%s\\WindowsPowerShell\\v1.0\\Modules", system);
    swprintf_s(temp, 32768, L"%s\\Temp", windows);
    size_t used = 0;
    environment(env, &used, L"MC_UNLOCK_ACTION", argv[1]);
    environment(env, &used, L"MC_UNLOCK_DEVELOPMENT", argc == 5 ? argv[4] : L"");
    environment(env, &used, L"MC_UNLOCK_INSTANCE", argc >= 3 ? argv[2] : L"default");
    environment(env, &used, L"MC_UNLOCK_PROPOSAL", argc >= 4 ? argv[3] : L"");
    environment(env, &used, L"MC_UNLOCK_SELF", self);
    environment(env, &used, L"PATH", system);
    environment(env, &used, L"PSModulePath", modules);
    environment(env, &used, L"SystemRoot", windows);
    environment(env, &used, L"TEMP", temp);
    environment(env, &used, L"TMP", temp);
    environment(env, &used, L"windir", windows);
    argument(command, 32768, powershell);
    wcscat_s(command, 32768, L" -NoLogo -NoProfile -NonInteractive -EncodedCommand ");
    wcscat_s(command, 32768, MC_UNLOCK_SCRIPT);
    STARTUPINFOW start = {0}; start.cb = sizeof(start);
    PROCESS_INFORMATION process = {0};
    if (!CreateProcessW(powershell, command, NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT,
            env, system, &start, &process)) { free(env); free(command); return (int)GetLastError(); }
    CloseHandle(process.hThread); free(env); free(command);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1; GetExitCodeProcess(process.hProcess, &code); CloseHandle(process.hProcess);
    return (int)code;
}
