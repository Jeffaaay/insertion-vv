use crate::{
    Result, RunError, require,
    types::{Command, Plant, Sensors, StepRecord},
};
use std::{
    io::{Read, Write},
    path::Path,
    process::{Child, Command as Process, Stdio},
    sync::mpsc::{self, Receiver, SyncSender},
    thread::{self, JoinHandle},
    time::Duration,
};

pub const IPC_LIMIT: usize = 1024 * 1024;

pub fn read_packet(reader: &mut impl Read) -> Result<Vec<u8>> {
    let mut header = [0u8; 4];
    reader.read_exact(&mut header)?;
    let size = u32::from_le_bytes(header) as usize;
    require((1..=IPC_LIMIT).contains(&size), "invalid IPC packet length")?;
    let mut data = vec![0; size];
    reader.read_exact(&mut data)?;
    Ok(data)
}

pub struct PlantPython {
    child: Child,
    sender: Option<SyncSender<Vec<u8>>>,
    receiver: Receiver<Result<Vec<u8>>>,
    workers: Vec<JoinHandle<()>>,
    timeout: Duration,
    last_truth: Vec<u8>,
}

impl PlantPython {
    pub fn new(python: &Path, repo: &Path, profile: &str) -> Result<Self> {
        let mut child = Process::new(python)
            .current_dir(repo)
            .args([
                "-u",
                "-m",
                "harness.plant_server",
                "--contact-profile",
                profile,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let mut input = child.stdin.take().unwrap();
        let mut output = child.stdout.take().unwrap();
        let (tx, requests) = mpsc::sync_channel::<Vec<u8>>(1);
        let (responses, rx) = mpsc::sync_channel(1);
        let errors = responses.clone();
        let writer = thread::spawn(move || {
            while let Ok(packet) = requests.recv() {
                let result = input
                    .write_all(&(packet.len() as u32).to_le_bytes())
                    .and_then(|_| input.write_all(&packet))
                    .and_then(|_| input.flush());
                if let Err(error) = result {
                    let _ = errors.try_send(Err(error.into()));
                    break;
                }
            }
        });
        let reader = thread::spawn(move || {
            loop {
                let packet = read_packet(&mut output);
                let failed = packet.is_err();
                if responses.try_send(packet).is_err() || failed {
                    break;
                }
            }
        });
        Ok(Self {
            child,
            sender: Some(tx),
            receiver: rx,
            workers: vec![reader, writer],
            timeout: Duration::from_secs(5),
            last_truth: Vec::new(),
        })
    }

    fn request(&mut self, packet: Vec<u8>, expected: u8) -> Result<Vec<u8>> {
        self.sender
            .as_ref()
            .ok_or_else(|| RunError("closed plant".into()))?
            .try_send(packet)
            .map_err(|e| RunError(e.to_string()))?;
        let response = self
            .receiver
            .recv_timeout(self.timeout)
            .map_err(|e| RunError(format!("plant timeout/disconnect: {e}")))??;
        if response.first() == Some(&0xff) {
            return Err(RunError(format!(
                "plant error: {}",
                String::from_utf8_lossy(&response[1..])
            )));
        }
        require(
            response.first() == Some(&expected),
            "unexpected IPC operation",
        )?;
        self.timeout = Duration::from_secs(2);
        Ok(response[1..].to_vec())
    }
}

impl Plant for PlantPython {
    fn reset(&mut self, seed: u64) -> Result<Sensors> {
        let mut request = vec![1];
        request.extend_from_slice(&seed.to_le_bytes());
        Sensors::from_ipc(&self.request(request, 0x81)?)
    }
    fn step(&mut self, tick: u32, command: Command, dt_us: u32) -> Result<StepRecord> {
        require(
            dt_us == 1000 && command.force_n.is_finite(),
            "invalid plant step",
        )?;
        let mut request = vec![2];
        request.extend_from_slice(&tick.to_le_bytes());
        request.extend_from_slice(&command.force_n.to_le_bytes());
        let data = self.request(request, 0x82)?;
        require(data.len() >= 49, "truncated plant step")?;
        let sensors = Sensors::from_ipc(&data[..41])?;
        require(
            sensors.tick == tick + 1 && sensors.time_us == (tick + 1) * 1000,
            "plant tick mismatch",
        )?;
        let mut offset = 41;
        let trace = take_record(&data, &mut offset)?;
        let truth = take_record(&data, &mut offset)?;
        require(offset == data.len(), "extra plant response bytes")?;
        for record in [&trace, &truth] {
            require(record.ends_with(b"\n"), "noncanonical record termination")?;
        }
        let t: serde_json::Value = serde_json::from_slice(&trace)?;
        let ground: serde_json::Value = serde_json::from_slice(&truth)?;
        require(
            t["sensors"]["tick"] == tick
                && ground["tick"] == tick
                && ground["time_us"] == tick * 1000,
            "record tick mismatch",
        )?;
        require(
            t["command"]["force_n"]
                .as_f64()
                .map(|n| (n as f32).to_bits())
                == Some(command.force_n.to_bits()),
            "record command mismatch",
        )?;
        self.last_truth = truth.clone();
        Ok(StepRecord {
            sensors,
            trace,
            truth,
        })
    }
    fn truth(&self) -> &[u8] {
        &self.last_truth
    }
    fn finish(&mut self, ticks: u32) -> Result<()> {
        let mut request = vec![3];
        request.extend_from_slice(&ticks.to_le_bytes());
        let response = self.request(request, 0x83)?;
        require(
            response == ticks.to_le_bytes(),
            "plant finish count mismatch",
        )
    }
}

fn take_record(data: &[u8], offset: &mut usize) -> Result<Vec<u8>> {
    require(
        data.len().saturating_sub(*offset) >= 4,
        "truncated record length",
    )?;
    let count = u32::from_le_bytes(data[*offset..*offset + 4].try_into().unwrap()) as usize;
    *offset += 4;
    require(
        count > 0 && count <= data.len().saturating_sub(*offset),
        "truncated/empty record",
    )?;
    let out = data[*offset..*offset + count].to_vec();
    *offset += count;
    Ok(out)
}

impl Drop for PlantPython {
    fn drop(&mut self) {
        self.sender.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
        for worker in self.workers.drain(..) {
            let _ = worker.join();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ipc_rejects_oversize_and_partial_data() {
        assert!(read_packet(&mut &0u32.to_le_bytes()[..]).is_err());
        assert!(read_packet(&mut &((IPC_LIMIT + 1) as u32).to_le_bytes()[..]).is_err());
        assert!(read_packet(&mut &[4, 0, 0, 0, 1, 2][..]).is_err());
        assert_eq!(
            read_packet(&mut &[2, 0, 0, 0, 1, 2][..]).unwrap(),
            vec![1, 2]
        );
    }
}
