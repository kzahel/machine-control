#import "../../platforms/macos/guests/macos/unlock/QuietResume.h"
#include <assert.h>
int main(void) { @autoreleasepool {
    assert(resumablePause(@"physical_presence"));
    assert(resumablePause(@"local_use_episode"));
    assert(!resumablePause(@"watchdog_interrupted"));
    assert(!resumablePause(nil));
    assert(quietResumeEligible(YES, YES, 100, 130, 30));
    assert(!quietResumeEligible(YES, YES, 100, 129.999, 30));
    assert(!quietResumeEligible(YES, YES, 100, 131, 29.999));
    assert(!quietResumeEligible(YES, NO, 100, 160, 60));
    assert(!quietResumeEligible(NO, YES, 100, 160, 60));
    assert(!quietResumeEligible(YES, YES, NAN, 160, 60));
    assert(!quietResumeEligible(YES, YES, 100, 160, NAN));
    assert(!quietResumeEligible(YES, YES, 0, 160, 60));
    assert(!quietResumeEligible(YES, YES, 200, 160, 60));
    puts("Root quiet-resume policy passed");
} }
