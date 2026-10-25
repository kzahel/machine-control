#import "../../platforms/macos/guests/macos/unlock/QuietResume.h"
#import "../../platforms/macos/guests/macos/unlock/CoveredInbox.h"
#import "../../platforms/macos/guests/macos/unlock/ConsoleLock.h"
#include <assert.h>
#include <unistd.h>
static void inboxTests(void) {
    int pair[2]; assert(!socketpair(AF_UNIX, SOCK_STREAM, 0, pair));
    CoveredInbox inbox = {0};
    const char *frames = "{\"operation\":\"heartbeat\"}\n{\"operation\":\"complete\",\"reason\":\"completed\"}\n";
    assert(write(pair[0], frames, strlen(frames)) == (ssize_t)strlen(frames));
    shutdown(pair[0], SHUT_WR);
    CoveredInput input = readCoveredInbox(pair[1], &inbox);
    assert(input == CoveredInputCompleted);
    assert([coveredInboxEnding(input, NO, YES, NO, YES, NO) isEqual:@"completed"]);
    assert([coveredInboxEnding(input, NO, YES, NO, YES, YES) isEqual:@"watchdog_interrupted"]);
    close(pair[0]); close(pair[1]);
    assert(!socketpair(AF_UNIX, SOCK_STREAM, 0, pair)); inbox = (CoveredInbox){0};
    assert(write(pair[0], "{\"oper", 6) == 6);
    assert(readCoveredInbox(pair[1], &inbox) == CoveredInputNone); // Never wait for the rest.
    frames = "ation\":\"heartbeat\"}\n";
    assert(write(pair[0], frames, strlen(frames)) == (ssize_t)strlen(frames));
    assert(readCoveredInbox(pair[1], &inbox) == CoveredInputHeartbeat);
    assert([coveredInboxEnding(CoveredInputHeartbeat, NO, NO, NO, YES, NO) isEqual:@"watchdog_interrupted"]);
    assert(coveredInboxEnding(CoveredInputHeartbeat, NO, NO, NO, NO, NO) == nil);
    shutdown(pair[0], SHUT_WR);
    assert(readCoveredInbox(pair[1], &inbox) == CoveredInputDisconnected);
    close(pair[0]); close(pair[1]);
    assert(!socketpair(AF_UNIX, SOCK_STREAM, 0, pair)); inbox = (CoveredInbox){0};
    char oversized[4096]; memset(oversized, 'x', sizeof(oversized));
    assert(write(pair[0], oversized, sizeof(oversized)) == sizeof(oversized));
    (void)readCoveredInbox(pair[1], &inbox);
    assert(readCoveredInbox(pair[1], &inbox) == CoveredInputDisconnected);
    close(pair[0]); close(pair[1]);
}
int main(void) { @autoreleasepool {
    inboxTests();
    NSDictionary *console = @{@"uuid":@"console", @"uid":@501, @"boot":@123};
    assert(consoleLockIdentity(console, @"console", @"123", @"501"));
    assert(!consoleLockIdentity(console, @"other", @"123", @"501"));
    assert(!consoleLockIdentity(console, @"console", @"124", @"501"));
    assert(!consoleLockIdentity(console, @"console", @"123", @"502"));
    assert(!consoleLockIdentity(@{@"uuid":@"console", @"uid":@0, @"boot":@123}, @"console", @"123", @"0"));
    assert(!consoleLockIdentity(nil, @"console", @"123", @"501"));
    assert(resumablePause(@"physical_presence"));
    assert(resumablePause(@"local_use_episode"));
    assert(!resumablePause(@"watchdog_interrupted"));
    assert(!resumablePause(nil));
    assert(quietResumeEligible(YES, YES, 100, 130, 30));
    assert(!quietResumeEligible(YES, YES, 100, 129.999, 30));
    assert(!quietResumeEligible(YES, YES, 100, 131, 29.999));
    assert(!quietResumeEligible(YES, NO, 100, 160, 60));
    assert(!quietResumeEligible(NO, YES, 100, 160, 60));
    assert(!quietResumeEligible(YES, YES, NAN, 160, 60));
    assert(!quietResumeEligible(YES, YES, 100, 160, NAN));
    assert(!quietResumeEligible(YES, YES, 0, 160, 60));
    assert(!quietResumeEligible(YES, YES, 200, 160, 60));
    assert(faultRecoveryEligible(YES, YES, YES, 100, 130, 30, 30));
    assert(!faultRecoveryEligible(YES, YES, NO, 100, 160, 60, 30));
    assert(!faultRecoveryEligible(YES, NO, YES, 100, 160, 60, 30));
    assert(!faultRecoveryEligible(NO, YES, YES, 100, 160, 60, 30));
    assert(!faultRecoveryEligible(YES, YES, YES, 100, 129, 60, 30));
    assert(!faultRecoveryEligible(YES, YES, YES, 100, 159, 60, 60));
    assert(faultRecoveryDelay(1) == 30 && faultRecoveryDelay(2) == 60 && faultRecoveryDelay(100) == 300);
    puts("Root quiet-resume policy passed");
} }
