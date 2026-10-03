#include <dlfcn.h>

// Measured private macOS route, deliberately limited to locking the console.
// Resolving the symbol is read-only. OS lock readback, not this call, is proof.
static BOOL lockConsoleAvailable(void) {
    static void *library;
    if (!library) library = dlopen("/System/Library/PrivateFrameworks/login.framework/login", RTLD_NOW);
    return library && dlsym(library, "SACLockScreenImmediate");
}
static void lockConsole(void) {
    static void *library;
    if (!library) library = dlopen("/System/Library/PrivateFrameworks/login.framework/login", RTLD_NOW);
    void (*lock)(void) = library ? dlsym(library, "SACLockScreenImmediate") : NULL;
    if (lock) lock();
}
