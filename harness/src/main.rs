use insertion_harness::{
    Result, RunError, ffi::ControllerInProcessC, plant::PlantPython, runner,
    serial::ControllerSerial, types::Controller,
};
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
};

fn main() {
    if let Err(error) = execute() {
        eprintln!("INVALID: {error}");
        std::process::exit(2);
    }
}
fn execute() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let mut options = HashMap::new();
    while let Some(key) = args.next() {
        if key == "--version" {
            println!("{}", runner::runtime()?);
            return Ok(());
        }
        if ![
            "--backend",
            "--python",
            "--build",
            "--output",
            "--contact-profile",
            "--port",
            "--address",
            "--board-evidence",
        ]
        .contains(&key.as_str())
        {
            return Err(RunError(format!("unknown option {key}")));
        }
        let value = args
            .next()
            .ok_or_else(|| RunError(format!("missing value for {key}")))?;
        if options.insert(key, value).is_some() {
            return Err(RunError("duplicate option".into()));
        }
    }
    let get = |key: &str| {
        options
            .get(key)
            .map(String::as_str)
            .ok_or_else(|| RunError(format!("required {key}")))
    };
    let profile = get("--contact-profile")?;
    insertion_harness::require(
        matches!(profile, "primary" | "paper_effective"),
        "unknown contact profile",
    )?;
    let directory = PathBuf::from(get("--build")?).canonicalize()?;
    let build: serde_json::Value =
        serde_json::from_slice(&std::fs::read(directory.join("build.json"))?)?;
    let source = build["controller_source_sha256"]
        .as_str()
        .ok_or_else(|| RunError("missing controller source hash".into()))?
        .to_owned();
    let repo = std::env::current_dir()?;
    insertion_harness::require(
        repo.join("sim/plant.py").is_file(),
        "run from the repository root",
    )?;
    let mut current_source = std::fs::read(repo.join("firmware/ctrl/controller.c"))?;
    current_source.push(0);
    current_source.extend(std::fs::read(repo.join("firmware/ctrl/controller.h"))?);
    insertion_harness::require(
        insertion_harness::sha256(&current_source) == source,
        "stale controller build",
    )?;
    let mut controller: Box<dyn Controller> = match get("--backend")? {
        "ffi" => Box::new(ControllerInProcessC::new(&directory)?),
        "serial" => {
            let receipt: serde_json::Value =
                serde_json::from_slice(&std::fs::read(get("--board-evidence")?)?)?;
            let mut serial = ControllerSerial::serial(get("--port")?, source)?;
            serial.bind_hardware(&build, &receipt)?;
            Box::new(serial)
        }
        "tcp" => Box::new(ControllerSerial::tcp(get("--address")?, source)?),
        _ => return Err(RunError("unknown controller backend".into())),
    };
    let mut plant = PlantPython::new(Path::new(get("--python")?), &repo, profile)?;
    let report = runner::run(&mut plant, controller.as_mut(), Path::new(get("--output")?))?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
