#import <Security/Security.h>
#import "Session.h"
#import "Relock.h"
#import "QuietResume.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/poll.h>
#include <sys/file.h>
#include <signal.h>
#include <math.h>
#include <libproc.h>

#define SOCKET_PATH "/var/run/machine-control-unlock/control.sock"
#define RECEIPT_PATH STATE_DIR "/receipt.plist"
static NSString *epoch;
static NSString *desktopEpoch;
static NSDictionary *lastState;
static NSMutableSet *requests;
static const char *rightName = "org.machine-control.screen-unlock";
static int coveredFD = -1;
static pid_t coveredPID;
static NSDictionary *coveredState;
static double coveredDeadline, heartbeatDeadline;
static BOOL relocking;
static NSString *endReason;
static BOOL paused;
static BOOL pausedSawLock;
static volatile sig_atomic_t stopping;
static BOOL serviceManaged;
static NSString *managedApp;
static NSData *managedAppHash, *managedResidentHash;
static NSDictionary<NSString *, NSData *> *managedPayloadHashes;
#define WATCH_PATH STATE_DIR "/covered-session.plist"
#define PAUSE_PATH STATE_DIR "/locked-use-paused.plist"

static void stopSignal(int value) { (void)value; stopping = 1; }
static BOOL sameSession(NSDictionary *a, NSDictionary *b) {
    return a && b && [a[@"uuid"] isEqual:b[@"uuid"]] &&
        [a[@"boot"] isEqual:b[@"boot"]] && [a[@"uid"] isEqual:b[@"uid"]];
}

static NSDictionary *readPlist(NSString *path) {
    return [NSDictionary dictionaryWithContentsOfURL:[NSURL fileURLWithPath:path] error:NULL];
}
static BOOL persistState(NSString *path, NSDictionary *state) {
    NSData *data = [NSPropertyListSerialization dataWithPropertyList:state
        format:NSPropertyListBinaryFormat_v1_0 options:0 error:NULL];
    NSString *temporary = [path stringByAppendingFormat:@".%@", NSUUID.UUID.UUIDString];
    int fd = open(temporary.fileSystemRepresentation, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (!data || fd < 0) return NO;
    BOOL written = write(fd, data.bytes, data.length) == (ssize_t)data.length && !fsync(fd);
    close(fd);
    if (!written || rename(temporary.fileSystemRepresentation, path.fileSystemRepresentation)) {
        unlink(temporary.fileSystemRepresentation); return NO;
    }
    int directory = open(STATE_DIR, O_RDONLY | O_DIRECTORY);
    BOOL synced = directory >= 0 && !fsync(directory);
    if (directory >= 0) close(directory);
    return synced;
}
static NSDictionary *normalized(NSDictionary *value) {
    NSMutableDictionary *copy = [value mutableCopy];
    [copy removeObjectsForKeys:@[@"created", @"modified"]];
    return copy;
}
static NSDictionary *right(const char *name) {
    CFDictionaryRef value = NULL;
    if (AuthorizationRightGet(name, &value)) return nil;
    return normalized(CFBridgingRelease(value));
}
static BOOL sendJSON(int fd, NSDictionary *value) {
    NSMutableData *data = [[NSJSONSerialization dataWithJSONObject:value options:0 error:NULL] mutableCopy];
    [data appendBytes:"\n" length:1];
    const char *bytes = data.bytes;
    NSUInteger left = data.length;
    while (left) { ssize_t n = write(fd, bytes, left); if (n <= 0) return NO; bytes += n; left -= n; }
    return YES;
}
static NSDictionary *receiveJSON(int fd) {
    NSMutableData *data = [NSMutableData data];
    char byte;
    double deadline = monotonicNow() + 2;
    while (data.length < 4096 && monotonicNow() < deadline) {
        struct pollfd p = {fd, POLLIN, 0};
        if (poll(&p, 1, 100) <= 0) continue;
        if (read(fd, &byte, 1) != 1) return nil;
        if (byte == '\n') {
            id value = [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
            return [value isKindOfClass:NSDictionary.class] ? value : nil;
        }
        [data appendBytes:&byte length:1];
    }
    return nil;
}
static NSDictionary *observe(void) {
    NSDictionary *state = sessionState() ?: @{@"desktopState": @"unknown"};
    if (![state isEqual:lastState] || [state[@"desktopState"] isEqual:@"unknown"]) {
        desktopEpoch = NSUUID.UUID.UUIDString;
        lastState = state;
        unlink(GRANT_PATH);
    }
    return state;
}
static BOOL peerAllowed(int fd, NSDictionary *receipt, pid_t *pid) {
    uid_t uid; gid_t gid;
    socklen_t size = sizeof(*pid);
    if (getpeereid(fd, &uid, &gid) ||
        getsockopt(fd, SOL_LOCAL, LOCAL_PEERPID, pid, &size) ||
        uid != [receipt[@"allowedUID"] unsignedIntValue] || *pid <= 0) return NO;
    SecCodeRef code = NULL;
    NSDictionary *attributes = @{(__bridge NSString *)kSecGuestAttributePid: @(*pid)};
    if (SecCodeCopyGuestWithAttributes(NULL, (__bridge CFDictionaryRef)attributes,
                                     kSecCSDefaultFlags, &code)) return NO;
    CFDictionaryRef info = NULL;
    OSStatus result = SecCodeCheckValidity(code, kSecCSStrictValidate, NULL);
    if (!result) result = SecCodeCopySigningInformation(code, kSecCSSigningInformation, &info);
    CFRelease(code);
    NSDictionary *signing = CFBridgingRelease(info);
    NSData *digest = signing[(__bridge NSString *)kSecCodeInfoUnique];
    return !result && digest && [digest isEqual:receipt[@"residentCDHash"]];
}
static BOOL artifactMatches(NSString *path, NSData *expected) {
    SecStaticCodeRef code = NULL;
    if (!expected || SecStaticCodeCreateWithPath((__bridge CFURLRef)[NSURL fileURLWithPath:path], kSecCSDefaultFlags, &code)) return NO;
    CFDictionaryRef info = NULL;
    OSStatus result = SecStaticCodeCheckValidity(code, kSecCSStrictValidate, NULL);
    if (!result) result = SecCodeCopySigningInformation(code, kSecCSSigningInformation, &info);
    CFRelease(code);
    NSDictionary *signing = CFBridgingRelease(info);
    return !result && [signing[(__bridge NSString *)kSecCodeInfoUnique] isEqual:expected];
}
static NSData *codeHash(NSString *path) {
    SecStaticCodeRef code = NULL;
    if (SecStaticCodeCreateWithPath((__bridge CFURLRef)[NSURL fileURLWithPath:path], 0, &code)) return nil;
    CFDictionaryRef info = NULL;
    OSStatus result = SecStaticCodeCheckValidity(code, kSecCSStrictValidate | kSecCSCheckNestedCode, NULL);
    if (!result) result = SecCodeCopySigningInformation(code, kSecCSSigningInformation, &info);
    CFRelease(code);
    NSDictionary *signing = CFBridgingRelease(info);
    return result ? nil : signing[(__bridge NSString *)kSecCodeInfoUnique];
}
static NSString *managedApplication(void) {
    char executable[PROC_PIDPATHINFO_MAXSIZE];
    if (proc_pidpath(getpid(), executable, sizeof(executable)) <= 0) return nil;
    NSString *path = [@(executable) stringByResolvingSymlinksInPath];
    NSString *suffix = @"/Contents/Resources/unlock/mc-unlock-broker";
    if (![path hasSuffix:suffix]) return nil;
    NSString *app = [path substringToIndex:path.length - suffix.length];
    return [app hasSuffix:@".app"] && codeHash(app) ? app : nil;
}
// Closed setup/removal API for the signed operator in the OS-approved bundle.
// UID and every executable/argument are derived here, never supplied by JSON.
static BOOL managePermission(int fd, NSDictionary *request, NSDictionary *receipt) {
    NSString *operation = request[@"operation"];
    if (![operation isEqual:@"permission.prepare"] && ![operation isEqual:@"permission.remove"]) return NO;
    uid_t uid; gid_t gid; pid_t pid = 0;
    NSDictionary *console = sessionState();
    NSString *resident = [managedApp stringByAppendingPathComponent:@"Contents/MacOS/macui"];
    NSData *hash = managedResidentHash;
    BOOL allowed = serviceManaged && hash && request.count == 1 &&
        !getpeereid(fd, &uid, &gid) && uid > 0 &&
        [console[@"desktopState"] isEqual:@"unlocked"] && [console[@"uid"] unsignedIntValue] == uid &&
        peerAllowed(fd, @{@"allowedUID":@(uid), @"residentCDHash":hash}, &pid);
    if (!allowed || coveredState || (receipt && ![receipt[@"management"] isEqual:@"service_managed"])) {
        sendJSON(fd, @{@"errorCode":coveredState ? @"covered_session_busy" : @"helper_permission_denied"}); return YES;
    }
    NSString *installer = [managedApp stringByAppendingPathComponent:@"Contents/Resources/unlock/mc-unlock-install"];
    if (![codeHash(managedApp) isEqual:managedAppHash] || ![codeHash(installer) isEqual:managedPayloadHashes[@"mc-unlock-install"]]) {
        sendJSON(fd, @{@"errorCode":@"helper_bundle_invalid"}); return YES;
    }
    // Execute only a verified copy in root-private storage. The approved app
    // can live in a user-writable directory; a check followed by exec there
    // would permit replacement between validation and process launch.
    NSString *stage = [@STATE_DIR stringByAppendingPathComponent:[@"permission-" stringByAppendingString:NSUUID.UUID.UUIDString]];
    NSFileManager *files = NSFileManager.defaultManager;
    BOOL copied = [files createDirectoryAtPath:stage withIntermediateDirectories:NO
        attributes:@{NSFilePosixPermissions:@0700} error:NULL];
    for (NSString *name in managedPayloadHashes) {
        NSString *source = [[installer stringByDeletingLastPathComponent] stringByAppendingPathComponent:name];
        NSString *destination = [stage stringByAppendingPathComponent:name];
        copied = copied && [files copyItemAtPath:source toPath:destination error:NULL] &&
            [codeHash(destination) isEqual:managedPayloadHashes[name]];
    }
    copied = copied && [codeHash(managedApp) isEqual:managedAppHash];
    if (!copied) {
        [files removeItemAtPath:stage error:NULL];
        sendJSON(fd, @{@"errorCode":@"helper_bundle_invalid"}); return YES;
    }
    NSTask *task = [NSTask new];
    task.executableURL = [NSURL fileURLWithPath:[stage stringByAppendingPathComponent:@"mc-unlock-install"]];
    task.arguments = [operation isEqual:@"permission.prepare"]
        ? @[@"install", @"--locked-use-uid", [NSString stringWithFormat:@"%u",uid], resident, @"--service-managed"]
        : @[@"uninstall", @"--service-managed"];
    task.standardInput = NSFileHandle.fileHandleWithNullDevice;
    task.standardOutput = NSFileHandle.fileHandleWithNullDevice;
    task.standardError = NSFileHandle.fileHandleWithNullDevice;
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        [files removeItemAtPath:stage error:NULL];
        sendJSON(fd, @{@"errorCode":@"helper_setup_failed"}); return YES;
    }
    double deadline = monotonicNow() + 20;
    while (task.running && monotonicNow() < deadline) usleep(10000);
    BOOL timedOut = task.running;
    if (timedOut) {
        [task terminate];
        double cleanupDeadline = monotonicNow() + 1;
        while (task.running && monotonicNow() < cleanupDeadline) usleep(10000);
        if (task.running) kill(task.processIdentifier, SIGKILL);
    }
    [task waitUntilExit];
    [files removeItemAtPath:stage error:NULL];
    if (timedOut) { sendJSON(fd, @{@"errorCode":@"helper_setup_timeout"}); return YES; }
    sendJSON(fd, task.terminationStatus == 0 ? @{@"completed":@YES} : @{@"errorCode":@"helper_setup_failed"});
    return YES;
}
static NSString *installationIssue(NSDictionary *receipt) {
    if (!receipt) return @"unlock_not_installed";
    if (![receipt[@"enabled"] boolValue]) return @"unlock_disabled";
    if (!artifactMatches(@"/Library/Security/SecurityAgentPlugins/MCUnlock.bundle", receipt[@"pluginCDHash"]) ||
        !artifactMatches(@STATE_DIR "/broker", receipt[@"brokerCDHash"])) return @"unlock_artifact_mismatch";
    if (![right("system.login.screensaver") isEqual:receipt[@"installedPolicy"]] ||
        ![right(rightName) isEqual:receipt[@"dedicatedPolicy"]]) return @"unlock_policy_conflict";
    return nil;
}
static void requestRelock(NSString *reason) {
    unlink(GRANT_PATH);
    relocking = YES;
    endReason = reason;
    // Faults require recovery. Physical takeover instead permits locked quiet
    // resumption; the marker survives resident restarts and cannot be cleared
    // through the ordinary agent control socket.
    if (![reason isEqual:@"completed"] && ![reason isEqual:@"duration_expired"]) {
        paused = YES; pausedSawLock = NO;
        NSMutableDictionary *marker = [coveredState mutableCopy];
        marker[@"pauseReason"] = reason; marker[@"pausedUptime"] = @(monotonicNow());
        persistState(@PAUSE_PATH, marker);
    }
    if (sameSession(sessionState(), coveredState)) lockConsole();
}
static void clearPause(void) {
    paused = NO; pausedSawLock = NO; unlink(PAUSE_PATH); unlink(WATCH_PATH);
}
static void finishCovered(BOOL locked) {
    if (paused && locked) pausedSawLock = YES;
    if (coveredFD >= 0) {
        sendJSON(coveredFD, @{@"ended":@YES, @"reason":endReason ?: @"session_changed", @"lockObserved":@(locked)});
        close(coveredFD);
    }
    coveredFD = -1; coveredState = nil; relocking = NO;
    // If a pause could not be written, retain the active marker so restart
    // fails closed instead of silently forgetting unexpected termination.
    if (!paused || readPlist(@PAUSE_PATH)) unlink(WATCH_PATH);
}
static void tickCovered(void) {
    NSDictionary *current = sessionState();
    if (coveredState) {
        if (current && !sameSession(current, coveredState)) { finishCovered(NO); return; }
        if (relocking) {
            if ([current[@"locked"] boolValue]) { finishCovered(YES); return; }
            if (sameSession(current, coveredState)) lockConsole(); return;
        }
        if (stopping || kill(coveredPID, 0) || monotonicNow() >= coveredDeadline ||
            monotonicNow() >= heartbeatDeadline || installationIssue(readPlist(@RECEIPT_PATH))) {
            requestRelock(stopping ? @"helper_stopping" : monotonicNow() >= coveredDeadline ? @"duration_expired" : @"watchdog_interrupted"); return;
        }
        struct pollfd p = {coveredFD, POLLIN | POLLHUP, 0};
        if (poll(&p, 1, 0) > 0) {
            NSDictionary *message = receiveJSON(coveredFD);
            if ([message[@"operation"] isEqual:@"heartbeat"] && message.count == 1) {
                heartbeatDeadline = monotonicNow() + 5;
            } else {
                requestRelock([message[@"operation"] isEqual:@"complete"] ? @"completed" :
                    [message[@"reason"] isEqual:@"physical_presence"] ? @"physical_presence" : @"owner_disconnected");
                return;
            }
        }
        if ([current[@"locked"] boolValue]) { requestRelock(@"desktop_locked"); return; }
    }
    if (paused && !coveredState) {
        NSDictionary *initial = readPlist(@PAUSE_PATH);
        if (sameSession(initial, current) && [current[@"locked"] boolValue]) pausedSawLock = YES;
        NSString *reason = initial[@"pauseReason"];
        if (resumablePause(reason) && sameSession(initial, current)) {
            if (pausedSawLock && [current[@"desktopState"] isEqual:@"unlocked"] &&
                ![reason isEqual:@"local_use_episode"]) {
                NSMutableDictionary *marker = [initial mutableCopy];
                marker[@"pauseReason"] = @"local_use_episode";
                persistState(@PAUSE_PATH, marker);
            }
            if (!installationIssue(readPlist(@RECEIPT_PATH)) &&
                quietResumeEligible(YES, [current[@"locked"] boolValue],
                    [initial[@"pausedUptime"] isKindOfClass:NSNumber.class] ? [initial[@"pausedUptime"] doubleValue] : NAN,
                    monotonicNow(), physicalIdleSeconds())) clearPause();
        } else if ((pausedSawLock && sameSession(initial, current) &&
                    [current[@"desktopState"] isEqual:@"unlocked"]) ||
                   (initial && current && !sameSession(initial, current))) {
            // Fault recovery retains its previous independently observed unlock
            // requirement. A changed console must obtain fresh ordinary access.
            clearPause();
        }
    }
}
static BOOL handle(int fd) {
    NSDictionary *request = receiveJSON(fd);
    if (!request) { sendJSON(fd, @{@"errorCode": @"invalid_request"}); return NO; }
    NSDictionary *receipt = readPlist(@RECEIPT_PATH);
    if (managePermission(fd, request, receipt)) return NO;
    NSDictionary *state = observe();
    pid_t pid = 0;
    BOOL allowed = peerAllowed(fd, receipt, &pid);
    NSString *issue = installationIssue(receipt);
    NSString *op = request[@"operation"];
    NSString *profile = receipt[@"profile"] ?: @"appliance";
    if ([op isEqual:@"status"]) {
        if (request.count != 1) { sendJSON(fd, @{@"errorCode":@"invalid_request"}); return NO; }
        sendJSON(fd, @{@"installation": receipt ? (issue && ![issue isEqual:@"unlock_disabled"] ? @"inconsistent" : @"healthy") : @"missing",
            @"policy": [receipt[@"enabled"] boolValue] ? @"enabled" : @"disabled",
            @"callerEligibility": allowed ? @"allowed" : @"denied",
            @"helperGeneration": epoch, @"helperDesktopGeneration": desktopEpoch,
            @"profile":profile, @"lockedUsePaused":@(paused), @"relockAvailable":@(lockConsoleAvailable()),
            @"coveredSession":@(coveredState != nil),
            @"lockedUsePauseReason":paused ? (readPlist(@PAUSE_PATH)[@"pauseReason"] ?: @"safety_fault") : @"",
            @"errorCode": issue ?: (allowed ? @"" : @"unlock_caller_denied")});
        return NO;
    }
    BOOL covered = [op isEqual:@"covered_unlock"];
    BOOL resume = [op isEqual:@"covered.resume"];
    NSMutableSet *keys = [NSMutableSet setWithArray:@[@"operation", @"requestId", @"helperGeneration", @"helperDesktopGeneration"]];
    if (covered) [keys addObjectsFromArray:@[@"durationSeconds", @"coversReady", @"controlDeadlineUptime"]];
    if (![[NSSet setWithArray:request.allKeys] isSubsetOfSet:keys]) {
        sendJSON(fd, @{@"errorCode":@"invalid_request"}); return NO;
    }
    if (![op isEqual:@"unlock"] && !covered && !resume) { sendJSON(fd, @{@"errorCode": @"unsupported_operation"}); return NO; }
    if (!allowed || issue) { sendJSON(fd, @{@"errorCode": issue ?: @"unlock_caller_denied"}); return NO; }
    if (coveredState) { sendJSON(fd, @{@"errorCode": @"covered_session_busy"}); return NO; }
    if (((covered || resume) && ![profile isEqual:@"locked_use"]) || (!covered && !resume && ![profile isEqual:@"appliance"])) {
        sendJSON(fd, @{@"errorCode": @"unlock_profile_mismatch"}); return NO;
    }
    if (resume) {
        NSString *requestID = request[@"requestId"];
        if (request.count != 4 || ![requestID isKindOfClass:NSString.class] ||
            requestID.length < 1 || requestID.length > 128 || requests.count >= 4096 ||
            [requests containsObject:requestID]) {
            sendJSON(fd, @{@"errorCode":@"invalid_request"}); return NO;
        }
        [requests addObject:requestID];
        NSDictionary *marker = readPlist(@PAUSE_PATH);
        if (![request[@"helperGeneration"] isEqual:epoch] ||
            ![request[@"helperDesktopGeneration"] isEqual:desktopEpoch] ||
            (paused && (!resumablePause(marker[@"pauseReason"]) || !sameSession(marker, state)))) {
            sendJSON(fd, @{@"errorCode":@"pause_recovery_required"}); return NO;
        }
        clearPause(); sendJSON(fd, @{@"resumed":@YES}); return NO;
    }
    id duration = request[@"durationSeconds"];
    id controlDeadline = request[@"controlDeadlineUptime"];
    double remaining = [controlDeadline isKindOfClass:NSNumber.class] ?
        [controlDeadline doubleValue] - NSProcessInfo.processInfo.systemUptime : -1;
    if (covered && (paused || !lockConsoleAvailable() ||
        ![duration isKindOfClass:NSNumber.class] || [duration doubleValue] < 1 || [duration doubleValue] > 900 ||
        CFGetTypeID((__bridge CFTypeRef)duration) == CFBooleanGetTypeID() || [duration doubleValue] != [duration integerValue] ||
        !isfinite(remaining) || remaining <= 0 || remaining > 900 || remaining > [duration doubleValue] + 1 ||
        ![request[@"coversReady"] isEqual:@YES])) {
        sendJSON(fd, @{@"errorCode":paused ? @"locked_use_paused" : @"covered_session_unavailable"}); return NO;
    }
    NSString *identifier = request[@"requestId"];
    if (![identifier isKindOfClass:NSString.class] || identifier.length < 1 || identifier.length > 128 ||
        ![request[@"helperGeneration"] isEqual:epoch] ||
        ![request[@"helperDesktopGeneration"] isEqual:desktopEpoch]) {
        sendJSON(fd, @{@"errorCode": @"stale_generation"}); return NO;
    }
    if ([requests containsObject:identifier] || requests.count >= 4096) {
        sendJSON(fd, @{@"errorCode": @"unlock_request_replayed_or_limit"}); return NO;
    }
    [requests addObject:identifier];
    if (![state[@"locked"] boolValue] || ![state[@"uid"] isEqual:receipt[@"allowedUID"]]) {
        sendJSON(fd, @{@"errorCode": @"unlock_session_unavailable"}); return NO;
    }
    NSMutableDictionary *grant = [state mutableCopy];
    grant[@"purpose"] = @"screen-unlock";
    grant[@"issued"] = @(monotonicNow()); grant[@"expires"] = @([grant[@"issued"] doubleValue] + (covered ? MIN(10, remaining) : 10));
    grant[@"brokerEpoch"] = epoch;
    grant[@"peerPID"] = @(pid);
    NSData *data = [NSPropertyListSerialization dataWithPropertyList:grant format:NSPropertyListBinaryFormat_v1_0 options:0 error:NULL];
    int file = open(GRANT_PATH, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (file < 0) { sendJSON(fd, @{@"errorCode": @"unlock_grant_unavailable"}); return NO; }
    BOOL written = write(file, data.bytes, data.length) == (ssize_t)data.length && !fsync(file);
    close(file);
    if (!written) { unlink(GRANT_PATH); sendJSON(fd, @{@"errorCode": @"unlock_grant_unavailable"}); return NO; }
    if (covered) {
        // Durable before authorization is acknowledged; daemon restart must
        // relock even if the previous process died during the unlock window.
        coveredState = state; coveredPID = pid;
        if (!persistState(@WATCH_PATH, state)) {
            unlink(GRANT_PATH); coveredState = nil;
            sendJSON(fd, @{ @"errorCode": @"covered_watchdog_state_unavailable" }); return NO;
        }
    }
    if (sendJSON(fd, @{@"armed": @YES})) {
        // The same authenticated connection owns this short transaction. EOF,
        // cancellation, timeout, or a session transition revokes remaining authority.
        double deadline = monotonicNow() + (covered ? MIN(10, remaining) : 10);
        BOOL unlocked = NO;
        while (monotonicNow() < deadline) {
            NSDictionary *current = sessionState();
            if (![current[@"uuid"] isEqual:state[@"uuid"]] ||
                ![current[@"boot"] isEqual:state[@"boot"]] ||
                ![current[@"uid"] isEqual:state[@"uid"]]) break;
            if (![current[@"locked"] boolValue]) { unlocked = YES; break; }
            if (kill(pid, 0) || installationIssue(readPlist(@RECEIPT_PATH))) break;
            struct pollfd p = {fd, POLLIN | POLLHUP, 0};
            if (poll(&p, 1, 100) > 0) break;
        }
        unlink(GRANT_PATH);
        if (covered) {
            coveredFD = fd;
            coveredDeadline = monotonicNow() + MAX(0, [controlDeadline doubleValue] - NSProcessInfo.processInfo.systemUptime);
            heartbeatDeadline = monotonicNow() + 5;
            if (!unlocked) requestRelock(@"unlock_not_observed");
            if (!sendJSON(fd, @{@"unlockedObserved": @(unlocked)})) requestRelock(@"owner_disconnected");
            observe(); return YES;
        }
        sendJSON(fd, @{@"unlockedObserved": @(unlocked)});
    }
    unlink(GRANT_PATH);
    observe();
    if (covered) { coveredFD = fd; requestRelock(@"owner_disconnected"); return YES; }
    return NO;
}
int main(int argc, char **argv) {
    @autoreleasepool {
        serviceManaged = argc == 2 && !strcmp(argv[1], "--service-managed");
        if ((argc != 1 && !serviceManaged) || geteuid()) return 2;
        if (serviceManaged) {
            managedApp = managedApplication();
            if (!managedApp) return 3;
            managedAppHash = codeHash(managedApp);
            managedResidentHash = codeHash([managedApp stringByAppendingPathComponent:@"Contents/MacOS/macui"]);
            NSMutableDictionary *payload = [NSMutableDictionary dictionary];
            for (NSString *name in @[@"mc-unlock-install", @"mc-unlock-broker", @"MCUnlock.bundle"]) {
                NSData *hash = codeHash([[managedApp stringByAppendingPathComponent:@"Contents/Resources/unlock"] stringByAppendingPathComponent:name]);
                if (!hash) return 3;
                payload[name] = hash;
            }
            managedPayloadHashes = [payload copy];
            if (!managedAppHash || !managedResidentHash) return 3;
            if (mkdir(STATE_DIR, 0700) && errno != EEXIST) return 3;
        }
        struct stat st;
        if (lstat(STATE_DIR, &st) || !S_ISDIR(st.st_mode) || st.st_uid || (st.st_mode & 0077)) return 3;
        int lock = open(STATE_DIR "/broker.lock", O_CREAT | O_RDWR | O_NOFOLLOW, 0600);
        if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) return 4;
        signal(SIGPIPE, SIG_IGN);
        signal(SIGTERM, stopSignal); signal(SIGINT, stopSignal);
        unlink(GRANT_PATH);
        epoch = NSUUID.UUID.UUIDString;
        [@{@"epoch":epoch, @"pid":@(getpid())} writeToFile:@STATE_DIR "/broker.plist" atomically:YES];
        chmod(STATE_DIR "/broker.plist", 0600);
        requests = [NSMutableSet set];
        paused = readPlist(@PAUSE_PATH) != nil;
        coveredState = readPlist(@WATCH_PATH);
        if (coveredState) requestRelock(@"helper_restarted");
        if (mkdir("/var/run/machine-control-unlock", 0755) && errno != EEXIST) return 5;
        if (lstat("/var/run/machine-control-unlock", &st) || !S_ISDIR(st.st_mode) || st.st_uid || (st.st_mode & 0022)) return 5;
        int server = socket(AF_UNIX, SOCK_STREAM, 0);
        struct sockaddr_un address = {.sun_family = AF_UNIX};
        strlcpy(address.sun_path, SOCKET_PATH, sizeof(address.sun_path));
        unlink(SOCKET_PATH);
        if (bind(server, (struct sockaddr *)&address, sizeof(address)) || chmod(SOCKET_PATH, 0666) || listen(server, 8)) return 6;
        while (YES) { @autoreleasepool {
            tickCovered();
            if (stopping && !coveredState) break;
            observe();
            struct pollfd p = {server, POLLIN, 0};
            if (poll(&p, 1, 100) <= 0) continue;
            int fd = accept(server, NULL, NULL);
            if (fd < 0) continue;
            struct timeval timeout = {2, 0};
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
            if (!handle(fd)) close(fd);
        }}
    }
}
