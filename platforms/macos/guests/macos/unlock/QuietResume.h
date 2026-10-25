#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#include <math.h>

// A missing HID observation or a clock reversal never establishes quiet.
static double physicalIdleSeconds(void) {
    io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IOHIDSystem"));
    if (!service) return NAN;
    id value = CFBridgingRelease(IORegistryEntryCreateCFProperty(service, CFSTR("HIDIdleTime"), kCFAllocatorDefault, 0));
    IOObjectRelease(service);
    if (![value isKindOfClass:NSNumber.class]) return NAN;
    double idle = [value doubleValue] / 1e9;
    return isfinite(idle) && idle >= 0 ? idle : NAN;
}
static BOOL resumablePause(NSString *reason) {
    return [reason isEqual:@"physical_presence"] || [reason isEqual:@"local_use_episode"];
}
static BOOL quietResumeEligible(BOOL same, BOOL locked, double pausedAt, double now, double idle) {
    return same && locked && isfinite(pausedAt) && pausedAt > 0 && isfinite(now) &&
        isfinite(idle) && now >= pausedAt + 30 && idle >= 30;
}

// A fault cannot grant authority or clear an operator pause. It can finish
// protected cleanup after root independently observes the original console
// locked, verifies its installation and waits for physical quiet. Every next
// covered task still creates fresh covers, input guards and finite authority.
static BOOL faultRecoveryEligible(BOOL same, BOOL locked, BOOL healthy,
                                  double pausedAt, double now, double idle, double delay) {
    return healthy && isfinite(delay) && delay >= 30 && delay <= 300 &&
        quietResumeEligible(same, locked, pausedAt, now, idle) && now >= pausedAt + delay;
}
static double faultRecoveryDelay(NSUInteger failures) {
    return MIN(300, 30 * pow(2, MIN(failures > 0 ? failures - 1 : 0, 4)));
}
