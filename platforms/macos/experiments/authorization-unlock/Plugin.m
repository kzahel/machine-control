#import <Security/AuthorizationPlugin.h>
#import "Session.h"

typedef struct {
    const AuthorizationCallbacks *callbacks;
} Plugin;

typedef struct {
    Plugin *plugin;
    AuthorizationEngineRef engine;
} Mechanism;

static OSStatus destroyPlugin(AuthorizationPluginRef plugin) {
    free(plugin);
    return errAuthorizationSuccess;
}

static OSStatus createMechanism(AuthorizationPluginRef plugin,
    AuthorizationEngineRef engine, AuthorizationMechanismId name,
    AuthorizationMechanismRef *outMechanism) {
    if (strcmp(name, "unlock")) return errAuthorizationInternal;
    Mechanism *mechanism = calloc(1, sizeof(*mechanism));
    if (!mechanism) return errAuthorizationInternal;
    mechanism->plugin = plugin;
    mechanism->engine = engine;
    *outMechanism = mechanism;
    return errAuthorizationSuccess;
}

static OSStatus invoke(AuthorizationMechanismRef reference) {
    @autoreleasepool {
        Mechanism *mechanism = reference;
        return mechanism->plugin->callbacks->SetResult(mechanism->engine,
            consumeGrant() ? kAuthorizationResultAllow : kAuthorizationResultDeny);
    }
}

static OSStatus deactivate(AuthorizationMechanismRef reference) {
    Mechanism *mechanism = reference;
    return mechanism->plugin->callbacks->DidDeactivate(mechanism->engine);
}

static OSStatus destroyMechanism(AuthorizationMechanismRef mechanism) {
    free(mechanism);
    return errAuthorizationSuccess;
}

static const AuthorizationPluginInterface interface = {
    kAuthorizationPluginInterfaceVersion, destroyPlugin, createMechanism,
    invoke, deactivate, destroyMechanism
};

__attribute__((visibility("default")))
OSStatus AuthorizationPluginCreate(const AuthorizationCallbacks *callbacks,
    AuthorizationPluginRef *outPlugin,
    const AuthorizationPluginInterface **outInterface) {
    Plugin *plugin = calloc(1, sizeof(*plugin));
    if (!plugin) return errAuthorizationInternal;
    plugin->callbacks = callbacks;
    *outPlugin = plugin;
    *outInterface = &interface;
    return errAuthorizationSuccess;
}
