use c1_faults::FaultInjector;
use std::{env, fs, path::Path};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<_> = env::args().collect();
    if a.len() != 5 {
        return Err("usage: c1-faults ROOT CASE.json INPUT.bin OUTPUT.bin".into());
    }
    let case = serde_json::from_slice(&fs::read(&a[2])?)?;
    let mut injector = FaultInjector::new(Path::new(&a[1]), &case)?;
    let input = fs::read(&a[3])?;
    if input.len() % 16 != 0 {
        return Err("input must be surface/force f64 pairs".into());
    }
    let mut out = Vec::new();
    for (tick, data) in input.as_chunks::<16>().0.iter().enumerate() {
        let surface = f64::from_le_bytes(data[..8].try_into()?);
        let force = f64::from_le_bytes(data[8..].try_into()?);
        let tick = tick as u32;
        let s = injector.capture(tick, surface)?;
        let present = s.flags != 0;
        out.extend_from_slice(&(if present { s.sample_time_us as i64 } else { -1 }).to_le_bytes());
        out.extend_from_slice(&(if present { s.sequence as i64 } else { -1 }).to_le_bytes());
        out.extend_from_slice(&s.surface_position.to_le_bytes());
        out.push(u8::from(s.flags == 3));
        out.push(u8::from(injector.skip(tick)));
        out.extend_from_slice(&injector.clip(tick, force, 2.0).to_le_bytes());
    }
    fs::write(&a[4], out)?;
    Ok(())
}
