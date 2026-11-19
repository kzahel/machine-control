// Independent, bounded guest-only input diagnostic. This is a software-posted
// kernel HID event, not evidence of a physical mouse or virtual HID device.
#import <Foundation/Foundation.h>
#import <ApplicationServices/ApplicationServices.h>
#import <IOKit/hidsystem/IOHIDLib.h>
#import <IOKit/hidsystem/IOHIDShared.h>
#import <IOKit/hidsystem/IOLLEvent.h>
#include <sys/sysctl.h>

int main(int argc, const char **argv) { @autoreleasepool {
    char model[128] = {0}; size_t length = sizeof(model);
    if (argc != 2 || (strcmp(argv[1], "--preflight") && strcmp(argv[1], "--move") && strcmp(argv[1], "--key")) ||
        sysctlbyname("hw.model", model, &length, NULL, 0) || strncmp(model,"VirtualMac",10)) {
        fputs("Dedicated VirtualMac and --preflight, --move or --key required\n",stderr); return 2;
    }
    IOHIDAccessType access = IOHIDCheckAccess(kIOHIDRequestTypePostEvent);
    NSString *state = access == kIOHIDAccessTypeGranted ? @"granted" : access == kIOHIDAccessTypeDenied ? @"denied" : @"unknown";
    if (!strcmp(argv[1],"--preflight")) {
        printf("{\"postAccess\":\"%s\",\"route\":\"guest.kernel.IOHIDPostEvent\"}\n",state.UTF8String); return 0;
    }
    // Never trigger consent, edit TCC, add entitlements, or manufacture event
    // origin metadata. Refuse when the independent route lacks permission.
    if (access != kIOHIDAccessTypeGranted) { puts("{\"accepted\":false,\"reason\":\"post_permission_unavailable\"}"); return 3; }
    io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault,IOServiceMatching("IOHIDSystem"));
    io_connect_t connection = IO_OBJECT_NULL;
    IOReturn result = service ? IOServiceOpen(service,mach_task_self(),kIOHIDParamConnectType,&connection) : kIOReturnNotFound;
    if (service) IOObjectRelease(service);
    if (result == kIOReturnSuccess) {
        NXEventData event = {0};
        if (!strcmp(argv[1],"--key")) {
            // One Escape press and release: a deliberate key-down, as a
            // person would type, from the kernel HID route (source PID 0).
            event.key.keyCode = 53; event.key.charSet = NX_ASCIISET; event.key.charCode = 27;
            result = IOHIDPostEvent(connection,NX_KEYDOWN,(IOGPoint){0,0},&event,kNXEventDataVersion,0,0);
            if (result == kIOReturnSuccess)
                result = IOHIDPostEvent(connection,NX_KEYUP,(IOGPoint){0,0},&event,kNXEventDataVersion,0,0);
        } else {
            event.mouseMove.dx = 1; event.mouseMove.dy = 0;
            result = IOHIDPostEvent(connection,NX_MOUSEMOVED,(IOGPoint){1,0},&event,kNXEventDataVersion,0,kIOHIDSetRelativeCursorPosition);
        }
        IOServiceClose(connection);
    }
    printf("{\"accepted\":%s,\"result\":%u,\"route\":\"guest.kernel.IOHIDPostEvent\"}\n",result == kIOReturnSuccess ? "true" : "false",result);
    return result == kIOReturnSuccess ? 0 : 1;
} }
