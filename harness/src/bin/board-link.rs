use insertion_harness::{Result, RunError, replay, require, serial::ControllerSerial};
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
};
fn execute() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let mut options = HashMap::new();
    while let Some(key) = args.next() {
        if key == "--list-ports" {
            let ports: Vec<Value> = serialport::available_ports().map_err(|e| RunError(e.to_string()))?
                .into_iter().map(|p| {
                    let usb = match p.port_type {
                        serialport::SerialPortType::UsbPort(u) => json!({"vid":u.vid,"pid":u.pid,
                            "serial_number":u.serial_number,"manufacturer":u.manufacturer,"product":u.product}),
                        _ => Value::Null };
                    json!({"port":p.port_name,"usb":usb})
                }).collect();
            println!("{}", serde_json::to_string_pretty(&ports)?);
            return Ok(());
        }
        require(
            [
                "--port",
                "--build",
                "--board-evidence",
                "--input",
                "--output",
            ]
            .contains(&key.as_str()),
            "unknown option",
        )?;
        let value = args
            .next()
            .ok_or_else(|| RunError("missing argument".into()))?;
        require(options.insert(key, value).is_none(), "duplicate argument")?;
    }
    let get = |key: &str| {
        options
            .get(key)
            .map(String::as_str)
            .ok_or_else(|| RunError(format!("required {key}")))
    };
    let build_path = PathBuf::from(get("--build")?);
    let build: Value = serde_json::from_slice(&fs::read(build_path.join("build.json"))?)?;
    require(
        insertion_harness::sha256(&fs::read(build_path.join("insertion-h723.bin"))?)
            == build["binary_sha256"],
        "binary checksum mismatch",
    )?;
    let receipt: Value = serde_json::from_slice(&fs::read(get("--board-evidence")?)?)?;
    let inputs = options.get("--input").map(fs::read).transpose()?;
    let source = build["controller_source_sha256"]
        .as_str()
        .ok_or_else(|| RunError("missing core hash".into()))?;
    let mut serial = ControllerSerial::serial(get("--port")?, source.into())?;
    let result = replay::run(
        &mut serial,
        &build,
        &receipt,
        inputs.as_deref(),
        Path::new(get("--output")?),
    )?;
    println!("{}", serde_json::to_string_pretty(&result)?);
    Ok(())
}
fn main() {
    if let Err(error) = execute() {
        eprintln!("INVALID: {error}");
        std::process::exit(2);
    }
}
