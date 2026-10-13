pub mod ffi;
pub mod plant;
pub mod protocol;
pub mod replay;
pub mod runner;
pub mod serial;
pub mod types;

use std::{error::Error, fmt};

#[derive(Debug)]
pub struct RunError(pub String);
impl fmt::Display for RunError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}
impl Error for RunError {}
impl From<std::io::Error> for RunError {
    fn from(value: std::io::Error) -> Self {
        Self(value.to_string())
    }
}
impl From<serde_json::Error> for RunError {
    fn from(value: serde_json::Error) -> Self {
        Self(value.to_string())
    }
}
pub type Result<T> = std::result::Result<T, RunError>;

pub fn require(condition: bool, message: &str) -> Result<()> {
    if condition {
        Ok(())
    } else {
        Err(RunError(message.to_owned()))
    }
}

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn sha256(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    hex(&Sha256::digest(bytes))
}
