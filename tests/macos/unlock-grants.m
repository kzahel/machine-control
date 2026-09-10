// Target-only root conformance. This tests the production grant validator in
// an isolated directory; it never modifies authorization policy or unlocks UI.
#define STATE_DIR "/var/db/machine-control-unlock-conformance"
#import "../../platforms/macos/guests/macos/unlock/Session.h"
#include <sys/wait.h>
static void require(BOOL pass, const char *name) {
    if (!pass) { fprintf(stderr, "FAIL:%s\n", name); exit(1); }
    printf("PASS:%s\n", name);
}
static NSMutableDictionary *grant(void) {
    NSMutableDictionary *value = [sessionState() mutableCopy];
    value[@"purpose"] = @"screen-unlock";
    value[@"issued"] = @(monotonicNow()); value[@"expires"] = @([value[@"issued"] doubleValue] + 10);
    value[@"brokerEpoch"] = @"test-epoch"; value[@"peerPID"] = @(getpid());
    return value;
}
static void writeGrant(NSDictionary *value) {
    unlink(GRANT_PATH);
    [value writeToFile:@GRANT_PATH atomically:YES]; chmod(GRANT_PATH, 0600);
}
int main(void) { @autoreleasepool {
    require(geteuid() == 0, "target-root");
    require([sessionState()[@"locked"] boolValue], "existing-locked-session");
    require(mkdir(STATE_DIR, 0700) == 0, "exclusive-test-directory");
    [@{@"epoch":@"test-epoch", @"pid":@(getpid())} writeToFile:@STATE_DIR "/broker.plist" atomically:YES];
    [@{@"enabled":@YES} writeToFile:@STATE_DIR "/receipt.plist" atomically:YES];
    require(!consumeGrant(), "missing");
    writeGrant(grant()); require(consumeGrant(), "valid"); require(!consumeGrant(), "single-use");
    for (NSString *field in @[@"uuid", @"uid", @"boot", @"purpose", @"brokerEpoch", @"peerPID"]) {
        NSMutableDictionary *value = grant(); value[field] = [@[@"uid", @"boot", @"peerPID"] containsObject:field] ? @0 : @"wrong";
        writeGrant(value); require(!consumeGrant(), field.UTF8String);
    }
    NSMutableDictionary *value = grant(); value[@"issued"] = @(monotonicNow() - 20); value[@"expires"] = @(monotonicNow() - 10);
    writeGrant(value); require(!consumeGrant(), "expired");
    value = grant(); value[@"expires"] = @(monotonicNow() + 120); writeGrant(value); require(!consumeGrant(), "excessive-ttl");
    value = grant(); value[@"issued"] = @(monotonicNow() + 5); writeGrant(value); require(!consumeGrant(), "future-issued");
    writeGrant(grant()); chmod(GRANT_PATH, 0644); require(!consumeGrant(), "unsafe-permissions");
    unlink(GRANT_PATH); symlink("receipt.plist", GRANT_PATH); require(!consumeGrant(), "symlink"); unlink(GRANT_PATH);
    writeGrant(grant()); link(GRANT_PATH, STATE_DIR "/alias"); require(!consumeGrant(), "hardlink"); unlink(STATE_DIR "/alias");
    writeGrant(grant()); [@{@"enabled":@NO} writeToFile:@STATE_DIR "/receipt.plist" atomically:YES]; require(!consumeGrant(), "disabled");
    [@{@"enabled":@YES} writeToFile:@STATE_DIR "/receipt.plist" atomically:YES];
    writeGrant(grant());
    pid_t children[8];
    for (int i=0; i<8; i++) { children[i] = fork(); if (!children[i]) _exit(consumeGrant() ? 42 : 0); }
    int allowed = 0;
    for (int i=0; i<8; i++) { int status; waitpid(children[i], &status, 0); if (WIFEXITED(status) && WEXITSTATUS(status)==42) allowed++; }
    require(allowed == 1, "concurrent-single-consumer");
    require([sessionState()[@"locked"] boolValue], "validator-does-not-unlock-desktop");
    require([[NSFileManager defaultManager] removeItemAtPath:@STATE_DIR error:NULL], "cleanup");
    return 0;
}}
