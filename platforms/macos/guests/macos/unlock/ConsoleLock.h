#import "Session.h"
#import "Relock.h"
#include <pwd.h>
#include <grp.h>

#define CONSOLE_LOCK_PATH "/Library/PrivilegedHelperTools/org.machine-control.console-lock"

static BOOL consoleLockIdentity(NSDictionary *current, NSString *uuid, NSString *boot, NSString *uid) {
    return current && [current[@"uuid"] isKindOfClass:NSString.class] &&
        [current[@"boot"] isKindOfClass:NSNumber.class] && [current[@"boot"] longLongValue] > 0 &&
        [current[@"uid"] isKindOfClass:NSNumber.class] && [current[@"uid"] unsignedIntValue] > 0 &&
        [current[@"uuid"] isEqual:uuid] && [[current[@"boot"] stringValue] isEqual:boot] &&
        [[current[@"uid"] stringValue] isEqual:uid];
}

// A non-setuid copy of the broker has one unprivileged entry point: lock the
// original, current console. Root enters its GUI bootstrap, then this entry
// irrevocably drops credentials and re-execs the fixed root-owned file. No
// command, executable path, environment or alternative target is accepted.
static int runConsoleLock(int argc, char **argv) {
    if (argc != 5 || strcmp(argv[1], "--lock-console") || strlen(argv[2]) > 128 ||
        strlen(argv[3]) > 20 || strlen(argv[4]) > 10) return 2;
    NSString *uuid = @(argv[2]), *boot = @(argv[3]), *user = @(argv[4]);
    NSDictionary *initial = sessionState();
    if (!consoleLockIdentity(initial, uuid, boot, user)) return 3;
    uid_t uid = [initial[@"uid"] unsignedIntValue];
    if (geteuid() == 0) {
        struct passwd account, *found = NULL; char buffer[16384];
        if (getpwuid_r(uid, &account, buffer, sizeof(buffer), &found) || !found || account.pw_uid != uid ||
            setgroups(0, NULL) || setgid(account.pw_gid) || setuid(uid) ||
            getuid() != uid || geteuid() != uid || setuid(0) == 0) return 4;
        char *args[] = {CONSOLE_LOCK_PATH, "--lock-console", argv[2], argv[3], argv[4], NULL};
        char *environment[] = {"PATH=/usr/bin:/bin:/usr/sbin:/sbin", "LANG=C", NULL};
        execve(CONSOLE_LOCK_PATH, args, environment); return 5;
    }
    if (getuid() != uid || geteuid() != uid || !lockConsoleAvailable()) return 4;
    if (![initial[@"locked"] boolValue]) lockConsole();
    double deadline = monotonicNow() + 2;
    do {
        NSDictionary *current = sessionState();
        if (!consoleLockIdentity(current, uuid, boot, user)) return 3;
        if ([current[@"locked"] boolValue]) { puts("{\"lockedObserved\":true}"); return 0; }
        usleep(20000);
    } while (monotonicNow() < deadline);
    puts("{\"lockedObserved\":false}"); return 6;
}
