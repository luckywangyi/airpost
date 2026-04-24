use rusqlite::{Connection, Result, params};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Account {
    pub id: String,
    pub nickname: String,
    pub cookie_path: String,
    pub proxy: Option<String>,
    pub status: String,
    pub last_login: String,
    pub daily_post_limit: u32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ContentItem {
    pub id: String,
    pub account_id: String,
    pub title: String,
    pub body: String,
    pub tags: String,
    pub images: String,
    pub scheduled_at: Option<String>,
    pub status: String,
    pub created_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct NoteStats {
    pub id: String,
    pub account_id: String,
    pub note_url: String,
    pub title: String,
    pub views: u64,
    pub likes: u64,
    pub collects: u64,
    pub comments: u64,
    pub shares: u64,
    pub collected_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CommentRecord {
    pub id: String,
    pub account_id: String,
    pub note_url: String,
    pub comment_text: String,
    pub reply_text: Option<String>,
    pub replied: bool,
    pub created_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TaskLog {
    pub id: String,
    pub task_type: String,
    pub account_id: Option<String>,
    pub status: String,
    pub message: Option<String>,
    pub created_at: String,
}

pub struct Database {
    pub conn: Mutex<Connection>,
}

impl Database {
    pub fn new(data_dir: &PathBuf) -> Result<Self> {
        std::fs::create_dir_all(data_dir).ok();
        let db_path = data_dir.join("xhs.db");
        let conn = Connection::open(db_path)?;
        let db = Database {
            conn: Mutex::new(conn),
        };
        db.init_tables()?;
        Ok(db)
    }

    fn init_tables(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL DEFAULT '',
                cookie_path TEXT NOT NULL DEFAULT '',
                proxy TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                last_login TEXT NOT NULL DEFAULT '',
                daily_post_limit INTEGER NOT NULL DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS content_queue (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                images TEXT NOT NULL DEFAULT '',
                scheduled_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS note_stats (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                note_url TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                collects INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                collected_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS comment_records (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                note_url TEXT NOT NULL DEFAULT '',
                comment_text TEXT NOT NULL DEFAULT '',
                reply_text TEXT,
                replied INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS task_logs (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL DEFAULT '',
                account_id TEXT,
                status TEXT NOT NULL DEFAULT '',
                message TEXT,
                created_at TEXT NOT NULL DEFAULT ''
            );"
        )?;
        Ok(())
    }

    // Account CRUD
    pub fn add_account(&self, account: &Account) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO accounts (id, nickname, cookie_path, proxy, status, last_login, daily_post_limit)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![account.id, account.nickname, account.cookie_path, account.proxy, account.status, account.last_login, account.daily_post_limit],
        )?;
        Ok(())
    }

    pub fn get_accounts(&self) -> Result<Vec<Account>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT id, nickname, cookie_path, proxy, status, last_login, daily_post_limit FROM accounts")?;
        let rows = stmt.query_map([], |row| {
            Ok(Account {
                id: row.get(0)?,
                nickname: row.get(1)?,
                cookie_path: row.get(2)?,
                proxy: row.get(3)?,
                status: row.get(4)?,
                last_login: row.get(5)?,
                daily_post_limit: row.get(6)?,
            })
        })?;
        let mut accounts = Vec::new();
        for row in rows {
            accounts.push(row?);
        }
        Ok(accounts)
    }

    pub fn update_account(&self, account: &Account) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "UPDATE accounts SET nickname=?2, cookie_path=?3, proxy=?4, status=?5, last_login=?6, daily_post_limit=?7 WHERE id=?1",
            params![account.id, account.nickname, account.cookie_path, account.proxy, account.status, account.last_login, account.daily_post_limit],
        )?;
        Ok(())
    }

    pub fn delete_account(&self, id: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM accounts WHERE id=?1", params![id])?;
        Ok(())
    }

    // Content Queue CRUD
    pub fn add_content(&self, item: &ContentItem) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO content_queue (id, account_id, title, body, tags, images, scheduled_at, status, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![item.id, item.account_id, item.title, item.body, item.tags, item.images, item.scheduled_at, item.status, item.created_at],
        )?;
        Ok(())
    }

    pub fn get_content_queue(&self) -> Result<Vec<ContentItem>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT id, account_id, title, body, tags, images, scheduled_at, status, created_at FROM content_queue ORDER BY created_at DESC")?;
        let rows = stmt.query_map([], |row| {
            Ok(ContentItem {
                id: row.get(0)?,
                account_id: row.get(1)?,
                title: row.get(2)?,
                body: row.get(3)?,
                tags: row.get(4)?,
                images: row.get(5)?,
                scheduled_at: row.get(6)?,
                status: row.get(7)?,
                created_at: row.get(8)?,
            })
        })?;
        let mut items = Vec::new();
        for row in rows {
            items.push(row?);
        }
        Ok(items)
    }

    pub fn get_content_by_id(&self, id: &str) -> Result<Option<ContentItem>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT id, account_id, title, body, tags, images, scheduled_at, status, created_at FROM content_queue WHERE id=?1")?;
        let mut rows = stmt.query_map(params![id], |row| {
            Ok(ContentItem {
                id: row.get(0)?,
                account_id: row.get(1)?,
                title: row.get(2)?,
                body: row.get(3)?,
                tags: row.get(4)?,
                images: row.get(5)?,
                scheduled_at: row.get(6)?,
                status: row.get(7)?,
                created_at: row.get(8)?,
            })
        })?;
        match rows.next() {
            Some(row) => Ok(Some(row?)),
            None => Ok(None),
        }
    }

    pub fn update_content(&self, item: &ContentItem) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "UPDATE content_queue SET account_id=?2, title=?3, body=?4, tags=?5, images=?6, scheduled_at=?7, status=?8 WHERE id=?1",
            params![item.id, item.account_id, item.title, item.body, item.tags, item.images, item.scheduled_at, item.status],
        )?;
        Ok(())
    }

    pub fn update_content_status(&self, id: &str, status: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("UPDATE content_queue SET status=?2 WHERE id=?1", params![id, status])?;
        Ok(())
    }

    pub fn delete_content(&self, id: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM content_queue WHERE id=?1", params![id])?;
        Ok(())
    }

    // Note Stats
    pub fn add_note_stats(&self, stats: &NoteStats) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO note_stats (id, account_id, note_url, title, views, likes, collects, comments, shares, collected_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
            params![stats.id, stats.account_id, stats.note_url, stats.title, stats.views, stats.likes, stats.collects, stats.comments, stats.shares, stats.collected_at],
        )?;
        Ok(())
    }

    pub fn get_note_stats(&self, account_id: Option<&str>) -> Result<Vec<NoteStats>> {
        let conn = self.conn.lock().unwrap();
        let (sql, p): (String, Vec<Box<dyn rusqlite::types::ToSql>>) = match account_id {
            Some(aid) => (
                "SELECT id, account_id, note_url, title, views, likes, collects, comments, shares, collected_at FROM note_stats WHERE account_id=?1 ORDER BY collected_at DESC".to_string(),
                vec![Box::new(aid.to_string())],
            ),
            None => (
                "SELECT id, account_id, note_url, title, views, likes, collects, comments, shares, collected_at FROM note_stats ORDER BY collected_at DESC".to_string(),
                vec![],
            ),
        };
        let mut stmt = conn.prepare(&sql)?;
        let rows = stmt.query_map(rusqlite::params_from_iter(p.iter()), |row| {
            Ok(NoteStats {
                id: row.get(0)?,
                account_id: row.get(1)?,
                note_url: row.get(2)?,
                title: row.get(3)?,
                views: row.get(4)?,
                likes: row.get(5)?,
                collects: row.get(6)?,
                comments: row.get(7)?,
                shares: row.get(8)?,
                collected_at: row.get(9)?,
            })
        })?;
        let mut stats_list = Vec::new();
        for row in rows {
            stats_list.push(row?);
        }
        Ok(stats_list)
    }

    // Task Logs
    pub fn add_task_log(&self, log: &TaskLog) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO task_logs (id, task_type, account_id, status, message, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![log.id, log.task_type, log.account_id, log.status, log.message, log.created_at],
        )?;
        Ok(())
    }

    pub fn get_task_logs(&self, limit: u32) -> Result<Vec<TaskLog>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT id, task_type, account_id, status, message, created_at FROM task_logs ORDER BY created_at DESC LIMIT ?1")?;
        let rows = stmt.query_map(params![limit], |row| {
            Ok(TaskLog {
                id: row.get(0)?,
                task_type: row.get(1)?,
                account_id: row.get(2)?,
                status: row.get(3)?,
                message: row.get(4)?,
                created_at: row.get(5)?,
            })
        })?;
        let mut logs = Vec::new();
        for row in rows {
            logs.push(row?);
        }
        Ok(logs)
    }
}
