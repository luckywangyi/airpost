use crate::db::{NoteStats, TaskLog, Database};
use tauri::State;

#[tauri::command]
pub fn get_note_stats(db: State<'_, Database>, account_id: Option<String>) -> Result<Vec<NoteStats>, String> {
    db.get_note_stats(account_id.as_deref()).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn add_note_stats(db: State<'_, Database>, stats: NoteStats) -> Result<(), String> {
    db.add_note_stats(&stats).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_task_logs(db: State<'_, Database>, limit: Option<u32>) -> Result<Vec<TaskLog>, String> {
    db.get_task_logs(limit.unwrap_or(50)).map_err(|e| e.to_string())
}
