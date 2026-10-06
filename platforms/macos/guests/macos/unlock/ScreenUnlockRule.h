#import <Foundation/Foundation.h>

// system.login.screensaver is shared with other authorization plug-ins. Each
// alternative is one named right in a k-of-n = 1 rule, ahead of Apple's
// use-login-window-ui password fallback. macOS only replaces whole rights, so
// every writer must re-read, change only its own entry and preserve the rest.
// These functions are pure: callers own reading, writing and confirmation.
NS_ASSUME_NONNULL_BEGIN

#define SCREEN_UNLOCK_FALLBACK @"use-login-window-ui"

// Entries of a rule in the supported one-of-n shape, otherwise nil. A rule
// with only the fallback may omit k-of-n; with several entries an absent
// k-of-n means all must pass, which no alternative may join.
static NSArray<NSString *> * _Nullable screenUnlockEntries(NSDictionary * _Nullable rule) {
    NSArray *entries = rule[@"rule"];
    if (![rule[@"class"] isEqual:@"rule"] || ![entries isKindOfClass:NSArray.class] ||
        ![entries containsObject:SCREEN_UNLOCK_FALLBACK]) return nil;
    for (id entry in entries) {
        if (![entry isKindOfClass:NSString.class] || ![entry length]) return nil;
    }
    id count = rule[@"k-of-n"];
    BOOL one = [count isKindOfClass:NSNumber.class] &&
        CFGetTypeID((__bridge CFTypeRef)count) != CFBooleanGetTypeID() && [count isEqual:@1];
    if (!one && !(count == nil && entries.count == 1)) return nil;
    return entries;
}
static BOOL screenUnlockRuleContains(NSDictionary * _Nullable rule, NSString *entry) {
    return [screenUnlockEntries(rule) containsObject:entry];
}
// Inserts entry immediately before the password fallback. Returns the rule
// unchanged when entry is present and nil when the shape is unsupported.
static NSDictionary * _Nullable screenUnlockRuleAdding(NSDictionary * _Nullable rule, NSString *entry) {
    NSArray<NSString *> *entries = screenUnlockEntries(rule);
    if (!entries || [entry isEqual:SCREEN_UNLOCK_FALLBACK]) return nil;
    if ([entries containsObject:entry]) return rule;
    NSMutableArray *next = [entries mutableCopy];
    [next insertObject:entry atIndex:[next indexOfObject:SCREEN_UNLOCK_FALLBACK]];
    NSMutableDictionary *result = [rule mutableCopy];
    result[@"rule"] = next; result[@"k-of-n"] = @1;
    return result;
}
// Removes only entry. A rule that does not mention it is returned unchanged
// whatever its shape; one that does but is unsupported returns nil.
static NSDictionary * _Nullable screenUnlockRuleRemoving(NSDictionary * _Nullable rule, NSString *entry) {
    if (!rule) return nil;
    NSArray *raw = rule[@"rule"];
    if (![raw isKindOfClass:NSArray.class] || ![raw containsObject:entry]) return rule;
    NSArray<NSString *> *entries = screenUnlockEntries(rule);
    if (!entries) return nil;
    NSMutableArray *next = [entries mutableCopy];
    [next removeObject:entry];
    NSMutableDictionary *result = [rule mutableCopy];
    result[@"rule"] = next;
    return result;
}
// Other alternatives sharing the rule, for honest status reporting.
static NSArray<NSString *> *screenUnlockPeers(NSDictionary * _Nullable rule, NSString *entry) {
    NSArray *raw = rule[@"rule"];
    if (![raw isKindOfClass:NSArray.class]) return @[];
    NSMutableArray *peers = [NSMutableArray array];
    for (id value in raw) {
        if ([value isKindOfClass:NSString.class] && ![value isEqual:entry] &&
            ![value isEqual:SCREEN_UNLOCK_FALLBACK] && ![peers containsObject:value]) [peers addObject:value];
    }
    return peers;
}

NS_ASSUME_NONNULL_END
