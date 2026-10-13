use crate::{
    Result, RunError, require, sha256,
    types::{CInput, Command, Controller, Sensors},
};
use libloading::Library;
use serde_json::{Value, json};
use std::{ffi::c_void, fs, path::Path};

#[repr(C)]
#[derive(Default)]
struct Params {
    numbers: [f32; 15],
    dt_us: u32,
    delay_us: u32,
}
type Init = unsafe extern "C" fn(*mut c_void, *const Params) -> i32;
type Step = unsafe extern "C" fn(*mut c_void, *const CInput, *mut f32) -> i32;

pub struct ControllerInProcessC {
    _library: Library,
    state: Vec<u64>,
    params: Params,
    init: Init,
    step: Step,
    build: Value,
}

impl ControllerInProcessC {
    pub fn new(directory: &Path) -> Result<Self> {
        let build: Value = serde_json::from_slice(&fs::read(directory.join("build.json"))?)?;
        let name = build["host"]["library"]
            .as_str()
            .ok_or_else(|| RunError("missing C library name".into()))?;
        require(
            Path::new(name).components().count() == 1,
            "library must be a build-directory filename",
        )?;
        let path = directory.join(name).canonicalize()?;
        require(
            sha256(&fs::read(&path)?) == build["host"]["sha256"],
            "C library SHA mismatch",
        )?;
        let mut encoded = serde_json::to_vec(&build["numerical_build"])?;
        encoded.push(b'\n');
        require(
            sha256(&encoded) == build["numerical_build_sha256"],
            "C numerical build hash mismatch",
        )?;
        // The library is our checksum-verified C artifact. Sizes are checked before
        // passing any pointer. Owned storage is aligned, and Library outlives calls.
        unsafe {
            let library = Library::new(&path).map_err(|e| RunError(e.to_string()))?;
            let state_size = library
                .get::<unsafe extern "C" fn() -> usize>(b"ctrl_state_size\0")
                .map_err(|e| RunError(e.to_string()))?();
            let params_size = library
                .get::<unsafe extern "C" fn() -> usize>(b"ctrl_params_size\0")
                .map_err(|e| RunError(e.to_string()))?();
            let sensors_size = library
                .get::<unsafe extern "C" fn() -> usize>(b"ctrl_sensors_size\0")
                .map_err(|e| RunError(e.to_string()))?();
            require(
                params_size == std::mem::size_of::<Params>()
                    && sensors_size == std::mem::size_of::<CInput>(),
                "C/Rust ABI mismatch",
            )?;
            require(
                (params_size..=65536).contains(&state_size),
                "invalid C state size",
            )?;
            let defaults = *library
                .get::<unsafe extern "C" fn(*mut Params)>(b"ctrl_default_params\0")
                .map_err(|e| RunError(e.to_string()))?;
            let init = *library
                .get::<Init>(b"ctrl_init\0")
                .map_err(|e| RunError(e.to_string()))?;
            let step = *library
                .get::<Step>(b"ctrl_step\0")
                .map_err(|e| RunError(e.to_string()))?;
            let mut params = Params::default();
            defaults(&mut params);
            let mut result = Self {
                _library: library,
                state: vec![0; state_size.div_ceil(8)],
                params,
                init,
                step,
                build,
            };
            result.reset()?;
            Ok(result)
        }
    }
}

impl Controller for ControllerInProcessC {
    fn reset(&mut self) -> Result<()> {
        let status = unsafe { (self.init)(self.state.as_mut_ptr().cast(), &self.params) };
        require(status == 0, "C init failed")
    }
    fn command(&mut self, sensors: &Sensors) -> Result<Command> {
        let input = sensors.to_c()?;
        let mut force = f32::NAN;
        let status = unsafe { (self.step)(self.state.as_mut_ptr().cast(), &input, &mut force) };
        require(
            status == 0 && force.is_finite(),
            "C step rejected input or returned nonfinite output",
        )?;
        Ok(Command { force_n: force })
    }
    fn provenance(&self) -> Value {
        json!({"backend":"ffi", "controller_build":self.build})
    }
}
