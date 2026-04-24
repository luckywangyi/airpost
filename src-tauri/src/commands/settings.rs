use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::Manager;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppSettings {
    pub sidecar_port: u16,
    pub auto_start: bool,
    pub ai_provider: String,
    pub ai_api_key: String,
    #[serde(default)]
    pub ai_base_url: String,
    #[serde(default = "default_ai_model")]
    pub ai_model: String,
    pub default_proxy: Option<String>,
    pub comment_check_interval: u32,
    pub data_collect_interval: u32,
    #[serde(default)]
    pub asset_folder: String,
    #[serde(default)]
    pub pexels_api_key: String,
}

fn default_ai_model() -> String {
    "gpt-4o-mini".to_string()
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            sidecar_port: 18765,
            auto_start: false,
            ai_provider: "openai".to_string(),
            ai_api_key: String::new(),
            ai_base_url: String::new(),
            ai_model: "gpt-4o-mini".to_string(),
            default_proxy: None,
            comment_check_interval: 30,
            data_collect_interval: 480,
            asset_folder: String::new(),
            pexels_api_key: String::new(),
        }
    }
}

fn settings_path(app: &tauri::AppHandle) -> PathBuf {
    let dir = app.path().app_data_dir().expect("failed to get app data dir");
    std::fs::create_dir_all(&dir).ok();
    dir.join("settings.json")
}

#[tauri::command]
pub fn get_settings(app: tauri::AppHandle) -> Result<AppSettings, String> {
    let path = settings_path(&app);
    if path.exists() {
        let data = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        serde_json::from_str(&data).map_err(|e| e.to_string())
    } else {
        let defaults = AppSettings::default();
        let json = serde_json::to_string_pretty(&defaults).map_err(|e| e.to_string())?;
        fs::write(&path, json).map_err(|e| e.to_string())?;
        Ok(defaults)
    }
}

#[tauri::command]
pub fn save_settings(app: tauri::AppHandle, settings: AppSettings) -> Result<(), String> {
    let path = settings_path(&app);
    let json = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| e.to_string())
}
