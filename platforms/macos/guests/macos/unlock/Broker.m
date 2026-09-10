#import <Security/Security.h>
#import "Session.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/poll.h>
#include <sys/file.h>
#include <signal.h>

#define SOCKET_PATH "/var/run/machine-control-unlock/control.sock"
#define RECEIPT_PATH STATE_DIR "/receipt.plist"
static NSString *epoch;
static NSString *desktopEpoch;
static NSDictionary *lastState;
static NSMutableSet *requests;
static const char *rightName = "org.machine-control.screen-unlock";

static NSDictionary *readPlist(NSString *path) {
    return [NSDictionary dictionaryWithContentsOfURL:[NSURL fileURLWithPath:path] error:NULL];
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
static NSString *installationIssue(NSDictionary *receipt) {
    if (!receipt) return @"unlock_not_installed";
    if (![receipt[@"enabled"] boolValue]) return @"unlock_disabled";
    if (!artifactMatches(@"/Library/Security/SecurityAgentPlugins/MCUnlock.bundle", receipt[@"pluginCDHash"]) ||
        !artifactMatches(@STATE_DIR "/broker", receipt[@"brokerCDHash"])) return @"unlock_artifact_mismatch";
    if (![right("system.login.screensaver") isEqual:receipt[@"installedPolicy"]] ||
        ![right(rightName) isEqual:receipt[@"dedicatedPolicy"]]) return @"unlock_policy_conflict";
    return nil;
}
static void handle(int fd) {
    NSDictionary *request = receiveJSON(fd);
    if (!request) { sendJSON(fd, @{@"errorCode": @"invalid_request"}); return; }
    NSDictionary *receipt = readPlist(@RECEIPT_PATH);
    NSDictionary *state = observe();
    pid_t pid = 0;
    BOOL allowed = peerAllowed(fd, receipt, &pid);
    NSString *issue = installationIssue(receipt);
    NSString *op = request[@"operation"];
    if ([op isEqual:@"status"]) {
        sendJSON(fd, @{@"installation": receipt ? (issue && ![issue isEqual:@"unlock_disabled"] ? @"inconsistent" : @"healthy") : @"missing",
            @"policy": [receipt[@"enabled"] boolValue] ? @"enabled" : @"disabled",
            @"callerEligibility": allowed ? @"allowed" : @"denied",
            @"helperGeneration": epoch, @"helperDesktopGeneration": desktopEpoch,
            @"errorCode": issue ?: (allowed ? @"" : @"unlock_caller_denied")});
        return;
    }
    if (![op isEqual:@"unlock"]) { sendJSON(fd, @{@"errorCode": @"unsupported_operation"}); return; }
    if (!allowed || issue) { sendJSON(fd, @{@"errorCode": issue ?: @"unlock_caller_denied"}); return; }
    NSString *identifier = request[@"requestId"];
    if (![identifier isKindOfClass:NSString.class] || identifier.length < 1 || identifier.length > 128 ||
        ![request[@"helperGeneration"] isEqual:epoch] ||
        ![request[@"helperDesktopGeneration"] isEqual:desktopEpoch]) {
        sendJSON(fd, @{@"errorCode": @"stale_generation"}); return;
    }
    if ([requests containsObject:identifier] || requests.count >= 4096) {
        sendJSON(fd, @{@"errorCode": @"unlock_request_replayed_or_limit"}); return;
    }
    [requests addObject:identifier];
    if (![state[@"locked"] boolValue] || ![state[@"uid"] isEqual:receipt[@"allowedUID"]]) {
        sendJSON(fd, @{@"errorCode": @"unlock_session_unavailable"}); return;
    }
    NSMutableDictionary *grant = [state mutableCopy];
    grant[@"purpose"] = @"screen-unlock";
    grant[@"issued"] = @(monotonicNow()); grant[@"expires"] = @([grant[@"issued"] doubleValue] + 10);
    grant[@"brokerEpoch"] = epoch;
    grant[@"peerPID"] = @(pid);
    NSData *data = [NSPropertyListSerialization dataWithPropertyList:grant format:NSPropertyListBinaryFormat_v1_0 options:0 error:NULL];
    int file = open(GRANT_PATH, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (file < 0) { sendJSON(fd, @{@"errorCode": @"unlock_grant_unavailable"}); return; }
    BOOL written = write(file, data.bytes, data.length) == (ssize_t)data.length && !fsync(file);
    close(file);
    if (!written) { unlink(GRANT_PATH); sendJSON(fd, @{@"errorCode": @"unlock_grant_unavailable"}); return; }
    if (sendJSON(fd, @{@"armed": @YES})) {
        // The same authenticated connection owns this short transaction. EOF,
        // cancellation, timeout, or a session transition revokes remaining authority.
        double deadline = monotonicNow() + 10;
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
        sendJSON(fd, @{@"unlockedObserved": @(unlocked)});
    }
    unlink(GRANT_PATH);
    observe();
}
int main(int argc, char **argv) {
    @autoreleasepool {
        (void)argv;
        if (argc != 1 || geteuid()) return 2;
        struct stat st;
        if (lstat(STATE_DIR, &st) || !S_ISDIR(st.st_mode) || st.st_uid || (st.st_mode & 0077)) return 3;
        int lock = open(STATE_DIR "/broker.lock", O_CREAT | O_RDWR | O_NOFOLLOW, 0600);
        if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) return 4;
        signal(SIGPIPE, SIG_IGN);
        unlink(GRANT_PATH);
        epoch = NSUUID.UUID.UUIDString;
        [@{@"epoch":epoch, @"pid":@(getpid())} writeToFile:@STATE_DIR "/broker.plist" atomically:YES];
        chmod(STATE_DIR "/broker.plist", 0600);
        requests = [NSMutableSet set];
        if (mkdir("/var/run/machine-control-unlock", 0755) && errno != EEXIST) return 5;
        if (lstat("/var/run/machine-control-unlock", &st) || !S_ISDIR(st.st_mode) || st.st_uid || (st.st_mode & 0022)) return 5;
        int server = socket(AF_UNIX, SOCK_STREAM, 0);
        struct sockaddr_un address = {.sun_family = AF_UNIX};
        strlcpy(address.sun_path, SOCKET_PATH, sizeof(address.sun_path));
        unlink(SOCKET_PATH);
        if (bind(server, (struct sockaddr *)&address, sizeof(address)) || chmod(SOCKET_PATH, 0666) || listen(server, 8)) return 6;
        while (YES) { @autoreleasepool {
            observe();
            struct pollfd p = {server, POLLIN, 0};
            if (poll(&p, 1, 100) <= 0) continue;
            int fd = accept(server, NULL, NULL);
            if (fd < 0) continue;
            struct timeval timeout = {2, 0};
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
            handle(fd); close(fd);
        }}
    }
}
