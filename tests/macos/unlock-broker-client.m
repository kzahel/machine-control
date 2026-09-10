// Standalone IPC fixture. Normal installation must deny this executable,
// including when it uses the correct UID, public labels, or runs as root.
#import <Foundation/Foundation.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
static int connectBroker(void) {
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    struct sockaddr_un addr = {.sun_family = AF_UNIX};
    strlcpy(addr.sun_path, "/var/run/machine-control-unlock/control.sock", sizeof(addr.sun_path));
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr))) exit(2);
    return fd;
}
static void sendJSON(int fd, NSDictionary *value) {
    NSMutableData *data = [[NSJSONSerialization dataWithJSONObject:value options:0 error:NULL] mutableCopy];
    [data appendBytes:"\n" length:1];
    if (write(fd, data.bytes, data.length) != (ssize_t)data.length) exit(3);
}
static NSDictionary *readJSON(int fd) {
    NSMutableData *data = [NSMutableData data]; char b;
    while (data.length < 4096 && read(fd, &b, 1) == 1 && b != '\n') [data appendBytes:&b length:1];
    id value = [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    return [value isKindOfClass:NSDictionary.class] ? value : @{};
}
int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 2 || (strcmp(argv[1], "status") && strcmp(argv[1], "unlock") && strcmp(argv[1], "cancel"))) return 2;
    int fd = connectBroker(); sendJSON(fd, @{@"operation":@"status"}); NSDictionary *status = readJSON(fd); close(fd);
    NSDictionary *result = status;
    if (strcmp(argv[1], "status")) {
        fd = connectBroker();
        sendJSON(fd, @{@"operation":@"unlock", @"requestId":NSUUID.UUID.UUIDString,
            @"helperGeneration":status[@"helperGeneration"] ?: @"",
            @"helperDesktopGeneration":status[@"helperDesktopGeneration"] ?: @""});
        result = readJSON(fd);
        if ([result[@"armed"] boolValue] && !strcmp(argv[1], "unlock")) result = readJSON(fd);
        close(fd);
    }
    NSData *data = [NSJSONSerialization dataWithJSONObject:result options:0 error:NULL];
    puts([[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding].UTF8String);
    return 0;
}}
