//! Board transfer, no simulated timing and no plant reimplementation.
use crate::{
    Result,
    protocol::{self, Frame},
    require,
    serial::{ControllerSerial, new_session},
    types::Controller,
};
use serde_json::{Value, json};
use std::{
    fs::{self, File},
    io::{BufWriter, Write},
    path::Path,
    time::{Duration, Instant},
};

pub fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = !0u32;
    for byte in bytes {
        crc ^= *byte as u32;
        for _ in 0..8 {
            crc = (crc >> 1) ^ if crc & 1 != 0 { 0xedb88320 } else { 0 };
        }
    }
    !crc
}
fn log(controller: &mut ControllerSerial, output: &mut impl Write) -> Result<()> {
    for event in controller.take_transport_events() {
        serde_json::to_writer(&mut *output, &event)?;
        output.write_all(b"\n")?;
    }
    output.flush()?;
    Ok(())
}
fn request(
    controller: &mut ControllerSerial,
    log_file: &mut impl Write,
    session: u32,
    kind: u8,
    payload: Vec<u8>,
) -> Result<Frame> {
    let response = controller.exchange(
        Frame {
            kind,
            session,
            payload,
        },
        Duration::from_secs(2),
    );
    log(controller, log_file)?;
    let frame = response?;
    require(frame.session == session, "replay session mismatch")?;
    Ok(frame)
}
pub fn summary_words(frame: &Frame) -> Result<Vec<u32>> {
    require(
        frame.kind == 0x89 && frame.payload.len() == 84,
        "invalid replay summary",
    )?;
    Ok(frame
        .payload
        .as_chunks::<4>()
        .0
        .iter()
        .map(|v| u32::from_le_bytes(*v))
        .collect())
}
fn fetch(
    controller: &mut ControllerSerial,
    log_file: &mut impl Write,
    session: u32,
    kind: u8,
    count: u32,
    output: &mut impl Write,
) -> Result<Vec<u8>> {
    let width = if kind == 8 { 17 } else { 8 };
    let mut bytes = Vec::new();
    for first in (0..count).step_by(10) {
        let n = (count - first).min(10) as u16;
        let mut p = first.to_le_bytes().to_vec();
        p.extend_from_slice(&n.to_le_bytes());
        let frame = request(controller, log_file, session, kind, p.clone())?;
        require(
            frame.kind == kind + 0x80
                && frame.payload.len() == 6 + n as usize * width
                && frame.payload[..6] == p,
            "replay fetch range/length mismatch",
        )?;
        output.write_all(&frame.payload[6..])?;
        output.flush()?;
        bytes.extend_from_slice(&frame.payload[6..]);
    }
    Ok(bytes)
}
pub fn run(
    controller: &mut ControllerSerial,
    build: &Value,
    receipt: &Value,
    inputs: Option<&[u8]>,
    output: &Path,
) -> Result<Value> {
    fs::create_dir_all(output)?;
    require(
        fs::read_dir(output)?.next().is_none(),
        "replay output must be empty",
    )?;
    let mut wire = BufWriter::new(File::create(output.join("transport.jsonl"))?);
    let mut report = json!({"status":"INVALID","hardware_timing_verified":false,
        "runtime":crate::runner::runtime()?, "firmware_binary_sha256":build["binary_sha256"]});
    let result: Result<()> = (|| {
        controller.bind_hardware(build, receipt)?;
        let hello = controller.hello();
        log(controller, &mut wire)?;
        hello?;
        report["controller"] = controller.provenance();
        let caps = report["controller"]["info"]["capabilities"]
            .as_u64()
            .unwrap_or(0);
        require(caps & 2 == 2, "board has no replay capability")?;
        let session = new_session()?;
        report["session"] = json!(session);
        let mut reset = vec![1];
        reset.extend_from_slice(&8000u32.to_le_bytes());
        protocol::ack(
            &request(controller, &mut wire, session, 2, reset)?,
            session,
            2,
        )?;
        let frame = request(controller, &mut wire, session, 9, vec![])?;
        let first = summary_words(&frame)?;
        require(
            first[16] == receipt["binary_crc32"] && first[17] == build["binary_bytes"],
            "runtime Flash CRC/length differs from verified binary",
        )?;
        report["identity_summary_words"] = json!(first);
        if let Some(inputs) = inputs {
            require(
                inputs.len() == 8000 * 29,
                "replay input must contain all 8000 wire payloads",
            )?;
            let input_crc = crc32(inputs);
            report["input_sha256"] = json!(crate::sha256(inputs));
            report["input_crc32"] = json!(input_crc);
            for (tick, p) in inputs.as_chunks::<29>().0.iter().enumerate() {
                require(
                    u32::from_le_bytes(p[..4].try_into().unwrap()) == tick as u32,
                    "stored input tick mismatch",
                )?;
                let frame = request(controller, &mut wire, session, 5, p.to_vec())?;
                require(
                    frame.kind == 0x85
                        && frame.payload.len() == 5
                        && frame.payload[..4] == p[..4]
                        && frame.payload[4] == 0,
                    "replay load failed",
                )?;
            }
            let loaded = summary_words(&request(controller, &mut wire, session, 9, vec![])?)?;
            require(
                loaded[0] == 0 && loaded[1] == 8000 && loaded[4] == input_crc,
                "whole input RAM CRC/count mismatch",
            )?;
            protocol::ack(
                &request(
                    controller,
                    &mut wire,
                    session,
                    6,
                    input_crc.to_le_bytes().to_vec(),
                )?,
                session,
                6,
            )?;
            let host_start = Instant::now();
            // No serial request while the nominal eight-second timer loop executes.
            std::thread::sleep(Duration::from_millis(8100));
            let state = request(controller, &mut wire, session, 7, vec![])?;
            require(
                state.kind == 0x87 && state.payload.len() == 9,
                "invalid replay state",
            )?;
            report["host_ack_to_state_seconds"] = json!(host_start.elapsed().as_secs_f64());
            report["host_elapsed_scope"] = json!(
                "includes deliberate 8.1s quiet wait, USB/OS and status latency; not a clock-accuracy gate"
            );
            let words = summary_words(&request(controller, &mut wire, session, 9, vec![])?)?;
            report["summary_words"] = json!(words);
            require(
                state.payload[0] as u32 == words[0]
                    && u32::from_le_bytes(state.payload[1..5].try_into().unwrap()) == words[2]
                    && u32::from_le_bytes(state.payload[5..9].try_into().unwrap()) == words[3]
                    && words[16] == first[16]
                    && words[17] == first[17],
                "status/summary or runtime identity changed",
            )?;
            require(
                words[2] <= 8000 && matches!(words[0], 2 | 3),
                "replay not stopped/completed",
            )?;
            let mut commands = File::create(output.join("commands.bin"))?;
            let command_bytes = fetch(controller, &mut wire, session, 8, words[2], &mut commands)?;
            let mut timing = File::create(output.join("timing.bin"))?;
            let timing_bytes = fetch(controller, &mut wire, session, 10, words[2], &mut timing)?;
            require(
                crc32(&command_bytes) == words[5] && crc32(&timing_bytes) == words[20],
                "whole telemetry CRC mismatch",
            )?;
            require(
                words[0] == 2 && words[2] == 8000 && words[6] == 8000,
                "incomplete board replay; partial evidence preserved",
            )?;
            protocol::ack(
                &request(
                    controller,
                    &mut wire,
                    session,
                    4,
                    8000u32.to_le_bytes().to_vec(),
                )?,
                session,
                4,
            )?;
            report["status"] = json!("COMPLETE");
            report["command_telemetry_sha256"] = json!(crate::sha256(&command_bytes));
            report["timing_sha256"] = json!(crate::sha256(&timing_bytes));
        } else {
            report["status"] = json!("IDENTITY_VERIFIED");
        }
        Ok(())
    })();
    log(controller, &mut wire)?;
    if let Err(error) = &result {
        report["error"] = json!(error.to_string());
    }
    fs::write(
        output.join("completion.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    result?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::Read,
        net::{TcpListener, TcpStream},
        thread,
    };

    fn receive(stream: &mut TcpStream) -> Frame {
        let mut bytes = vec![0; 10];
        stream.read_exact(&mut bytes).unwrap();
        let n = u16::from_le_bytes([bytes[4], bytes[5]]) as usize;
        bytes.resize(n + 12, 0);
        stream.read_exact(&mut bytes[10..]).unwrap();
        Frame::decode(&bytes).unwrap()
    }

    // Test-only TCP fixture: never available in the board-link executable.
    fn exercise_transfer(corrupt_runtime_crc: bool) {
        let root = std::env::temp_dir().join(format!(
            "vv-synthetic-replay-{}-{}",
            std::process::id(),
            new_session().unwrap()
        ));
        fs::create_dir(&root).unwrap();
        let readback = root.join("readback.bin");
        fs::write(&readback, b"synthetic-test-image").unwrap();
        let image_crc = crc32(b"synthetic-test-image");
        let build = json!({"binary_sha256":crate::sha256(b"synthetic-test-image"),
            "elf_sha256":"c".repeat(64),"git_commit":"a".repeat(40),
            "binary_bytes":20,"controller_source_sha256":"b".repeat(64),
            "configured_hardware":{"core_hz":520000000,"timer_hz":260000000}});
        let receipt = json!({"status":"FLASH_VERIFIED","binary_sha256":build["binary_sha256"],
            "elf_sha256":build["elf_sha256"],"firmware_git":build["git_commit"],
            "controller_source_sha256":build["controller_source_sha256"],"readback_file":readback,
            "binary_crc32":image_crc,"identity":{"unique_id_hex":"01".repeat(12),
                "mcu_idcode":0x483,"arm_cpuid":0x410fc271}});
        let mut inputs = vec![];
        let mut commands = vec![];
        let mut timings = vec![];
        for k in 0u32..8000 {
            inputs.extend_from_slice(&k.to_le_bytes());
            inputs.extend_from_slice(&(k * 1000).to_le_bytes());
            inputs.extend_from_slice(&[0; 21]);
            commands.extend_from_slice(&k.to_le_bytes());
            commands.extend_from_slice(&(-0.001f32).to_le_bytes());
            commands.extend_from_slice(&(k * 520000).to_le_bytes());
            commands.extend_from_slice(&5200u32.to_le_bytes());
            commands.push(0);
            timings.extend_from_slice(&100u32.to_le_bytes());
            timings.extend_from_slice(&5500u32.to_le_bytes());
        }
        let expected_commands = commands.clone();
        let expected_timings = timings.clone();
        let expected_inputs = inputs.clone();
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap().to_string();
        let peer = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream.set_nodelay(true).unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(20)))
                .unwrap();
            let mut loaded = 0;
            let mut started = false;
            let mut session = 0;
            loop {
                let req = receive(&mut stream);
                let (kind, payload) = match req.kind {
                    1 => {
                        assert_eq!(req.session, 0);
                        let mut p = vec![1, 1, 3, 0];
                        for word in [520000000u32, 260000000, 8000] {
                            p.extend_from_slice(&word.to_le_bytes());
                        }
                        p.extend_from_slice(&[b'a'; 40]);
                        p.extend_from_slice(&[b'b'; 64]);
                        p.extend_from_slice(&[1; 12]);
                        p.extend_from_slice(&0x483u32.to_le_bytes());
                        p.extend_from_slice(&0x410fc271u32.to_le_bytes());
                        (0x81, p)
                    }
                    2 => {
                        assert_eq!(req.payload, [1, 0x40, 0x1f, 0, 0]);
                        assert_ne!(req.session, 0);
                        session = req.session;
                        (0x82, vec![2, 0])
                    }
                    5 => {
                        assert!(!started);
                        assert_eq!(req.payload, expected_inputs[loaded * 29..(loaded + 1) * 29]);
                        let mut p = (loaded as u32).to_le_bytes().to_vec();
                        p.push(0);
                        loaded += 1;
                        (0x85, p)
                    }
                    6 => {
                        assert_eq!(loaded, 8000);
                        assert_eq!(req.payload, crc32(&expected_inputs).to_le_bytes());
                        started = true;
                        (0x82, vec![6, 0])
                    }
                    7 => {
                        assert!(started);
                        let mut p = vec![2];
                        p.extend_from_slice(&8000u32.to_le_bytes());
                        p.extend_from_slice(&0u32.to_le_bytes());
                        (0x87, p)
                    }
                    9 => {
                        let mut words = [0u32; 21];
                        words[0] = if started { 2 } else { 0 };
                        words[1] = loaded as u32;
                        if started {
                            words[2] = 8000;
                            words[6] = 8000;
                        }
                        words[4] = crc32(&expected_inputs[..loaded * 29]);
                        words[5] = crc32(&commands);
                        words[16] = image_crc ^ u32::from(corrupt_runtime_crc);
                        words[17] = 20;
                        words[20] = crc32(&timings);
                        (0x89, words.iter().flat_map(|w| w.to_le_bytes()).collect())
                    }
                    8 | 10 => {
                        assert!(started);
                        let first =
                            u32::from_le_bytes(req.payload[..4].try_into().unwrap()) as usize;
                        let count =
                            u16::from_le_bytes(req.payload[4..].try_into().unwrap()) as usize;
                        assert!((1..=10).contains(&count));
                        let (data, width) = if req.kind == 8 {
                            (&commands, 17)
                        } else {
                            (&timings, 8)
                        };
                        let mut p = req.payload.clone();
                        p.extend_from_slice(&data[first * width..(first + count) * width]);
                        (req.kind + 0x80, p)
                    }
                    4 => {
                        assert!(started);
                        assert_eq!(req.payload, 8000u32.to_le_bytes());
                        (0x82, vec![4, 0])
                    }
                    _ => panic!("unexpected request"),
                };
                if req.kind != 1 {
                    assert_eq!(req.session, session);
                }
                let bytes = Frame {
                    kind,
                    session: req.session,
                    payload,
                }
                .encode()
                .unwrap();
                // Exercise fragmented records across the actual codec/read loop.
                for part in bytes.chunks(37) {
                    stream.write_all(part).unwrap();
                }
                if req.kind == 4 || (corrupt_runtime_crc && req.kind == 9) {
                    break;
                }
            }
        });
        let mut controller = ControllerSerial::synthetic_hardware(&address, "b".repeat(64));
        let result = run(
            &mut controller,
            &build,
            &receipt,
            Some(&inputs),
            &root.join("raw"),
        );
        peer.join().unwrap();
        let saved: Value =
            serde_json::from_slice(&fs::read(root.join("raw/completion.json")).unwrap()).unwrap();
        assert_eq!(saved["hardware_timing_verified"], false);
        if corrupt_runtime_crc {
            assert!(result.is_err());
            assert_eq!(saved["status"], "INVALID");
            assert!(saved["error"].as_str().unwrap().contains("Flash CRC"));
            assert!(!root.join("raw/commands.bin").exists());
        } else {
            assert_eq!(result.unwrap()["status"], "COMPLETE");
            assert_eq!(
                fs::read(root.join("raw/commands.bin")).unwrap(),
                expected_commands
            );
            assert_eq!(
                fs::read(root.join("raw/timing.bin")).unwrap(),
                expected_timings
            );
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn complete_fragmented_replay_transfer_is_checked() {
        exercise_transfer(false);
    }
    #[test]
    fn runtime_flash_mismatch_preserves_invalid_evidence() {
        exercise_transfer(true);
    }
    #[test]
    fn standard_crc_and_bounded_summary() {
        assert_eq!(crc32(b"123456789"), 0xcbf43926);
        assert_eq!(crc32(b""), 0);
        let mut frame = Frame {
            kind: 0x89,
            session: 1,
            payload: vec![0; 84],
        };
        assert_eq!(summary_words(&frame).unwrap().len(), 21);
        frame.payload.pop();
        assert!(summary_words(&frame).is_err());
        frame.payload.push(0);
        frame.kind = 0x87;
        assert!(summary_words(&frame).is_err());
    }
}
