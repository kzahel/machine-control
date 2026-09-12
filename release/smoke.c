#include <stdio.h>
#include "smoke_identity.h"

int main(void) {
    puts("{\"schema\":\"machine-control-signing-smoke/v0\","
         "\"platform\":\"" MC_PLATFORM "\","
         "\"sourceRevision\":\"" MC_REVISION "\"}");
    return 0;
}
