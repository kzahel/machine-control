#import "../../platforms/macos/guests/macos/unlock/Session.h"
#include <assert.h>
int main(void) { @autoreleasepool {
    assert(!consoleSessionState(nil, @[]));
    assert(!consoleSessionState(@YES, @"invalid"));
    assert(!consoleSessionState(@YES, @[@"invalid"]));
    assert([consoleSessionState(@YES, @[])[@"desktopState"] isEqual:@"no_session"]);
    NSDictionary *user = @{@"kCGSSessionOnConsoleKey":@YES, @"kCGSessionLoginDoneKey":@YES,
        @"CGSSessionUniqueSessionUUID":@"fixture-session", @"kCGSSessionUserIDKey":@501};
    assert([consoleSessionState(@YES, @[user])[@"desktopState"] isEqual:@"locked"]);
    assert([consoleSessionState(@NO, @[user])[@"desktopState"] isEqual:@"unlocked"]);
    assert(!consoleSessionState(@YES, @[user,user]));
    NSMutableDictionary *incomplete = [user mutableCopy]; [incomplete removeObjectForKey:@"CGSSessionUniqueSessionUUID"];
    assert(!consoleSessionState(@YES, @[incomplete]));
    incomplete = [user mutableCopy]; incomplete[@"kCGSSessionUserIDKey"] = @0;
    assert(!consoleSessionState(@YES, @[incomplete]));
    puts("Session observation fixtures passed"); return 0;
}}
