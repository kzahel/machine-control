use std::{env, path::PathBuf, process::Command};

fn main() {
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("macos") {
        return;
    }
    let output = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    let arch = if env::var("CARGO_CFG_TARGET_ARCH").unwrap() == "aarch64" {
        "arm64"
    } else {
        "x86_64"
    };
    let status = Command::new("xcrun")
        .args([
            "swiftc",
            "-O",
            "-emit-library",
            "-static",
            "-module-name",
            "MCSudo",
            "-target",
            &format!("{arch}-apple-macos13.0"),
            "Native.swift",
            "-o",
        ])
        .arg(output.join("libMCSudo.a"))
        .status()
        .expect("Swift compiler required on macOS");
    assert!(status.success(), "native sudo helper build failed");
    let sdk = Command::new("xcrun")
        .args(["--show-sdk-path"])
        .output()
        .unwrap();
    let sdk = String::from_utf8(sdk.stdout).unwrap();
    println!("cargo:rerun-if-changed=Native.swift");
    println!("cargo:rustc-link-search=native={}", output.display());
    println!(
        "cargo:rustc-link-search=native={}/usr/lib/swift",
        sdk.trim()
    );
    println!("cargo:rustc-link-lib=static=MCSudo");
    println!("cargo:rustc-link-lib=swiftCore");
    for framework in ["AppKit", "Foundation", "Security", "CoreGraphics"] {
        println!("cargo:rustc-link-lib=framework={framework}");
    }
    println!("cargo:rustc-link-arg=-Wl,-rpath,/usr/lib/swift");
}
