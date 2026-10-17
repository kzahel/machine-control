// Guest-only source-native workstation fixture. Compile as main.swift beside
// the production resident sources, excluding their main.swift. No test approval
// path: native consent must be clicked through the separate appliance resident.
import AppKit
import Foundation

let probe = Process()
probe.executableURL = URL(fileURLWithPath:"/usr/sbin/sysctl")
probe.arguments = ["-n", "hw.model"]
let output = Pipe(); probe.standardOutput = output
try probe.run(); probe.waitUntilExit()
let model = String(decoding:output.fileHandleForReading.readDataToEndOfFile(), as:UTF8.self)
guard model.hasPrefix("VirtualMac"),
      let socket = Bundle.main.object(forInfoDictionaryKey:"MCFixtureSocket") as? String,
      let suite = Bundle.main.object(forInfoDictionaryKey:"MCFixturePreferences") as? String,
      let preferences = UserDefaults(suiteName:suite) else { fatalError("Explicit VM fixture configuration required") }
if let origin = CommandLine.arguments.dropFirst().first, origin.hasPrefix("chrome-extension://") {
    runBrowserHost(origin:origin, socketPath:socket)
}
_ = NSApplication.shared
NSApp.setActivationPolicy(.regular)
let runtime = try ResidentRuntime(socketPath:socket, policy:.workstation(issue:nil), journal:nil,
                                  preferences:preferences)
try runtime.start()
// This test owns its stdin, just as the desktop shell owns its in-process
// operator calls. No command here issues a grant or answers a consent prompt.
Thread.detachNewThread {
    while let line = readLine() {
        DispatchQueue.main.async {
            switch line {
            case "enable":
                print(String(describing:runtime.operatorCommand(["method":"browser_while_locked", "enabled":true])))
            case "disable":
                print(String(describing:runtime.operatorCommand(["method":"browser_while_locked", "enabled":false])))
            case "pause":
                print(String(describing:runtime.operatorCommand(["method":"pause"])))
            case "resume":
                // No helper is installed or needed for this browser-only probe.
                try? runtime.server.broker.resume()
            case "stop": runtime.stopAccess()
            case "quit":
                runtime.stop(); preferences.removePersistentDomain(forName:suite); exit(0)
            default: fatalError("Unsupported fixture command")
            }
            fflush(stdout)
        }
    }
    DispatchQueue.main.async { runtime.stop(); preferences.removePersistentDomain(forName:suite); exit(0) }
}
NSApp.run()
