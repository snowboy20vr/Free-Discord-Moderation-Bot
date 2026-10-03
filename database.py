from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import DATABASE_PATH, PREFIX


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Settings and punishment persistence lives in SQLite.

class Database:
    def __init__(self, path: str = DATABASE_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.setup()

    def setup(self) -> None:
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            prefix TEXT NOT NULL DEFAULT '!',
            log_channel_id INTEGER,
            mute_role_id INTEGER,
            dm_actions INTEGER NOT NULL DEFAULT 0,
            require_reason INTEGER NOT NULL DEFAULT 1,
            ban_delete_days INTEGER NOT NULL DEFAULT 1,
            softban_delete_days INTEGER NOT NULL DEFAULT 1,
            case_counter INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS level_names (
            guild_id INTEGER NOT NULL,
            level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
            name TEXT NOT NULL,
            PRIMARY KEY(guild_id, level)
        );
        CREATE TABLE IF NOT EXISTS role_levels (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
            PRIMARY KEY(guild_id, role_id)
        );
        CREATE TABLE IF NOT EXISTS command_levels (
            guild_id INTEGER NOT NULL,
            command_name TEXT NOT NULL,
            level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),
            PRIMARY KEY(guild_id, command_name)
        );
        CREATE TABLE IF NOT EXISTS temp_punishments (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            case_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY(guild_id, user_id, action)
        );
        CREATE TABLE IF NOT EXISTS cases (
            guild_id INTEGER NOT NULL,
            case_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT,
            duration TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY(guild_id, case_id)
        );
        CREATE TABLE IF NOT EXISTS warnings (
            guild_id INTEGER NOT NULL,
            warning_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(guild_id, warning_id)
        );
        ''')
        self._migrate_columns()
        self.conn.commit()

    def _migrate_columns(self) -> None:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(guild_settings)").fetchall()}
        migrations = {
            "require_reason": "ALTER TABLE guild_settings ADD COLUMN require_reason INTEGER NOT NULL DEFAULT 1",
            "ban_delete_days": "ALTER TABLE guild_settings ADD COLUMN ban_delete_days INTEGER NOT NULL DEFAULT 1",
            "softban_delete_days": "ALTER TABLE guild_settings ADD COLUMN softban_delete_days INTEGER NOT NULL DEFAULT 1",
        }
        for name, sql in migrations.items():
            if name not in columns:
                self.conn.execute(sql)

    def ensure_guild(self, guild_id: int) -> None:
        timestamp = now_iso()
        self.conn.execute('INSERT OR IGNORE INTO guild_settings (guild_id, prefix, created_at, updated_at) VALUES (?, ?, ?, ?)', (guild_id, PREFIX, timestamp, timestamp))
        self.conn.commit()

    def settings(self, guild_id: int) -> dict[str, Any]:
        self.ensure_guild(guild_id)
        row = self.conn.execute('SELECT * FROM guild_settings WHERE guild_id = ?', (guild_id,)).fetchone()
        return dict(row)

    def set_setting(self, guild_id: int, key: str, value: Any) -> None:
        allowed = {'prefix', 'log_channel_id', 'mute_role_id', 'dm_actions', 'require_reason', 'ban_delete_days', 'softban_delete_days'}
        if key not in allowed:
            raise ValueError('Invalid setting')
        self.ensure_guild(guild_id)
        self.conn.execute(f'UPDATE guild_settings SET {key} = ?, updated_at = ? WHERE guild_id = ?', (value, now_iso(), guild_id))
        self.conn.commit()

    def get_command_level(self, guild_id: int, command_name: str, default: int = 1) -> int:
        self.ensure_guild(guild_id)
        row = self.conn.execute('SELECT level FROM command_levels WHERE guild_id = ? AND command_name = ?', (guild_id, command_name.lower().lstrip('/'))).fetchone()
        return int(row['level']) if row else default

    def set_command_level(self, guild_id: int, command_name: str, level: int) -> None:
        if not 1 <= level <= 5:
            raise ValueError('Permission level must be 1-5')
        self.conn.execute('INSERT INTO command_levels (guild_id, command_name, level) VALUES (?, ?, ?) ON CONFLICT(guild_id, command_name) DO UPDATE SET level = excluded.level', (guild_id, command_name.lower().lstrip('/'), level))
        self.conn.commit()

    def all_command_levels(self, guild_id: int) -> dict[str, int]:
        rows = self.conn.execute('SELECT command_name, level FROM command_levels WHERE guild_id = ?', (guild_id,)).fetchall()
        return {row['command_name']: int(row['level']) for row in rows}

    def level_names(self, guild_id: int) -> dict[int, str]:
        self.ensure_guild(guild_id)
        defaults = {1: 'Owner / Full Control', 2: 'Administrator', 3: 'Senior Moderator', 4: 'Moderator', 5: 'Trial Moderator'}
        rows = self.conn.execute('SELECT level, name FROM level_names WHERE guild_id = ?', (guild_id,)).fetchall()
        names = defaults.copy()
        names.update({int(row['level']): str(row['name']) for row in rows})
        return names

    def set_level_name(self, guild_id: int, level: int, name: str) -> None:
        if not 1 <= level <= 5:
            raise ValueError('Permission level must be 1-5')
        name = ' '.join(name.strip().split())
        if not name:
            raise ValueError('Level name cannot be empty')
        if len(name) > 40:
            raise ValueError('Level name must be 40 characters or fewer')
        self.ensure_guild(guild_id)
        self.conn.execute(
            'INSERT INTO level_names (guild_id, level, name) VALUES (?, ?, ?) '
            'ON CONFLICT(guild_id, level) DO UPDATE SET name = excluded.name',
            (guild_id, level, name),
        )
        self.conn.commit()

    def set_role_level(self, guild_id: int, role_id: int, level: int) -> None:
        if not 1 <= level <= 5:
            raise ValueError('Permission level must be 1-5')
        self.conn.execute('INSERT INTO role_levels (guild_id, role_id, level) VALUES (?, ?, ?) ON CONFLICT(guild_id, role_id) DO UPDATE SET level = excluded.level', (guild_id, role_id, level))
        self.conn.commit()

    def role_levels(self, guild_id: int) -> dict[int, int]:
        rows = self.conn.execute('SELECT role_id, level FROM role_levels WHERE guild_id = ?', (guild_id,)).fetchall()
        return {int(row['role_id']): int(row['level']) for row in rows}

    def next_case(self, guild_id: int, action: str, target_id: int, moderator_id: int, reason: str, duration: str | None = None) -> int:
        self.ensure_guild(guild_id)
        row = self.conn.execute('SELECT case_counter FROM guild_settings WHERE guild_id = ?', (guild_id,)).fetchone()
        case_id = int(row['case_counter']) + 1
        self.conn.execute('UPDATE guild_settings SET case_counter = ?, updated_at = ? WHERE guild_id = ?', (case_id, now_iso(), guild_id))
        self.conn.execute('INSERT INTO cases (guild_id, case_id, action, target_id, moderator_id, reason, duration, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (guild_id, case_id, action, target_id, moderator_id, reason, duration, now_iso()))
        self.conn.commit()
        return case_id

    def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        self.ensure_guild(guild_id)
        row = self.conn.execute('SELECT COALESCE(MAX(warning_id), 0) + 1 AS next_id FROM warnings WHERE guild_id = ?', (guild_id,)).fetchone()
        warning_id = int(row['next_id'])
        self.conn.execute('INSERT INTO warnings (guild_id, warning_id, user_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)', (guild_id, warning_id, user_id, moderator_id, reason, now_iso()))
        self.conn.commit()
        return warning_id

    def warnings_for(self, guild_id: int, user_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute('SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? AND active = 1 ORDER BY warning_id DESC', (guild_id, user_id)).fetchall()
        return [dict(row) for row in rows]

    def clear_warnings(self, guild_id: int, user_id: int) -> int:
        cursor = self.conn.execute('UPDATE warnings SET active = 0 WHERE guild_id = ? AND user_id = ? AND active = 1', (guild_id, user_id))
        self.conn.commit()
        return cursor.rowcount


    def add_temp_punishment(self, guild_id: int, user_id: int, action: str, case_id: int, expires_at: datetime) -> None:
        self.conn.execute(
            "INSERT INTO temp_punishments (guild_id, user_id, action, case_id, expires_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id, action) DO UPDATE SET case_id = excluded.case_id, expires_at = excluded.expires_at",
            (guild_id, user_id, action, case_id, expires_at.astimezone(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def due_temp_punishments(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM temp_punishments WHERE expires_at <= ?", (now_iso(),)).fetchall()
        return [dict(row) for row in rows]

    def remove_temp_punishment(self, guild_id: int, user_id: int, action: str) -> None:
        self.conn.execute(
            "DELETE FROM temp_punishments WHERE guild_id = ? AND user_id = ? AND action = ?",
            (guild_id, user_id, action),
        )
        self.conn.commit()
