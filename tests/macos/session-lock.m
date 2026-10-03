// Explicit physical-test lock runner. No credential or unlock authority.
#import "../../platforms/macos/guests/macos/unlock/Session.h"
#import "../../platforms/macos/guests/macos/unlock/Relock.h"

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc != 2 || strcmp(argv[1], "--lock")) {
            fputs("Usage: session-lock --lock\n", stderr);
            return 2;
        }
        NSDictionary *initial = sessionState();
        if (!initial || ![initial[@"uid"] isEqual:@(getuid())] || !lockConsoleAvailable()) {
            fputs("Current user's console and native lock primitive are required\n", stderr);
            return 1;
        }
        if (![initial[@"locked"] boolValue]) lockConsole();
        double deadline = monotonicNow() + 5;
        BOOL locked = NO;
        do {
            NSDictionary *current = sessionState();
            if (![current[@"uuid"] isEqual:initial[@"uuid"]] ||
                ![current[@"boot"] isEqual:initial[@"boot"]] ||
                ![current[@"uid"] isEqual:initial[@"uid"]]) break;
            if ([current[@"locked"] boolValue]) { locked = YES; break; }
            usleep(20000);
        } while (monotonicNow() < deadline);
        puts(locked ? "{\"lockedObserved\":true}" : "{\"lockedObserved\":false}");
        return locked ? 0 : 1;
    }
}
