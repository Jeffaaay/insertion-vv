use crate::{
    Result, RunError, hex,
    protocol::{self, Frame},
    require,
    types::{Command, Controller, Sensors},
};
use serde_json::{Value, json};
use std::{
    collections::HashSet,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    sync::{Mutex, OnceLock},
    time::{Duration, Instant},
};

enum Connection {
    Serial(Box<dyn serialport::SerialPort>),
    Tcp(TcpStream),
}
impl Connection {
    fn timeout(&mut self, timeout: Duration) -> Result<()> {
        match self {
            Self::Serial(port) => port
                .set_timeout(timeout)
                .map_err(|e| RunError(e.to_string())),
            Self::Tcp(stream) => {
                stream.set_read_timeout(Some(timeout))?;
                stream.set_write_timeout(Some(timeout))?;
                Ok(())
            }
        }
    }
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        match self {
            Self::Serial(port) => port.read(buffer),
            Self::Tcp(stream) => stream.read(buffer),
        }
    }
    fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
        match self {
            Self::Serial(port) => port.write(buffer),
            Self::Tcp(stream) => stream.write(buffer),
        }
    }
}

pub struct ControllerSerial {
    connection: Connection,
    expected_source: String,
    device_kind: u8,
    endpoint: String,
    session: u32,
    next_tick: u32,
    info: Value,
    events: Vec<Value>,
    started: Instant,
    finished: bool,
}

impl ControllerSerial {
    pub fn serial(port: &str, expected_source: String) -> Result<Self> {
        let connection = serialport::new(port, 460800)
            .timeout(Duration::from_secs(2))
            .data_bits(serialport::DataBits::Eight)
            .parity(serialport::Parity::None)
            .stop_bits(serialport::StopBits::One)
            .flow_control(serialport::FlowControl::None)
            .open()
            .map_err(|e| RunError(e.to_string()))?;
        Ok(Self::new(
            Connection::Serial(connection),
            expected_source,
            1,
            port.into(),
        ))
    }
    pub fn tcp(address: &str, expected_source: String) -> Result<Self> {
        let address: SocketAddr = address
            .parse()
            .map_err(|e| RunError(format!("invalid TCP endpoint: {e}")))?;
        let stream = TcpStream::connect_timeout(&address, Duration::from_secs(5))?;
        stream.set_nodelay(true)?;
        Ok(Self::new(
            Connection::Tcp(stream),
            expected_source,
            0,
            address.to_string(),
        ))
    }
    fn new(
        connection: Connection,
        expected_source: String,
        device_kind: u8,
        endpoint: String,
    ) -> Self {
        Self {
            connection,
            expected_source,
            device_kind,
            endpoint,
            session: 0,
            next_tick: 0,
            info: Value::Null,
            events: Vec::new(),
            started: Instant::now(),
            finished: false,
        }
    }
    fn remaining(deadline: Instant) -> Result<Duration> {
        deadline
            .checked_duration_since(Instant::now())
            .filter(|v| !v.is_zero())
            .ok_or_else(|| RunError("total transport deadline exceeded".into()))
    }
    fn receive(&mut self, bytes: &mut Vec<u8>, count: usize, deadline: Instant) -> Result<()> {
        while bytes.len() < count {
            self.connection.timeout(Self::remaining(deadline)?)?;
            let mut chunk = [0u8; 268];
            let size = self.connection.read(&mut chunk[..count - bytes.len()])?;
            require(size > 0, "transport disconnected")?;
            bytes.extend_from_slice(&chunk[..size]);
        }
        Ok(())
    }
    fn exchange(&mut self, frame: Frame, timeout: Duration) -> Result<Frame> {
        let tx = frame.encode()?;
        let deadline = Instant::now() + timeout;
        self.events.push(json!({"direction":"tx","elapsed_ns":self.started.elapsed().as_nanos() as u64,"hex":hex(&tx)}));
        let mut rx = Vec::new();
        let result = (|| {
            let mut written = 0;
            while written < tx.len() {
                self.connection.timeout(Self::remaining(deadline)?)?;
                let count = self.connection.write(&tx[written..])?;
                require(count > 0, "zero transport write")?;
                written += count;
            }
            self.receive(&mut rx, 10, deadline)?;
            let size = u16::from_le_bytes(rx[4..6].try_into().unwrap()) as usize;
            require(size <= protocol::MAX_PAYLOAD, "wire payload exceeds bound")?;
            self.receive(&mut rx, size + 12, deadline)?;
            Frame::decode(&rx)
        })();
        self.events.push(json!({"direction":"rx","elapsed_ns":self.started.elapsed().as_nanos() as u64,"hex":hex(&rx),
            "error":result.as_ref().err().map(ToString::to_string)}));
        result
    }
    fn hello(&mut self) -> Result<()> {
        let info = self.exchange(
            Frame {
                kind: 1,
                session: 0,
                payload: vec![],
            },
            Duration::from_secs(5),
        )?;
        require(
            info.kind == 0x81 && info.session == 0 && info.payload.len() == 140,
            "invalid INFO response",
        )?;
        let p = &info.payload;
        let word = |offset| u32::from_le_bytes(p[offset..offset + 4].try_into().unwrap());
        let source = std::str::from_utf8(&p[56..120]).map_err(|e| RunError(e.to_string()))?;
        let git = std::str::from_utf8(&p[16..56]).map_err(|e| RunError(e.to_string()))?;
        require(
            p[0] == self.device_kind
                && p[1] == 1
                && u16::from_le_bytes([p[2], p[3]]) & 1 == 1
                && word(12) == 8000,
            "incompatible board capabilities/ABI",
        )?;
        require(
            git.bytes().all(|b| b.is_ascii_hexdigit()) && source == self.expected_source,
            "firmware source identity mismatch",
        )?;
        if self.device_kind == 0 {
            require(
                word(4) == 0 && word(8) == 0 && p[120..].iter().all(|v| *v == 0),
                "virtual timing/identity must be zero",
            )?;
        } else {
            require(word(4) > 0 && word(8) > 0, "missing hardware clocks")?;
        }
        self.info = json!({"device_kind":p[0],"abi":p[1],"capabilities":u16::from_le_bytes([p[2],p[3]]),
            "core_clock_hz":word(4),"timer_clock_hz":word(8),"max_ticks":word(12),"git_commit":git,
            "controller_source_sha256":source,"unique_id_hex":hex(&p[120..132]),"mcu_idcode":word(132),"arm_cpuid":word(136)});
        Ok(())
    }
}

fn new_session() -> Result<u32> {
    static USED: OnceLock<Mutex<HashSet<u32>>> = OnceLock::new();
    let mut used = USED
        .get_or_init(|| Mutex::new(HashSet::new()))
        .lock()
        .map_err(|_| RunError("session lock poisoned".into()))?;
    for _ in 0..32 {
        let mut bytes = [0; 4];
        getrandom::fill(&mut bytes).map_err(|e| RunError(e.to_string()))?;
        let session = u32::from_le_bytes(bytes);
        if session != 0 && used.insert(session) {
            return Ok(session);
        }
    }
    Err(RunError("could not allocate unique session".into()))
}

impl Controller for ControllerSerial {
    fn reset(&mut self) -> Result<()> {
        self.hello()?;
        self.session = new_session()?;
        self.next_tick = 0;
        self.finished = false;
        let mut payload = vec![0];
        payload.extend_from_slice(&8000u32.to_le_bytes());
        let response = self.exchange(
            Frame {
                kind: 2,
                session: self.session,
                payload,
            },
            Duration::from_secs(2),
        )?;
        protocol::ack(&response, self.session, 2)
    }
    fn command(&mut self, sensors: &Sensors) -> Result<Command> {
        require(
            self.session != 0
                && !self.finished
                && sensors.tick == self.next_tick
                && sensors.tick < 8000
                && sensors.time_us == sensors.tick * 1000,
            "invalid serial tick/state",
        )?;
        let response = self.exchange(
            Frame {
                kind: 3,
                session: self.session,
                payload: protocol::sensors_payload(sensors)?,
            },
            Duration::from_secs(2),
        )?;
        let command = protocol::command_payload(&response, self.session, sensors.tick)?;
        if self.device_kind == 0 {
            require(
                response.payload[8..16].iter().all(|b| *b == 0),
                "virtual board reported physical timing",
            )?;
        }
        self.next_tick += 1;
        Ok(command)
    }
    fn finish(&mut self, ticks: u32) -> Result<()> {
        require(
            !self.finished && ticks == 8000 && self.next_tick == ticks,
            "incomplete serial run",
        )?;
        let response = self.exchange(
            Frame {
                kind: 4,
                session: self.session,
                payload: ticks.to_le_bytes().to_vec(),
            },
            Duration::from_secs(2),
        )?;
        protocol::ack(&response, self.session, 4)?;
        self.finished = true;
        Ok(())
    }
    fn provenance(&self) -> Value {
        json!({"backend":if self.device_kind==0 {"tcp-virtual"} else {"serial"},
        "endpoint":self.endpoint,"session":self.session,"info":self.info,"baud":460800,"framing":"8N1"})
    }
    fn take_transport_events(&mut self) -> Vec<Value> {
        std::mem::take(&mut self.events)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{net::TcpListener, thread};

    fn read_frame(stream: &mut TcpStream) -> Frame {
        stream
            .set_read_timeout(Some(Duration::from_secs(2)))
            .unwrap();
        let mut data = vec![0; 10];
        stream.read_exact(&mut data).unwrap();
        let count = u16::from_le_bytes([data[4], data[5]]) as usize;
        data.resize(count + 12, 0);
        stream.read_exact(&mut data[10..]).unwrap();
        Frame::decode(&data).unwrap()
    }
    fn reply(stream: &mut TcpStream, frame: Frame) {
        for chunk in frame.encode().unwrap().chunks(3) {
            stream.write_all(chunk).unwrap();
        }
    }
    #[test]
    fn fragmented_handshake_and_command_then_wrong_session_rejected() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap().to_string();
        let worker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream.set_nodelay(true).unwrap();
            assert_eq!(read_frame(&mut stream).kind, 1);
            let mut payload = vec![0; 140];
            payload[1] = 1;
            payload[2] = 1;
            payload[12..16].copy_from_slice(&8000u32.to_le_bytes());
            payload[16..56].fill(b'0');
            payload[56..120].fill(b'a');
            reply(
                &mut stream,
                Frame {
                    kind: 0x81,
                    session: 0,
                    payload,
                },
            );
            let reset = read_frame(&mut stream);
            assert_eq!(reset.kind, 2);
            assert_ne!(reset.session, 0);
            reply(
                &mut stream,
                Frame {
                    kind: 0x82,
                    session: reset.session,
                    payload: vec![2, 0],
                },
            );
            for tick in 0u32..2 {
                let input = read_frame(&mut stream);
                assert_eq!(input.kind, 3);
                assert_eq!(input.payload.len(), 29);
                let mut payload = tick.to_le_bytes().to_vec();
                payload.extend_from_slice(&(-0.005f32).to_le_bytes());
                payload.extend_from_slice(&[0; 9]);
                reply(
                    &mut stream,
                    Frame {
                        kind: 0x83,
                        session: reset.session ^ tick,
                        payload,
                    },
                );
            }
        });
        let mut controller = ControllerSerial::tcp(&address, "a".repeat(64)).unwrap();
        controller.reset().unwrap();
        let mut s = Sensors {
            tick: 0,
            time_us: 0,
            sample_time_us: 0,
            sequence: 0,
            needle_position: 0.001,
            needle_velocity: 0.,
            surface_position: 0.,
            flags: 0,
        };
        assert_eq!(
            controller.command(&s).unwrap().force_n.to_bits(),
            (-0.005f32).to_bits()
        );
        assert!(controller.finish(1).is_err());
        s.tick = 1;
        s.time_us = 1000;
        assert!(controller.command(&s).is_err());
        assert_eq!(controller.take_transport_events().len(), 8);
        worker.join().unwrap();
    }
    #[test]
    fn total_deadline_and_partial_response_are_retained() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap().to_string();
        let worker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            read_frame(&mut stream);
            stream.write_all(&[0xa5, 0x5a, 1]).unwrap();
            thread::sleep(Duration::from_millis(200));
        });
        let mut controller = ControllerSerial::tcp(&address, "a".repeat(64)).unwrap();
        assert!(
            controller
                .exchange(
                    Frame {
                        kind: 1,
                        session: 0,
                        payload: vec![]
                    },
                    Duration::from_millis(50)
                )
                .is_err()
        );
        let events = controller.take_transport_events();
        assert_eq!(events[1]["hex"], "a55a01");
        assert!(events[1]["error"].is_string());
        worker.join().unwrap();
    }
    #[test]
    fn sessions_are_nonzero_and_not_reused() {
        let sessions: HashSet<u32> = (0..100).map(|_| new_session().unwrap()).collect();
        assert_eq!(sessions.len(), 100);
        assert!(!sessions.contains(&0));
    }
}
