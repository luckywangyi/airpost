use std::sync::Mutex;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};

pub struct SidecarState {
    pub child: Mutex<Option<CommandChild>>,
    pub port: Mutex<u16>,
}

impl SidecarState {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(18765),
        }
    }
}

#[tauri::command]
pub async fn start_sidecar(app: AppHandle, port: Option<u16>) -> Result<String, String> {
    let state = app.state::<SidecarState>();
    let p = port.unwrap_or(18765);
    *state.port.lock().unwrap() = p;

    {
        let existing = state.child.lock().unwrap();
        if existing.is_some() {
            return Ok(format!("Sidecar already running on port {}", p));
        }
    }

    let sidecar_dir = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("sidecar");

    let (mut rx, child) = app
        .shell()
        .command("python")
        .args(["main.py", &p.to_string()])
        .current_dir(sidecar_dir)
        .spawn()
        .map_err(|e| format!("Failed to start sidecar: {}", e))?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    log::info!("[sidecar stdout] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    log::warn!("[sidecar stderr] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(payload) => {
                    log::info!("[sidecar] terminated with code: {:?}", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });

    *state.child.lock().unwrap() = Some(child);

    Ok(format!("Sidecar started on port {}", p))
}

#[tauri::command]
pub fn stop_sidecar(app: AppHandle) -> Result<String, String> {
    let state = app.state::<SidecarState>();
    let mut child = state.child.lock().unwrap();
    if let Some(c) = child.take() {
        c.kill().map_err(|e| format!("Failed to kill sidecar: {}", e))?;
        Ok("Sidecar stopped".into())
    } else {
        Ok("Sidecar was not running".into())
    }
}

#[tauri::command]
pub fn get_sidecar_url(app: AppHandle) -> String {
    let state = app.state::<SidecarState>();
    let port = *state.port.lock().unwrap();
    format!("http://127.0.0.1:{}", port)
}
