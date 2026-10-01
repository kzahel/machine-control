use std::{env, fs, path::PathBuf, process::Command};
fn run(command: &mut Command) {
    assert!(
        command.status().expect("native build tool").success(),
        "native build failed"
    );
}
fn main() {
    if env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos") {
        let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
        let sources = root.join("../../platforms/macos/resident/Sources/macui");
        let native = root.join("native");
        let framework = native.join("MCResident.framework");
        let revision = env::var("GITHUB_SHA").unwrap_or_else(|_| {
            String::from_utf8(
                Command::new("git")
                    .args(["rev-parse", "HEAD"])
                    .output()
                    .unwrap()
                    .stdout,
            )
            .unwrap()
            .trim()
            .to_owned()
        });
        assert!(revision.len() == 40 && revision.bytes().all(|b| b.is_ascii_hexdigit()));
        fs::create_dir_all(&native).unwrap();
        fs::write(native.join("Info.plist"), format!("<?xml version=\"1.0\"?><plist version=\"1.0\"><dict><key>MCSourceRevision</key><string>{revision}</string></dict></plist>")).unwrap();
        println!("cargo:rerun-if-env-changed=GITHUB_SHA");
        for name in ["HEAD", "refs/heads/main"] {
            let path = Command::new("git")
                .args(["rev-parse", "--git-path", name])
                .output()
                .unwrap();
            println!(
                "cargo:rerun-if-changed={}",
                String::from_utf8(path.stdout).unwrap().trim()
            );
        }

        fs::create_dir_all(&framework).unwrap();
        let arch = if env::var("TARGET").unwrap().starts_with("aarch64") {
            "arm64"
        } else {
            "x86_64"
        };
        let target = format!("{arch}-apple-macos13.0");
        let mut swift = Command::new("xcrun");
        swift
            .args([
                "swiftc",
                "-O",
                "-emit-library",
                "-module-name",
                "MCResident",
                "-target",
                &target,
                "-Xlinker",
                "-install_name",
                "-Xlinker",
                "@rpath/MCResident.framework/MCResident",
                "-o",
            ])
            .arg(framework.join("MCResident"));
        let mut files: Vec<_> = fs::read_dir(&sources)
            .unwrap()
            .map(|e| e.unwrap().path())
            .filter(|p| {
                p.extension().is_some_and(|e| e == "swift")
                    && p.file_name().unwrap() != "main.swift"
            })
            .collect();
        files.sort();
        for file in files {
            println!("cargo:rerun-if-changed={}", file.display());
            swift.arg(file);
        }
        let bridge = root.join("../native/Bridge.swift");
        println!("cargo:rerun-if-changed={}", bridge.display());
        swift.arg(bridge);
        run(&mut swift);
        fs::write(framework.join("Info.plist"), r#"<?xml version="1.0"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>CFBundleIdentifier</key><string>org.machine-control.resident.framework</string><key>CFBundleExecutable</key><string>MCResident</string><key>CFBundlePackageType</key><string>FMWK</string><key>CFBundleVersion</key><string>1</string></dict></plist>"#).unwrap();
        let probe = root.join("../../platforms/macos/guests/macos/unlock/Probe.m");
        println!("cargo:rerun-if-changed={}", probe.display());
        run(Command::new("xcrun")
            .args([
                "clang",
                "-O2",
                "-target",
                &target,
                "-fobjc-arc",
                "-Wno-unused-function",
                "-framework",
                "Foundation",
                "-framework",
                "IOKit",
                "-o",
            ])
            .arg(native.join("mc-session-probe"))
            .arg(probe));
        println!("cargo:rustc-link-search=framework={}", native.display());
        println!("cargo:rustc-link-lib=framework=MCResident");
        println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path/../Frameworks");
        println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path/../../native");
        println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path/../../../native");
    }
    if env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
        let identity = root.join("native/runtime/desktop-runtime.json");
        println!("cargo:rerun-if-changed={}", identity.display());
        let value: serde_json::Value =
            serde_json::from_slice(&fs::read(identity).expect("staged Windows runtime")).unwrap();
        let revision = value["sourceRevision"].as_str().unwrap();
        assert!(revision.len() == 40 && revision.bytes().all(|b| b.is_ascii_hexdigit()));
        println!("cargo:rustc-env=MC_SOURCE_REVISION={revision}");
    }
    tauri_build::build();
}
