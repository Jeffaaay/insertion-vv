use insertion_harness::{Result, RunError, require, types::Sensors};
use serde_json::Value;
use std::{collections::VecDeque, fs, path::Path};

pub struct FaultInjector {
    pub fault: String,
    level: f64,
    onset: u32,
    seed: String,
    ablation: String,
    tables: Value,
    pending: VecDeque<(u32, u32, u32, f64)>,
    last: Option<(u32, u32, f64)>,
    previous_capture: Option<f64>,
    frozen: Option<f64>,
    sequence: u32,
    last_due: u32,
}

impl FaultInjector {
    pub fn new(root: &Path, case: &Value) -> Result<Self> {
        let fault = case["fault"]
            .as_str()
            .ok_or(RunError("fault missing".into()))?;
        let level = case["level"]
            .as_f64()
            .ok_or(RunError("level missing".into()))?;
        if fault != "none" {
            let spec: Value =
                serde_json::from_slice(&fs::read(root.join(format!("faults/{fault}.yaml")))?)?;
            require(
                spec["levels"]
                    .as_array()
                    .is_some_and(|a| a.iter().any(|v| v.as_f64() == Some(level))),
                "unregistered severity",
            )?;
        }
        let ablation = case["ablation"]
            .as_str()
            .ok_or(RunError("ablation missing".into()))?;
        require(
            [
                "baseline",
                "no-delay",
                "no-jitter-model",
                "no-quantization",
                "no-noise",
                "no-dropped-frame-model",
            ]
            .contains(&ablation),
            "unregistered ablation",
        )?;
        Ok(Self {
            fault: fault.into(),
            level,
            onset: case["onset_ms"]
                .as_u64()
                .ok_or(RunError("onset missing".into()))? as u32,
            seed: case["seed"]
                .as_u64()
                .ok_or(RunError("seed missing".into()))?
                .to_string(),
            ablation: ablation.into(),
            tables: serde_json::from_slice(&fs::read(root.join("faults/random-v1.json"))?)?,
            pending: VecDeque::new(),
            last: None,
            previous_capture: None,
            frozen: None,
            sequence: 0,
            last_due: 0,
        })
    }

    fn active(&self, tick: u32) -> bool {
        if self.fault == "none" || tick < self.onset {
            return false;
        }
        match self.fault.as_str() {
            "F1" | "F6" => tick < self.onset + self.level as u32,
            "F2" | "F3" => tick < self.onset + 300,
            _ => true,
        }
    }

    pub fn skip(&self, tick: u32) -> bool {
        self.fault == "F6" && self.active(tick)
    }

    pub fn clip(&self, tick: u32, force: f64, peak: f64) -> f64 {
        if self.fault == "F7" && self.active(tick) {
            let limit = peak * (self.level / 100.0);
            force.clamp(-limit, limit)
        } else {
            force
        }
    }

    pub fn capture(&mut self, tick: u32, mut measured: f64) -> Result<Sensors> {
        require(measured.is_finite(), "nonfinite captured value")?;
        let previous = self.previous_capture;
        self.previous_capture = Some(measured);
        let seq = self.sequence;
        self.sequence += 1;
        let base = if self.ablation == "no-delay" { 0 } else { 15 };
        let mut delay = base;
        let mut drop = false;
        if self.active(tick) {
            match self.fault.as_str() {
                "F1" => {
                    if self.frozen.is_none() {
                        self.frozen = previous;
                    }
                    measured = self
                        .frozen
                        .ok_or(RunError("F1 needs prior capture".into()))?;
                }
                "F2" if self.ablation != "no-dropped-frame-model" => {
                    let word = self.tables["F2"][&self.seed][(tick - self.onset) as usize]
                        .as_u64()
                        .ok_or(RunError("missing random word".into()))?;
                    drop = word < (self.level * 4294967296.0 / 100.0).floor() as u64;
                }
                "F3" if self.ablation != "no-jitter-model" => {
                    delay = self.tables["F3"][&self.seed][base.to_string()][self.level.to_string()]
                        [(tick - self.onset) as usize]
                        .as_u64()
                        .ok_or(RunError("missing random delay".into()))?
                        as u32;
                }
                "F4" => {
                    drop = !tick.is_multiple_of(1000 / self.level as u32);
                }
                "F8" if self.ablation != "no-quantization" => {
                    let half = (1u32 << (self.level as u32 - 1)) as f64;
                    let lsb = 0.002 / (1u32 << self.level as u32) as f64;
                    let code = (measured / lsb).round_ties_even().clamp(-half, half - 1.0) as i64;
                    measured = code as f64 * lsb;
                }
                _ => {}
            }
        }
        if !drop {
            let due = (tick + delay).max(self.last_due);
            self.last_due = due;
            self.pending.push_back((due, tick * 1000, seq, measured));
        }
        let mut fresh = false;
        while self.pending.front().is_some_and(|p| p.0 <= tick) {
            let (_, sampled, sequence, value) = self.pending.pop_front().unwrap();
            self.last = Some((sampled, sequence, value));
            fresh = true;
        }
        let (sample_time_us, sequence, surface_position) = self.last.unwrap_or((0, 0, 0.0));
        Ok(Sensors {
            tick,
            time_us: tick * 1000,
            sample_time_us,
            sequence,
            needle_position: 0.0,
            needle_velocity: 0.0,
            surface_position,
            flags: if self.last.is_none() {
                0
            } else if fresh {
                3
            } else {
                1
            },
        })
    }
}
