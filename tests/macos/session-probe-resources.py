#!/usr/bin/env python3
"""Exercise the production observer without querying or controlling a desktop."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=(Path(__file__).resolve().parents[2] /
                    'platforms/macos/guests/macos/ui/macui.swift') if '__file__' in globals() else
                    Path.home() / 'Library/Application Support/macvm-testbed/macui.swift')
parser.add_argument('--iterations', type=int, default=500)
parser.add_argument('--idle-only', action='store_true',
                    help='compare unchanged old/new no-argument observer under a 128-FD limit')
parser.add_argument('--spawn-boundary', action='store_true',
                    help='explicit isolated 12000-FD Darwin spawn-boundary diagnostic')
parser.add_argument('--caller-pool', action='store_true',
                    help='diagnostic pool around each idle-only call')
args = parser.parse_args()
source = args.source.read_text()
observer = source[source.index('func nativeSessionObservation('):source.index('// Pure projection:')]
child = r'''
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
int main(int argc, char **argv) {
    char *mode = strrchr(argv[0], '/'); mode = mode ? mode + 1 : argv[0];
    if (!strcmp(mode, "nonzero")) return 23;
    if (!strcmp(mode, "invalid")) { puts("not json"); return 0; }
    if (!strcmp(mode, "shape")) { puts("{\"desktopState\":\"invented\"}"); return 0; }
    if (!strcmp(mode, "large")) { for (int i=0;i<40000;i++) putchar('x'); return 0; }
    if (!strcmp(mode, "hang") || !strcmp(mode, "closed")) {
        signal(SIGTERM, SIG_IGN);
        if (!strcmp(mode, "closed")) close(STDOUT_FILENO);
        sleep(30); return 0;
    }
    puts("{\"desktopState\":\"unlocked\"}"); return 0;
}
'''
fixture = r'''
func fds() -> Int { (0..<128).filter { fcntl(Int32($0), F_GETFD) >= 0 }.count }
func noChildren() {
    var status: Int32 = 0
    precondition(waitpid(-1, &status, WNOHANG) == -1 && errno == ECHILD, "unreaped probe")
}
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let iterations = Int(CommandLine.arguments[2])!
var limit = rlimit(rlim_cur: 128, rlim_max: 128)
precondition(setrlimit(RLIMIT_NOFILE, &limit) == 0)
func observe(_ name: String, timeout: TimeInterval = 2,
             cancelled: () -> Bool = { false }) -> [String: Any] {
    nativeSessionObservation(probeURL: root.appendingPathComponent(name),
                             timeout: timeout, cancelled: cancelled)
}
// Preconditions remain active in the optimized test build.
// Warm Foundation once before measuring. Deliberately NO caller pool: idle
// polling used to leak even though request handling already had a pool.
precondition(observe("ok")["desktopState"] as? String == "unlocked")
let baseline = fds()
for i in 1...iterations {
    precondition(observe("ok")["desktopState"] as? String == "unlocked")
    if i % 100 == 0 {
        precondition(fds() <= baseline, "descriptor growth at \(i)")
        noChildren()
    }
    if i % 1000 == 0 { print("probes=\(i) fds=\(fds()) baseline=\(baseline)"); fflush(stdout) }
}
for _ in 0..<10 {
    for (mode, failure) in [("missing", "launch_failed"), ("nonzero", "nonzero_exit"),
                            ("invalid", "invalid_response"), ("shape", "invalid_response"),
                            ("large", "output_limit"), ("hang", "timeout"), ("closed", "timeout")] {
        let result = observe(mode, timeout: 0.1)
        precondition(result["desktopState"] as? String == "unknown")
        precondition(result["probeFailure"] as? String == failure, "\(mode): \(result)")
        precondition(fds() <= baseline); noChildren()
    }
    precondition(observe("ok", cancelled: { true })["probeFailure"] as? String == "cancelled")
    let start = ProcessInfo.processInfo.systemUptime
    precondition(observe("hang", cancelled: {
        ProcessInfo.processInfo.systemUptime - start > 0.05
    })["probeFailure"] as? String == "cancelled")
    precondition(ProcessInfo.processInfo.systemUptime - start < 1)
    precondition(observe("ok")["desktopState"] as? String == "unlocked")
    precondition(fds() <= baseline); noChildren()
}
print("Session probe resource fixtures passed: \(iterations) successes, errors, deadlines, cancellation, reaping; fds=\(fds()) baseline=\(baseline)")
'''
if args.idle_only:
    fixture = r'''
func fds() -> Int { (0..<128).filter { fcntl(Int32($0), F_GETFD) >= 0 }.count }
var limit = rlimit(rlim_cur: 128, rlim_max: 128)
precondition(setrlimit(RLIMIT_NOFILE, &limit) == 0)
let pooled = CommandLine.arguments.contains("pooled")
let initial = fds()
for i in 1...Int(CommandLine.arguments[2])! {
    let value = pooled ? autoreleasepool { nativeSessionObservation() } : nativeSessionObservation()
    if i % 25 == 0 || value["desktopState"] as? String != "unlocked" {
        print("probes=\(i) fds=\(fds()) baseline=\(initial) state=\(value["desktopState"] ?? "absent")")
        fflush(stdout)
    }
    if value["desktopState"] as? String != "unlocked" { exit(1) }
}
precondition(fds() == initial)
'''
if args.spawn_boundary:
    fixture = r'''
func fds() -> Int { (0..<20000).filter { fcntl(Int32($0), F_GETFD) >= 0 }.count }
var limit = rlimit()
precondition(getrlimit(RLIMIT_NOFILE, &limit) == 0)
precondition(limit.rlim_cur > 13000, "requires an already sufficient process limit")
print("limit=\(limit.rlim_cur) baseline=\(fds())")
var readers: [Int32] = []
defer { for fd in readers { close(fd) } }
for target in [100, 1000, 10000, 10230, 10240, 10300, 10600, 12000] {
    while readers.count < target {
        var pair: [Int32] = [0, 0]
        precondition(pipe(&pair) == 0)
        close(pair[1]); readers.append(pair[0])
    }
    var actions: posix_spawn_file_actions_t? = nil
    precondition(posix_spawn_file_actions_init(&actions) == 0)
    let high = readers.last!
    let duplicated = posix_spawn_file_actions_adddup2(&actions, high, 1)
    posix_spawn_file_actions_destroy(&actions)
    // Check the actual OS boundary separately from Foundation and the probe.
    precondition(duplicated == (high >= OPEN_MAX ? EBADF : 0))
    var spawnError = 0
    do {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/true")
        try process.run(); process.waitUntilExit()
    } catch { spawnError = (error as NSError).code }
    let state = nativeSessionObservation()
    print("prefill=\(target) highFD=\(high) adddup2=\(duplicated) spawnError=\(spawnError) fds=\(fds()) state=\(state["desktopState"] ?? "absent")")
    fflush(stdout)
    if high >= OPEN_MAX {
        precondition(spawnError == Int(EBADF))
        precondition(state["desktopState"] as? String == "unknown")
    } else if target <= 10000 {
        precondition(spawnError == 0)
        precondition(state["desktopState"] as? String == "unlocked")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='mc-probe-resources-') as directory:
    path = Path(directory)
    (path / 'probe.c').write_text(child)
    subprocess.run(['xcrun', 'clang', str(path / 'probe.c'), '-o', str(path / 'ok')], check=True)
    for mode in ['nonzero', 'invalid', 'shape', 'large', 'hang', 'closed']:
        (path / mode).symlink_to('ok')
    (path / 'Contents/MacOS').mkdir(parents=True)
    (path / 'Contents/Resources').mkdir()
    (path / 'Contents/Resources/mc-session-probe').symlink_to(path / 'ok')
    (path / 'main.swift').write_text('import Foundation\nimport Darwin\n' + observer + fixture)
    subprocess.run(['xcrun', 'swiftc', '-O', str(path / 'main.swift'), '-o', str(path / 'Contents/MacOS/test')], check=True)
    subprocess.run([str(path / 'Contents/MacOS/test'), str(path), str(args.iterations), 'pooled' if args.caller_pool else 'unpooled'], check=True, timeout=min(7200, max(120, args.iterations)))
