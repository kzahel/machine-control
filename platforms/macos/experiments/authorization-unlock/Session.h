#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <time.h>
#include <unistd.h>

#define STATE_DIR "/var/db/machine-control-unlock-experiment"
#define GRANT_PATH STATE_DIR "/grant.plist"

static NSDictionary *sessionState(void) {
    io_registry_entry_t root = IORegistryGetRootEntry(kIOMainPortDefault);
    if (!root) return nil;
    id locked = CFBridgingRelease(IORegistryEntryCreateCFProperty(root,
        CFSTR("IOConsoleLocked"), kCFAllocatorDefault, 0));
    id users = CFBridgingRelease(IORegistryEntryCreateCFProperty(root,
        CFSTR("IOConsoleUsers"), kCFAllocatorDefault, 0));
    IOObjectRelease(root);
    if (![locked isKindOfClass:NSNumber.class] ||
        ![users isKindOfClass:NSArray.class]) return nil;

    NSMutableArray *active = [NSMutableArray array];
    for (id session in users) {
        if ([session isKindOfClass:NSDictionary.class] &&
            [session[@"kCGSSessionOnConsoleKey"] boolValue] &&
            [session[@"kCGSessionLoginDoneKey"] boolValue]) {
            [active addObject:session];
        }
    }
    if (active.count != 1) return nil;
    NSDictionary *session = active[0];
    id uuid = session[@"CGSSessionUniqueSessionUUID"];
    id uid = session[@"kCGSSessionUserIDKey"];
    if (![uuid isKindOfClass:NSString.class] ||
        ![uid isKindOfClass:NSNumber.class] || [uid unsignedIntValue] == 0) {
        return nil;
    }
    struct timeval boot = {0};
    size_t length = sizeof(boot);
    int mib[] = {CTL_KERN, KERN_BOOTTIME};
    if (sysctl(mib, 2, &boot, &length, NULL, 0)) return nil;
    return @{@"locked": locked, @"uuid": uuid, @"uid": uid,
             @"boot": @((long long)boot.tv_sec)};
}

static double monotonicNow(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC_RAW, &now);
    return now.tv_sec + now.tv_nsec / 1e9;
}

static void recordDecision(const char *reason) {
    int fd = open(STATE_DIR "/decisions.log",
        O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW, 0600);
    if (fd >= 0) {
        dprintf(fd, "%s\n", reason);
        close(fd);
    }
}

static BOOL consumeGrant(void) {
    if (geteuid() != 0) return NO;
    struct stat directory;
    if (lstat(STATE_DIR, &directory) || !S_ISDIR(directory.st_mode) ||
        directory.st_uid != 0 || (directory.st_mode & 0077)) return NO;
    int fd = open(GRANT_PATH, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) {
        recordDecision("deny:no-grant");
        return NO;
    }
    struct stat original;
    if (fstat(fd, &original) || !S_ISREG(original.st_mode) ||
        original.st_uid != 0 || (original.st_mode & 0077) ||
        original.st_nlink != 1 || original.st_size <= 0 ||
        original.st_size > 4096) {
        close(fd);
        recordDecision("deny:invalid-file");
        return NO;
    }

    // Atomic rename makes only one concurrent invocation the consumer.
    char consumed[512];
    snprintf(consumed, sizeof(consumed), STATE_DIR "/consumed-%d-%llu",
        getpid(), (unsigned long long)clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW));
    if (rename(GRANT_PATH, consumed)) {
        close(fd);
        recordDecision("deny:race");
        return NO;
    }
    struct stat claimed;
    if (lstat(consumed, &claimed) || claimed.st_ino != original.st_ino ||
        claimed.st_dev != original.st_dev) {
        close(fd);
        unlink(consumed);
        recordDecision("deny:changed-file");
        return NO;
    }
    NSMutableData *data = [NSMutableData dataWithLength:(NSUInteger)original.st_size];
    ssize_t length = read(fd, data.mutableBytes, data.length);
    close(fd);
    unlink(consumed);
    if (length != (ssize_t)data.length) {
        recordDecision("deny:read");
        return NO;
    }
    id grant = [NSPropertyListSerialization propertyListWithData:data
        options:NSPropertyListImmutable format:NULL error:NULL];
    NSDictionary *state = sessionState();
    double now = monotonicNow();
    BOOL allowed = [grant isKindOfClass:NSDictionary.class] &&
        [grant[@"purpose"] isEqual:@"screen-unlock"] &&
        [state[@"locked"] boolValue] &&
        [grant[@"uuid"] isEqual:state[@"uuid"]] &&
        [grant[@"uid"] isEqual:state[@"uid"]] &&
        [grant[@"boot"] isEqual:state[@"boot"]] &&
        [grant[@"expires"] isKindOfClass:NSNumber.class] &&
        [grant[@"issued"] isKindOfClass:NSNumber.class] &&
        now >= [grant[@"issued"] doubleValue] &&
        now < [grant[@"expires"] doubleValue] &&
        [grant[@"expires"] doubleValue] - [grant[@"issued"] doubleValue] <= 30.0;
    recordDecision(allowed ? "allow:consumed" : "deny:state-or-expiry");
    return allowed;
}
