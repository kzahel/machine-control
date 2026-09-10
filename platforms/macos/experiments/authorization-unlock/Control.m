#import <Security/Security.h>
#import "Session.h"
#include <math.h>

static const char *rightName = "org.machine-control.experiment.screen-unlock";

static int arm(int argc, char **argv) {
    if (geteuid() != 0) return 3;
    NSDictionary *state = sessionState();
    if (!state || ![state[@"locked"] boolValue]) return 4;
    char *end = NULL;
    double ttl = argc > 2 ? strtod(argv[2], &end) : 15;
    if (argc > 3 || !isfinite(ttl) || ttl < 1 || ttl > 30 ||
        (argc > 2 && (end == argv[2] || *end))) return 2;
    if (mkdir(STATE_DIR, 0700) && errno != EEXIST) return 5;
    struct stat directory;
    if (lstat(STATE_DIR, &directory) || !S_ISDIR(directory.st_mode) ||
        directory.st_uid != 0 || (directory.st_mode & 0077)) return 5;

    NSMutableDictionary *grant = [state mutableCopy];
    grant[@"purpose"] = @"screen-unlock";
    grant[@"issued"] = @(monotonicNow());
    grant[@"expires"] = @([grant[@"issued"] doubleValue] + ttl);
    NSData *data = [NSPropertyListSerialization dataWithPropertyList:grant
        format:NSPropertyListBinaryFormat_v1_0 options:0 error:NULL];
    if (!data) return 7;
    int fd = open(GRANT_PATH, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (fd < 0) return 6;
    ssize_t written = write(fd, data.bytes, data.length);
    int syncResult = fsync(fd);
    close(fd);
    if (written != (ssize_t)data.length || syncResult) {
        unlink(GRANT_PATH);
        return 7;
    }
    puts("armed");
    return 0;
}

static int evaluate(void) {
    // An absent right can fall through to generic admin authentication.
    // Never launch that unrelated UI when the experiment is removed or changed.
    CFDictionaryRef definition = NULL;
    OSStatus status = AuthorizationRightGet(rightName, &definition);
    NSDictionary *policy = CFBridgingRelease(definition);
    if (status || ![policy[@"class"] isEqual:@"evaluate-mechanisms"] ||
        ![policy[@"mechanisms"] isEqual:@[@"MCUnlockExperiment:unlock,privileged"]]) {
        puts("{\"errorCode\":\"experiment_right_unavailable\"}");
        return 10;
    }
    AuthorizationRef auth = NULL;
    status = AuthorizationCreate(NULL, kAuthorizationEmptyEnvironment,
                                 kAuthorizationFlagDefaults, &auth);
    if (status) return 8;
    AuthorizationItem item = {rightName, 0, NULL, 0};
    AuthorizationRights rights = {1, &item};
    status = AuthorizationCopyRights(auth, &rights, kAuthorizationEmptyEnvironment,
        kAuthorizationFlagInteractionAllowed | kAuthorizationFlagExtendRights, NULL);
    printf("{\"authorizationStatus\":%d}\n", (int)status);
    AuthorizationFree(auth, kAuthorizationFlagDestroyRights);
    return status == 0 ? 0 : 9;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 2) return 2;
        if (!strcmp(argv[1], "arm")) return arm(argc, argv);
        if (argc != 2) return 2;
        if (!strcmp(argv[1], "state")) {
            NSDictionary *state = sessionState();
            if (!state) return 1;
            NSData *data = [NSJSONSerialization dataWithJSONObject:state
                options:0 error:NULL];
            puts([[NSString alloc] initWithData:data
                encoding:NSUTF8StringEncoding].UTF8String);
            return 0;
        }
        if (!strcmp(argv[1], "revoke")) {
            if (geteuid() != 0) return 3;
            return unlink(GRANT_PATH) && errno != ENOENT;
        }
        if (!strcmp(argv[1], "evaluate")) return evaluate();
        return 2;
    }
}
