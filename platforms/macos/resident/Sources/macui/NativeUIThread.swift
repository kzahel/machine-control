import Foundation

/// Only short, thread-affine OS reads belong here. Never wrap AX messaging,
/// process/socket waits or whole provider operations: the coordinator must run.
enum NativeUIThread {
    static func perform<T>(_ read: () throws -> T) rethrows -> T {
        if Thread.isMainThread { return try read() }
        return try DispatchQueue.main.sync(execute:read)
    }
}
