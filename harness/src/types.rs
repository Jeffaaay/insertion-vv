use crate::{Result, require};

#[derive(Clone, Debug, PartialEq)]
pub struct Sensors {
    pub tick: u32,
    pub time_us: u32,
    pub sample_time_us: u32,
    pub sequence: u32,
    pub needle_position: f64,
    pub needle_velocity: f64,
    pub surface_position: f64,
    pub flags: u8,
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct CInput {
    pub tick: u32,
    pub time_us: u32,
    pub sample_time_us: u32,
    pub sequence: u32,
    pub needle_position: f32,
    pub needle_velocity: f32,
    pub surface_position: f32,
    pub flags: u32,
}

impl Sensors {
    pub fn from_ipc(data: &[u8]) -> Result<Self> {
        require(data.len() == 41, "wrong IPC Sensors length")?;
        let word = |offset| u32::from_le_bytes(data[offset..offset + 4].try_into().unwrap());
        let number = |offset| f64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
        let value = Self {
            tick: word(0),
            time_us: word(4),
            sample_time_us: word(8),
            sequence: word(12),
            needle_position: number(16),
            needle_velocity: number(24),
            surface_position: number(32),
            flags: data[40],
        };
        value.to_c()?;
        Ok(value)
    }

    pub fn to_c(&self) -> Result<CInput> {
        require(matches!(self.flags, 0 | 1 | 3), "invalid sensor flags")?;
        require(
            self.needle_position.is_finite()
                && self.needle_velocity.is_finite()
                && self.surface_position.is_finite(),
            "nonfinite sensor",
        )?;
        if self.flags == 0 {
            require(
                self.sample_time_us == 0
                    && self.sequence == 0
                    && self.surface_position.to_bits() == 0,
                "invalid absent-measurement placeholders",
            )?;
        }
        let input = CInput {
            tick: self.tick,
            time_us: self.time_us,
            sample_time_us: self.sample_time_us,
            sequence: self.sequence,
            needle_position: self.needle_position as f32,
            needle_velocity: self.needle_velocity as f32,
            surface_position: self.surface_position as f32,
            flags: self.flags as u32,
        };
        require(
            input.needle_position.is_finite()
                && input.needle_velocity.is_finite()
                && input.surface_position.is_finite(),
            "sensor overflow at C32 boundary",
        )?;
        Ok(input)
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Command {
    pub force_n: f32,
}

pub trait Controller {
    fn reset(&mut self) -> Result<()>;
    fn command(&mut self, sensors: &Sensors) -> Result<Command>;
    fn finish(&mut self, _ticks: u32) -> Result<()> {
        Ok(())
    }
    fn provenance(&self) -> serde_json::Value;
    fn take_transport_events(&mut self) -> Vec<serde_json::Value> {
        Vec::new()
    }
}

pub struct StepRecord {
    pub sensors: Sensors,
    pub trace: Vec<u8>,
    pub truth: Vec<u8>,
}

pub trait Plant {
    fn reset(&mut self, seed: u64) -> Result<Sensors>;
    fn step(&mut self, tick: u32, command: Command, dt_us: u32) -> Result<StepRecord>;
    // Canonical evaluator record for the most recently completed control tick.
    fn truth(&self) -> &[u8];
    fn finish(&mut self, ticks: u32) -> Result<()>;
}
