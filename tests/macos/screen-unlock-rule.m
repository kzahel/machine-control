#import "../../platforms/macos/guests/macos/unlock/ScreenUnlockRule.h"
#include <assert.h>
int main(void) { @autoreleasepool {
    NSString *ours = @"org.machine-control.screen-unlock";
    NSString *peer = @"com.example.unlock";
    NSDictionary *stock = @{@"class":@"rule", @"rule":@[SCREEN_UNLOCK_FALLBACK], @"version":@1,
        @"comment":@"stock"};
    NSDictionary *shared = @{@"class":@"rule", @"k-of-n":@1, @"rule":@[peer, SCREEN_UNLOCK_FALLBACK]};

    NSDictionary *alone = screenUnlockRuleAdding(stock, ours);
    assert([alone[@"rule"] isEqual:(@[ours, SCREEN_UNLOCK_FALLBACK])]);
    assert([alone[@"k-of-n"] isEqual:@1] && [alone[@"comment"] isEqual:@"stock"]);
    assert(screenUnlockRuleContains(alone, ours));
    assert(screenUnlockRuleAdding(alone, ours) == alone);

    // Join after other alternatives, before the password fallback.
    NSDictionary *joined = screenUnlockRuleAdding(shared, ours);
    assert([joined[@"rule"] isEqual:(@[peer, ours, SCREEN_UNLOCK_FALLBACK])]);
    assert([screenUnlockPeers(joined, ours) isEqual:@[peer]]);
    assert([screenUnlockPeers(stock, ours) isEqual:@[]]);

    // Removal preserves everyone else, including entries added after ours.
    NSDictionary *later = @{@"class":@"rule", @"k-of-n":@1,
        @"rule":@[@"com.example.later", ours, peer, SCREEN_UNLOCK_FALLBACK]};
    assert([screenUnlockRuleRemoving(later, ours)[@"rule"] isEqual:(@[@"com.example.later", peer, SCREEN_UNLOCK_FALLBACK])]);
    assert([screenUnlockRuleRemoving(alone, ours)[@"rule"] isEqual:@[SCREEN_UNLOCK_FALLBACK]]);
    assert(screenUnlockRuleRemoving(shared, ours) == shared);
    NSDictionary *foreign = @{@"class":@"evaluate-mechanisms", @"mechanisms":@[@"x"]};
    assert(screenUnlockRuleRemoving(foreign, ours) == foreign);
    assert(!screenUnlockRuleRemoving(@{@"class":@"user", @"rule":@[ours]}, ours));
    assert(!screenUnlockRuleRemoving(nil, ours));

    // Unsupported shapes refuse rather than guess.
    assert(!screenUnlockRuleAdding(nil, ours));
    assert(!screenUnlockRuleAdding(foreign, ours));
    assert(!screenUnlockRuleAdding(@{@"class":@"rule", @"rule":@[peer, SCREEN_UNLOCK_FALLBACK]}, ours));
    assert(!screenUnlockRuleAdding(@{@"class":@"rule", @"k-of-n":@2, @"rule":@[peer, SCREEN_UNLOCK_FALLBACK]}, ours));
    assert(!screenUnlockRuleAdding(@{@"class":@"rule", @"k-of-n":@YES, @"rule":@[SCREEN_UNLOCK_FALLBACK]}, ours));
    assert(!screenUnlockRuleAdding(@{@"class":@"rule", @"k-of-n":@1, @"rule":@[peer]}, ours));
    assert(!screenUnlockRuleAdding(@{@"class":@"rule", @"k-of-n":@1, @"rule":@[@3, SCREEN_UNLOCK_FALLBACK]}, ours));
    assert(!screenUnlockRuleAdding(stock, SCREEN_UNLOCK_FALLBACK));
    assert(!screenUnlockRuleContains(shared, ours));
    puts("Shared screen-unlock rule composition passed");
} }
