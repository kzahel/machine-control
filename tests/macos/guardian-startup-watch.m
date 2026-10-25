// Disposable-VM fault injector: stop only the exact resident's new guardian.
// No input, credentials or production test hook. The caller verifies root and
// OS state before deciding whether this injection was early enough to qualify.
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#include <libproc.h>
#include <signal.h>
#include <sys/sysctl.h>
#include <unistd.h>
#include <time.h>

static BOOL guardianArguments(pid_t pid) {
    int mib[] = {CTL_KERN, KERN_PROCARGS2, pid};
    char args[32768]; size_t size = sizeof(args);
    if (sysctl(mib, 3, args, &size, NULL, 0) || size <= sizeof(int)) return NO;
    int count; memcpy(&count, args, sizeof(count));
    if (count != 2) return NO;
    size_t offset = sizeof(int);
    size_t length = strnlen(args + offset, size - offset);
    if (length == size - offset) return NO;
    offset += length;
    while (offset < size && args[offset] == 0) offset++;
    if (offset >= size) return NO;
    length = strnlen(args + offset, size - offset);
    if (length == size - offset) return NO;
    offset += length + 1;
    return offset < size && strnlen(args + offset, size - offset) == strlen("locked-use-guardian") &&
        strcmp(args + offset, "locked-use-guardian") == 0;
}

int main(int argc, const char **argv) { @autoreleasepool {
    if (argc == 2 && !strcmp(argv[1], "--raw-time")) {
        struct timespec now;
        if (clock_gettime(CLOCK_MONOTONIC_RAW, &now)) return 3;
        printf("%.9f\n", now.tv_sec + now.tv_nsec / 1e9); return 0;
    }
    if (argc == 3 && !strcmp(argv[1], "--pidpath")) {
        pid_t pid = (pid_t)[@(argv[2]) intValue]; char path[PROC_PIDPATHINFO_MAXSIZE];
        if (pid <= 1 || proc_pidpath(pid, path, sizeof(path)) <= 0) return 3;
        puts(path); return 0;
    }
    if (argc != 2) return 2;
    pid_t parent = (pid_t)[@(argv[1]) intValue];
    char expected[PROC_PIDPATHINFO_MAXSIZE];
    if (parent <= 1 || proc_pidpath(parent, expected, sizeof(expected)) <= 0) return 3;
    for (int attempt = 0; attempt < 30000; attempt++) {
        pid_t children[256];
        int count = proc_listchildpids(parent, children, sizeof(children));
        if (count < 0 || count >= 256) return 4;
        for (int index = 0; index < count; index++) {
            pid_t child = children[index]; char path[PROC_PIDPATHINFO_MAXSIZE];
            if (proc_pidpath(child, path, sizeof(path)) <= 0 || strcmp(path, expected) || !guardianArguments(child)) continue;
            if (kill(child, SIGSTOP)) return 5;
            NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID));
            NSUInteger count = 0;
            for (NSDictionary *window in windows) if ([window[(id)kCGWindowOwnerPID] intValue] == child) count++;
            NSData *data = [NSJSONSerialization dataWithJSONObject:@{@"pid":@(child), @"ownedWindows":@(count)} options:0 error:NULL];
            fwrite(data.bytes, 1, data.length, stdout); fputc('\n', stdout); fflush(stdout);
            return 0;
        }
        usleep(1000);
    }
    return 6;
} }
