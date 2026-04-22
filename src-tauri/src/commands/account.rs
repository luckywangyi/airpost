use crate::db::{Account, Database};
use tauri::State;

#[tauri::command]
pub fn get_accounts(db: State<'_, Database>) -> Result<Vec<Account>, String> {
    db.get_accounts().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn add_account(db: State<'_, Database>, account: Account) -> Result<(), String> {
    db.add_account(&account).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn update_account(db: State<'_, Database>, account: Account) -> Result<(), String> {
    db.update_account(&account).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn delete_account(db: State<'_, Database>, id: String) -> Result<(), String> {
    db.delete_account(&id).map_err(|e| e.to_string())
}
