// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MachineControlResident",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "macui",
            path: "Sources/macui",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("ApplicationServices"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("SystemConfiguration"),
                .linkedFramework("ScreenCaptureKit"),
                .linkedFramework("ServiceManagement"),
            ]),
        .testTarget(
            name: "macuiTests",
            dependencies: ["macui"],
            path: "Tests/macuiTests"),
    ]
)
