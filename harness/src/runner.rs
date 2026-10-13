use crate::{
    Result, require, sha256,
    types::{Controller, Plant},
};
use serde_json::{Value, json};
use std::{
    fs::{self, File, OpenOptions},
    io::{BufWriter, Write},
    path::Path,
    time::Instant,
};

pub fn runtime() -> Result<Value> {
    Ok(json!({"rustc":env!("VV_RUSTC"),"target":env!("VV_TARGET"),
        "executable_sha256":sha256(&fs::read(std::env::current_exe()?)?)}))
}
fn file(directory: &Path, name: &str) -> Result<BufWriter<File>> {
    Ok(BufWriter::new(
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(directory.join(name))?,
    ))
}
fn transport(controller: &mut dyn Controller, log: &mut impl Write) -> Result<()> {
    for event in controller.take_transport_events() {
        serde_json::to_writer(&mut *log, &event)?;
        log.write_all(b"\n")?;
    }
    Ok(())
}

pub fn run(
    plant: &mut dyn Plant,
    controller: &mut dyn Controller,
    directory: &Path,
) -> Result<Value> {
    fs::create_dir_all(directory)?;
    require(
        fs::read_dir(directory)?.next().is_none(),
        "output directory must be empty",
    )?;
    let mut trace = file(directory, "trace.jsonl")?;
    let mut truth = file(directory, "truth.jsonl")?;
    let mut wall = file(directory, "wall_time.csv")?;
    let mut wire = file(directory, "transport.jsonl")?;
    wall.write_all(b"tick,wall_time_ns\n")?;
    let mut completed = 0u32;
    let result: Result<()> = (|| {
        let mut sensors = plant.reset(42)?;
        require(
            sensors.tick == 0 && sensors.time_us == 0,
            "invalid initial plant tick",
        )?;
        controller.reset()?;
        transport(controller, &mut wire)?;
        for tick in 0..8000 {
            require(
                sensors.tick == tick && sensors.time_us == tick * 1000,
                "plant tick mismatch",
            )?;
            let start = Instant::now();
            let command = controller.command(&sensors)?;
            let record = plant.step(tick, command, 1000)?;
            let elapsed = start.elapsed().as_nanos();
            require(
                plant.truth() == record.truth,
                "plant evaluation record mismatch",
            )?;
            trace.write_all(&record.trace)?;
            truth.write_all(&record.truth)?;
            writeln!(wall, "{tick},{elapsed}")?;
            transport(controller, &mut wire)?;
            sensors = record.sensors;
            completed += 1;
        }
        controller.finish(completed)?;
        plant.finish(completed)?;
        Ok(())
    })();
    transport(controller, &mut wire)?;
    trace.flush()?;
    truth.flush()?;
    wall.flush()?;
    wire.flush()?;
    let report = json!({"status":if result.is_ok(){"COMPLETE"}else{"INVALID"},"completed_ticks":completed,
        "error":result.as_ref().err().map(ToString::to_string),"runtime":runtime()?,"controller":controller.provenance(),
        "trace_sha256":sha256(&fs::read(directory.join("trace.jsonl"))?),"truth_sha256":sha256(&fs::read(directory.join("truth.jsonl"))?),
        "wall_time_scope":"controller + Python IPC/evaluation + unchanged MuJoCo/sensors; excludes host artifact writes"});
    let mut output = file(directory, "completion.json")?;
    serde_json::to_writer_pretty(&mut output, &report)?;
    output.write_all(b"\n")?;
    output.flush()?;
    result?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        RunError,
        types::{Command, Sensors, StepRecord},
    };
    struct FakePlant {
        record: Vec<u8>,
    }
    fn sensors(tick: u32) -> Sensors {
        Sensors {
            tick,
            time_us: tick * 1000,
            sample_time_us: 0,
            sequence: 0,
            needle_position: 0.001,
            needle_velocity: 0.,
            surface_position: 0.,
            flags: 0,
        }
    }
    impl Plant for FakePlant {
        fn reset(&mut self, _seed: u64) -> Result<Sensors> {
            Ok(sensors(0))
        }
        fn step(&mut self, tick: u32, _command: Command, _dt: u32) -> Result<StepRecord> {
            self.record = b"{}\n".to_vec();
            Ok(StepRecord {
                sensors: sensors(tick + 1),
                trace: b"{}\n".to_vec(),
                truth: self.record.clone(),
            })
        }
        fn truth(&self) -> &[u8] {
            &self.record
        }
        fn finish(&mut self, _ticks: u32) -> Result<()> {
            Ok(())
        }
    }
    struct FailingController {
        at: u32,
    }
    impl Controller for FailingController {
        fn reset(&mut self) -> Result<()> {
            Ok(())
        }
        fn command(&mut self, s: &Sensors) -> Result<Command> {
            if s.tick == self.at {
                Err(RunError("injected transport failure".into()))
            } else {
                Ok(Command { force_n: 0. })
            }
        }
        fn finish(&mut self, _ticks: u32) -> Result<()> {
            Err(RunError("missing finish ACK".into()))
        }
        fn provenance(&self) -> Value {
            json!({"backend":"test"})
        }
    }
    #[test]
    fn partial_run_and_missing_finish_ack_are_invalid() {
        for failed_tick in [3, 8000] {
            let directory = std::env::temp_dir().join(format!(
                "insertion-rust-failure-{}-{failed_tick}",
                std::process::id()
            ));
            // create_dir fails on collision: never erase pre-existing data.
            fs::create_dir(&directory).unwrap();
            let mut plant = FakePlant { record: vec![] };
            let mut controller = FailingController { at: failed_tick };
            assert!(run(&mut plant, &mut controller, &directory).is_err());
            let report: Value =
                serde_json::from_slice(&fs::read(directory.join("completion.json")).unwrap())
                    .unwrap();
            assert_eq!(report["status"], "INVALID");
            assert_eq!(report["completed_ticks"], failed_tick);
            assert!(report["error"].is_string());
            assert_eq!(
                fs::read_to_string(directory.join("trace.jsonl"))
                    .unwrap()
                    .lines()
                    .count(),
                failed_tick as usize
            );
            assert!(run(&mut plant, &mut controller, &directory).is_err());
            fs::remove_dir_all(directory).unwrap();
        }
    }
}
