use crate::{
    Result, RunError, require,
    types::{Command, Sensors},
};

pub const MAX_PAYLOAD: usize = 256;
pub const SENSOR_BYTES: usize = 29;
pub const COMMAND_BYTES: usize = 17;

pub fn crc16(data: &[u8]) -> u16 {
    let mut crc = 0xffffu16;
    for &byte in data {
        crc ^= (byte as u16) << 8;
        for _ in 0..8 {
            crc = if crc & 0x8000 != 0 {
                (crc << 1) ^ 0x1021
            } else {
                crc << 1
            };
        }
    }
    crc
}

#[derive(Debug, PartialEq)]
pub struct Frame {
    pub kind: u8,
    pub session: u32,
    pub payload: Vec<u8>,
}

impl Frame {
    pub fn encode(&self) -> Result<Vec<u8>> {
        require(
            self.payload.len() <= MAX_PAYLOAD,
            "wire payload exceeds bound",
        )?;
        let mut out = vec![0xa5, 0x5a, 1, self.kind];
        out.extend_from_slice(&(self.payload.len() as u16).to_le_bytes());
        out.extend_from_slice(&self.session.to_le_bytes());
        out.extend_from_slice(&self.payload);
        out.extend_from_slice(&crc16(&out[2..]).to_le_bytes());
        Ok(out)
    }
    pub fn decode(data: &[u8]) -> Result<Self> {
        require(data.len() >= 12, "truncated frame")?;
        require(
            data[..2] == [0xa5, 0x5a] && data[2] == 1,
            "bad sync/version",
        )?;
        let size = u16::from_le_bytes(data[4..6].try_into().unwrap()) as usize;
        require(
            size <= MAX_PAYLOAD && data.len() == size + 12,
            "bad payload length",
        )?;
        require(
            crc16(&data[2..data.len() - 2])
                == u16::from_le_bytes(data[data.len() - 2..].try_into().unwrap()),
            "CRC mismatch",
        )?;
        require(
            matches!(data[3], 1..=8 | 0x81..=0x83 | 0x85 | 0x87 | 0x88),
            "unknown frame type",
        )?;
        Ok(Self {
            kind: data[3],
            session: u32::from_le_bytes(data[6..10].try_into().unwrap()),
            payload: data[10..10 + size].to_vec(),
        })
    }
}

pub fn sensors_payload(sensors: &Sensors) -> Result<Vec<u8>> {
    let input = sensors.to_c()?;
    let mut out = Vec::with_capacity(SENSOR_BYTES);
    for word in [
        input.tick,
        input.time_us,
        input.sample_time_us,
        input.sequence,
    ] {
        out.extend_from_slice(&word.to_le_bytes());
    }
    for number in [
        input.needle_position,
        input.needle_velocity,
        input.surface_position,
    ] {
        out.extend_from_slice(&number.to_bits().to_le_bytes());
    }
    out.push(input.flags as u8);
    Ok(out)
}

pub fn command_payload(frame: &Frame, session: u32, tick: u32) -> Result<Command> {
    require(
        frame.kind == 0x83 && frame.session == session && frame.payload.len() == COMMAND_BYTES,
        "unexpected command frame",
    )?;
    let echo = u32::from_le_bytes(frame.payload[..4].try_into().unwrap());
    require(echo == tick, "command tick mismatch")?;
    require(
        frame.payload[16] == 0,
        "controller status error in lockstep",
    )?;
    let force_n = f32::from_bits(u32::from_le_bytes(frame.payload[4..8].try_into().unwrap()));
    require(force_n.is_finite(), "nonfinite controller command")?;
    Ok(Command { force_n })
}

pub fn ack(frame: &Frame, session: u32, request_type: u8) -> Result<()> {
    require(
        frame.kind == 0x82 && frame.session == session && frame.payload == [request_type, 0],
        "invalid/missing acknowledgement",
    )
}

pub fn decode_hex(text: &str) -> Result<Vec<u8>> {
    require(text.len().is_multiple_of(2), "odd hex length")?;
    text.as_bytes()
        .as_chunks::<2>()
        .0
        .iter()
        .map(|pair| {
            let s = std::str::from_utf8(pair).map_err(|e| RunError(e.to_string()))?;
            u8::from_str_radix(s, 16).map_err(|e| RunError(e.to_string()))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    #[test]
    fn independent_golden_vectors() {
        assert_eq!(crc16(b"123456789"), 0x29b1);
        let golden: Value =
            serde_json::from_str(include_str!("../tests/data/protocol_v1.json")).unwrap();
        for row in golden["frames"].as_array().unwrap() {
            let frame = Frame {
                kind: row["type"].as_u64().unwrap() as u8,
                session: row["session"].as_u64().unwrap() as u32,
                payload: decode_hex(row["payload_hex"].as_str().unwrap()).unwrap(),
            };
            let bytes = decode_hex(row["frame_hex"].as_str().unwrap()).unwrap();
            assert_eq!(frame.encode().unwrap(), bytes);
            assert_eq!(Frame::decode(&bytes).unwrap(), frame);
        }
    }
    #[test]
    fn every_single_bit_error_rejected() {
        let bytes = Frame {
            kind: 3,
            session: 8,
            payload: vec![0; 29],
        }
        .encode()
        .unwrap();
        for bit in 0..bytes.len() * 8 {
            let mut damaged = bytes.clone();
            damaged[bit / 8] ^= 1 << (bit % 8);
            assert!(Frame::decode(&damaged).is_err(), "bit {bit}");
        }
    }
    #[test]
    fn truncation_oversize_and_garbage_rejected() {
        let bytes = Frame {
            kind: 3,
            session: 8,
            payload: vec![0; 29],
        }
        .encode()
        .unwrap();
        for n in 0..bytes.len() {
            assert!(Frame::decode(&bytes[..n]).is_err());
        }
        let mut extra = bytes.clone();
        extra.push(0);
        assert!(Frame::decode(&extra).is_err());
        assert!(
            Frame {
                kind: 3,
                session: 1,
                payload: vec![0; 257]
            }
            .encode()
            .is_err()
        );
    }
    #[test]
    fn wrong_tick_session_status_and_nan_rejected() {
        let mut payload = Vec::new();
        payload.extend_from_slice(&15u32.to_le_bytes());
        payload.extend_from_slice(&(-0.005f32).to_le_bytes());
        payload.extend_from_slice(&[0; 9]);
        let mut frame = Frame {
            kind: 0x83,
            session: 7,
            payload,
        };
        assert!(command_payload(&frame, 7, 15).is_ok());
        assert!(command_payload(&frame, 8, 15).is_err());
        assert!(command_payload(&frame, 7, 14).is_err());
        frame.payload[16] = 1;
        assert!(command_payload(&frame, 7, 15).is_err());
        frame.payload[16] = 0;
        frame.payload[4..8].copy_from_slice(&f32::NAN.to_le_bytes());
        assert!(command_payload(&frame, 7, 15).is_err());
    }
    #[test]
    fn full_sensor_inputs_and_raw_float_bits() {
        let s = Sensors {
            tick: 15,
            time_us: 15000,
            sample_time_us: 0,
            sequence: 0,
            needle_position: 0.001,
            needle_velocity: 0.0,
            surface_position: 0.0,
            flags: 3,
        };
        let bytes = sensors_payload(&s).unwrap();
        assert_eq!(bytes.len(), 29);
        assert_eq!(
            u32::from_le_bytes(bytes[16..20].try_into().unwrap()),
            (0.001f32).to_bits()
        );
        let golden: Value =
            serde_json::from_str(include_str!("../tests/data/protocol_v1.json")).unwrap();
        assert_eq!(
            bytes,
            decode_hex(golden["frames"][2]["payload_hex"].as_str().unwrap()).unwrap()
        );
    }
}
