use std::{env, process::Command};

fn main() {
    let output = Command::new(env::var("RUSTC").expect("RUSTC"))
        .arg("-vV")
        .output()
        .expect("query rustc version");
    assert!(output.status.success());
    println!(
        "cargo::rustc-env=VV_RUSTC={}",
        String::from_utf8(output.stdout)
            .unwrap()
            .trim()
            .replace('\n', " | ")
    );
    println!("cargo::rustc-env=VV_TARGET={}", env::var("TARGET").unwrap());
    println!("cargo::rerun-if-changed=build.rs");
}
