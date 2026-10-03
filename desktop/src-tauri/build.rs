use std::{env, fs, path::PathBuf, process::Command};
fn run(command: &mut Command) {
    assert!(
        command.status().expect("native build tool").success(),
        "native build failed"
    );
}
fn main() {
    let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let repository = root.join("../..");
    let revision = env::var("GITHUB_SHA").unwrap_or_else(|_| {
        String::from_utf8(
            Command::new("git")
                .args(["rev-parse", "HEAD"])
                .current_dir(&repository)
                .output()
                .expect("source identity")
                .stdout,
        )
        .unwrap()
        .trim()
        .to_owned()
    });
    let config: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("tauri.conf.json")).unwrap()).unwrap();
    println!("cargo:rerun-if-env-changed=GITHUB_SHA");
    println!("cargo:rerun-if-env-changed=PYTHON");
    // Exported source builds can supply GITHUB_SHA without installing Git.
    // When Git is available, retain precise rebuild tracking for local commits.
    if let Ok(branch) = Command::new("git")
        .args(["symbolic-ref", "-q", "HEAD"])
        .current_dir(&repository)
        .output()
    {
        let branch = String::from_utf8(branch.stdout).unwrap();
        for name in ["HEAD", branch.trim()]
            .into_iter()
            .filter(|v| !v.is_empty())
        {
            if let Ok(path) = Command::new("git")
                .args(["rev-parse", "--path-format=absolute", "--git-path", name])
                .current_dir(&repository)
                .output()
            {
                if path.status.success() {
                    println!(
                        "cargo:rerun-if-changed={}",
                        String::from_utf8(path.stdout).unwrap().trim()
                    );
                }
            }
        }
    }
    for path in [
        "client",
        "bin/machine-control",
        "providers/claims",
        "platforms/macos/bin/machost",
        "platforms/macos/host",
        "platforms/windows/host",
        "platforms/linux/host",
        "desktop/python-runtime.lock.json",
        "desktop/scripts/prepare-cli.py",
        "desktop/native/windows-launch.py",
        "desktop/native/windows-path.py",
        "desktop/python-licenses",
    ] {
        println!("cargo:rerun-if-changed={}", repository.join(path).display());
    }
    let python = env::var_os("PYTHON")
        .unwrap_or_else(|| if cfg!(windows) { "python" } else { "python3" }.into());
    let cli = root.join("native/mc-cli");
    if cli.join("package.cat").is_file() || cli.join("files.json.sig").is_file() {
        let staged: serde_json::Value =
            serde_json::from_slice(&fs::read(cli.join("client-runtime.json")).unwrap()).unwrap();
        assert!(
            staged["sourceRevision"] == revision
                && staged["target"] == env::var("TARGET").unwrap()
                && staged["version"] == config["version"],
            "Pre-signed CLI identity mismatch; restage and sign the correct payload"
        );
        run(Command::new(&python)
            .arg(repository.join("desktop/scripts/cli-payload.py"))
            .arg("verify")
            .arg(cli));
    } else {
        run(Command::new(&python)
            .arg(repository.join("desktop/scripts/prepare-cli.py"))
            .args(["--target", &env::var("TARGET").unwrap()])
            .args(["--version", config["version"].as_str().unwrap()])
            .args(["--revision", &revision]));
    }
    if env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos") {
        let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
        let sources = root.join("../../platforms/macos/resident/Sources/macui");
        let native = root.join("native");
        let sudo = root.join("../../platforms/macos/sudo");
        for file in [
            "Cargo.toml",
            "Cargo.lock",
            "build.rs",
            "Native.swift",
            "src/lib.rs",
            "src/macos.rs",
            "src/main.rs",
            "src/askpass.rs",
        ] {
            println!("cargo:rerun-if-changed={}", sudo.join(file).display());
        }
        let sudo_target = native.join("sudo-build");
        let rust_target = env::var("TARGET").unwrap();
        run(
            Command::new(env::var_os("CARGO").unwrap_or_else(|| "cargo".into()))
                .args(["build", "--locked", "--release", "--manifest-path"])
                .arg(sudo.join("Cargo.toml"))
                .args(["--target", &rust_target, "--target-dir"])
                .arg(&sudo_target),
        );
        fs::create_dir_all(&native).unwrap();
        for binary in ["mc-sudo", "mc-sudo-askpass"] {
            fs::copy(
                sudo_target.join(&rust_target).join("release").join(binary),
                native.join(binary),
            )
            .unwrap();
        }
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
        fs::write(native.join("Info.plist"), format!("<?xml version=\"1.0\"?><plist version=\"1.0\"><dict><key>MCSourceRevision</key><string>{revision}</string><key>MCNativeSudoVersion</key><integer>1</integer><key>MCClientProtocol</key><integer>1</integer></dict></plist>")).unwrap();
        println!("cargo:rerun-if-env-changed=GITHUB_SHA");

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
    if env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("linux") {
        let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
        let identity = root.join("native/linux-runtime/desktop-runtime.json");
        println!("cargo:rerun-if-changed={}", identity.display());
        let value: serde_json::Value =
            serde_json::from_slice(&fs::read(identity).expect("staged Linux runtime")).unwrap();
        let revision = value["sourceRevision"].as_str().unwrap();
        assert!(revision.len() == 40 && revision.bytes().all(|b| b.is_ascii_hexdigit()));
        println!("cargo:rustc-env=MC_SOURCE_REVISION={revision}");
        let purpose = value
            .get("purpose")
            .and_then(|v| v.as_str())
            .unwrap_or("candidate");
        assert!(matches!(purpose, "candidate" | "update_sender_fixture"));
        println!("cargo:rustc-env=MC_DESKTOP_PURPOSE={purpose}");
    }
    tauri_build::build();
}
