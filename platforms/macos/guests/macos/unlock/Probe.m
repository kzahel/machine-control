#import "Session.h"
int main(void) { @autoreleasepool {
    NSDictionary *state = sessionState() ?: @{@"desktopState": @"unknown"};
    NSData *data = [NSJSONSerialization dataWithJSONObject:state options:0 error:NULL];
    puts([[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding].UTF8String);
    return 0;
}}
