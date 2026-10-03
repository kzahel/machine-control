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
