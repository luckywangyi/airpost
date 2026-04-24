use crate::db::{ContentItem, Database};
use tauri::State;

#[tauri::command]
pub fn get_content_queue(db: State<'_, Database>) -> Result<Vec<ContentItem>, String> {
    db.get_content_queue().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_content_by_id(db: State<'_, Database>, id: String) -> Result<Option<ContentItem>, String> {
    db.get_content_by_id(&id).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn add_content(db: State<'_, Database>, item: ContentItem) -> Result<(), String> {
    db.add_content(&item).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn update_content(db: State<'_, Database>, item: ContentItem) -> Result<(), String> {
    db.update_content(&item).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn update_content_status(db: State<'_, Database>, id: String, status: String) -> Result<(), String> {
    db.update_content_status(&id, &status).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn delete_content(db: State<'_, Database>, id: String) -> Result<(), String> {
    db.delete_content(&id).map_err(|e| e.to_string())
}
