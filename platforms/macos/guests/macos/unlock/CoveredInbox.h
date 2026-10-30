#import <Foundation/Foundation.h>
#include <sys/socket.h>
#include <errno.h>
#include <string.h>
#include <math.h>

typedef NS_ENUM(int, CoveredInput) {
    CoveredInputNone, CoveredInputHeartbeat, CoveredInputCompleted,
    CoveredInputPhysicalPresence, CoveredInputDisconnected, CoveredInputRenewal
};
typedef struct { char bytes[4096]; size_t used; double renewalUptime; } CoveredInbox;

// Drain bounded already-delivered frames before judging peer death. A guardian
// can write completion and exit before the watchdog next runs. Partial frames
// never block the root, and queued heartbeats do not establish timely liveness.
static CoveredInput readCoveredInbox(int fd, CoveredInbox *inbox) {
    CoveredInput result = CoveredInputNone;
    size_t budget = sizeof(inbox->bytes);
    while (YES) {
        // A renewal returns one acknowledgement at a time. Later frames from
        // that same read must be drained before another recv (including EOF).
        char *newline;
        while ((newline = memchr(inbox->bytes, '\n', inbox->used))) {
            size_t length = (size_t)(newline - inbox->bytes);
            NSData *data = [NSData dataWithBytes:inbox->bytes length:length];
            id message = [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
            size_t consumed = length + 1;
            memmove(inbox->bytes, inbox->bytes + consumed, inbox->used - consumed);
            inbox->used -= consumed;
            if (![message isKindOfClass:NSDictionary.class]) return CoveredInputDisconnected;
            NSString *operation = message[@"operation"];
            if ([operation isEqual:@"complete"] && ([message count] == 1 ||
                ([message count] == 2 && [message[@"reason"] isKindOfClass:NSString.class]))) return CoveredInputCompleted;
            if ([operation isEqual:@"heartbeat"] && [message count] == 1) { result = CoveredInputHeartbeat; continue; }
            if ([operation isEqual:@"renew"] && [message count] == 2) {
                id deadline = message[@"controlDeadlineUptime"];
                if (![deadline isKindOfClass:NSNumber.class] ||
                    CFGetTypeID((__bridge CFTypeRef)deadline) == CFBooleanGetTypeID() ||
                    !isfinite([deadline doubleValue]) || [deadline doubleValue] <= 0) return CoveredInputDisconnected;
                inbox->renewalUptime = [deadline doubleValue];
                return CoveredInputRenewal;
            }
            return [operation isEqual:@"cancel"] && [message count] == 2 && [message[@"reason"] isEqual:@"physical_presence"]
                ? CoveredInputPhysicalPresence : CoveredInputDisconnected;
        }
        if (!budget) return result;
        if (inbox->used == sizeof(inbox->bytes)) return CoveredInputDisconnected;
        size_t capacity = MIN(sizeof(inbox->bytes) - inbox->used, budget);
        ssize_t count = recv(fd, inbox->bytes + inbox->used, capacity, MSG_DONTWAIT);
        if (!count) return CoveredInputDisconnected;
        if (count < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) return result;
            return CoveredInputDisconnected;
        }
        inbox->used += (size_t)count; budget -= (size_t)count;
    }
}

// Completion ends authority; it can be honored after EOF/death. Heartbeats may
// renew only a live, unexpired watchdog, never an already expired one.
static NSString *coveredInboxEnding(CoveredInput input, BOOL stopping, BOOL dead,
                                   BOOL durationExpired, BOOL heartbeatExpired, BOOL installationBad) {
    if (stopping) return @"helper_stopping";
    if (installationBad) return @"watchdog_interrupted";
    if (input == CoveredInputCompleted) return @"completed";
    if (input == CoveredInputPhysicalPresence) return @"physical_presence";
    if (durationExpired) return @"duration_expired";
    if (dead || heartbeatExpired || installationBad) return @"watchdog_interrupted";
    return input == CoveredInputDisconnected ? @"owner_disconnected" : nil;
}
