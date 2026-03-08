"""
╔══════════════════════════════════════════════════════════════════╗
║                   NEXACODE DATABASE                             ║
║         Session, History & Configuration Persistence             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import time
import asyncio
import aiosqlite
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from nexacode.config.settings import DB_FILE


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    workspace TEXT,
    model TEXT,
    agent TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    agent_name TEXT,
    model TEXT,
    tokens_used INTEGER DEFAULT 0,
    cost REAL DEFAULT 0.0,
    timestamp REAL NOT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS file_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    operation TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_before TEXT,
    content_after TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS api_configs (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    name TEXT NOT NULL,
    base_url TEXT,
    model_id TEXT,
    api_key_encrypted TEXT,
    settings TEXT DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    model TEXT,
    provider TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost REAL DEFAULT 0.0,
    response_time REAL DEFAULT 0.0,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    language TEXT,
    content TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS project_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at REAL
);

CREATE TABLE IF NOT EXISTS project_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    workspace TEXT NOT NULL,
    summary TEXT DEFAULT '',
    files_list TEXT DEFAULT '[]',
    tech_stack TEXT DEFAULT '',
    last_task TEXT DEFAULT '',
    conversation_snapshot TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_file_ops_session ON file_operations(session_id);
CREATE INDEX IF NOT EXISTS idx_usage_stats_model ON usage_stats(model);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_memory_name ON project_memory(project_name);
"""


class Database:
    """Async SQLite database for NexaCode persistence."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_FILE)
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Initialize database connection."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    # ─────────────────────────────────────────────────
    # SESSION OPERATIONS
    # ─────────────────────────────────────────────────
    async def create_session(self, session_id: str, name: str, workspace: str = "", model: str = "", agent: str = "") -> Dict:
        now = time.time()
        await self._db.execute(
            "INSERT OR REPLACE INTO sessions (id, name, workspace, model, agent, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, name, workspace, model, agent, now, now),
        )
        await self._db.commit()
        return {"id": session_id, "name": name, "created_at": now}

    async def get_session(self, session_id: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_sessions(self, limit: int = 50) -> List[Dict]:
        async with self._db.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_session(self, session_id: str):
        await self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await self._db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await self._db.commit()

    async def update_session(self, session_id: str, **kwargs):
        kwargs["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [session_id]
        await self._db.execute(f"UPDATE sessions SET {sets} WHERE id = ?", values)
        await self._db.commit()

    # ─────────────────────────────────────────────────
    # MESSAGE OPERATIONS
    # ─────────────────────────────────────────────────
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: str = "",
        model: str = "",
        tokens_used: int = 0,
        cost: float = 0.0,
        metadata: dict = None,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO messages (session_id, role, content, agent_name, model, tokens_used, cost, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, agent_name, model, tokens_used, cost, time.time(), json.dumps(metadata or {})),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_messages(self, session_id: str, limit: int = 100) -> List[Dict]:
        async with self._db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def search_messages(self, query: str, session_id: str = None, limit: int = 50) -> List[Dict]:
        if session_id:
            sql = "SELECT * FROM messages WHERE session_id = ? AND content LIKE ? ORDER BY timestamp DESC LIMIT ?"
            params = (session_id, f"%{query}%", limit)
        else:
            sql = "SELECT * FROM messages WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?"
            params = (f"%{query}%", limit)

        async with self._db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────────────
    # FILE OPERATION TRACKING
    # ─────────────────────────────────────────────────
    async def log_file_operation(
        self, session_id: str, operation: str, file_path: str,
        content_before: str = None, content_after: str = None,
    ):
        await self._db.execute(
            """INSERT INTO file_operations (session_id, operation, file_path, content_before, content_after, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, operation, file_path, content_before, content_after, time.time()),
        )
        await self._db.commit()

    async def get_file_history(self, file_path: str = None, session_id: str = None, limit: int = 50) -> List[Dict]:
        conditions = []
        params = []
        if file_path:
            conditions.append("file_path = ?")
            params.append(file_path)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        async with self._db.execute(
            f"SELECT * FROM file_operations {where} ORDER BY timestamp DESC LIMIT ?", params
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────────────
    # API CONFIG OPERATIONS
    # ─────────────────────────────────────────────────
    async def save_api_config(self, config_id: str, provider: str, name: str, base_url: str = "",
                               model_id: str = "", api_key: str = "", settings: dict = None):
        now = time.time()
        await self._db.execute(
            """INSERT OR REPLACE INTO api_configs (id, provider, name, base_url, model_id, api_key_encrypted, settings, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (config_id, provider, name, base_url, model_id, api_key, json.dumps(settings or {}), now, now),
        )
        await self._db.commit()

    async def get_api_configs(self) -> List[Dict]:
        async with self._db.execute("SELECT * FROM api_configs ORDER BY updated_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_api_config(self, config_id: str):
        await self._db.execute("DELETE FROM api_configs WHERE id = ?", (config_id,))
        await self._db.commit()

    # ─────────────────────────────────────────────────
    # USAGE STATISTICS
    # ─────────────────────────────────────────────────
    async def log_usage(self, session_id: str, model: str, provider: str,
                         input_tokens: int, output_tokens: int, cost: float, response_time: float):
        await self._db.execute(
            """INSERT INTO usage_stats (session_id, model, provider, input_tokens, output_tokens, cost, response_time, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, model, provider, input_tokens, output_tokens, cost, response_time, time.time()),
        )
        await self._db.commit()

    async def get_usage_summary(self) -> Dict:
        stats = {}
        async with self._db.execute(
            "SELECT model, SUM(input_tokens) as input_t, SUM(output_tokens) as output_t, SUM(cost) as total_cost, COUNT(*) as requests FROM usage_stats GROUP BY model"
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                r = dict(row)
                stats[r["model"]] = {
                    "input_tokens": r["input_t"],
                    "output_tokens": r["output_t"],
                    "total_cost": r["total_cost"],
                    "requests": r["requests"],
                }

        async with self._db.execute(
            "SELECT SUM(input_tokens) as t_in, SUM(output_tokens) as t_out, SUM(cost) as t_cost, COUNT(*) as t_req FROM usage_stats"
        ) as cursor:
            total = dict(await cursor.fetchone())

        return {"by_model": stats, "total": total}

    # ─────────────────────────────────────────────────
    # SNIPPETS
    # ─────────────────────────────────────────────────
    async def save_snippet(self, name: str, content: str, language: str = "", tags: list = None) -> int:
        cursor = await self._db.execute(
            "INSERT INTO snippets (name, language, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, language, content, json.dumps(tags or []), time.time()),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_snippets(self, language: str = None, limit: int = 50) -> List[Dict]:
        if language:
            sql = "SELECT * FROM snippets WHERE language = ? ORDER BY created_at DESC LIMIT ?"
            params = (language, limit)
        else:
            sql = "SELECT * FROM snippets ORDER BY created_at DESC LIMIT ?"
            params = (limit,)

        async with self._db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────────────
    # PROJECT CACHE
    # ─────────────────────────────────────────────────
    async def cache_set(self, key: str, value: Any, ttl: int = None):
        expires = time.time() + ttl if ttl else None
        await self._db.execute(
            "INSERT OR REPLACE INTO project_cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), expires),
        )
        await self._db.commit()

    async def cache_get(self, key: str) -> Optional[Any]:
        async with self._db.execute("SELECT value, expires_at FROM project_cache WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                if r["expires_at"] and r["expires_at"] < time.time():
                    await self._db.execute("DELETE FROM project_cache WHERE key = ?", (key,))
                    await self._db.commit()
                    return None
                return json.loads(r["value"])
            return None

    # ─────────────────────────────────────────────────
    # PROJECT MEMORY OPERATIONS
    # ─────────────────────────────────────────────────
    async def save_project_memory(
        self,
        project_name: str,
        workspace: str,
        summary: str = "",
        files_list: list = None,
        tech_stack: str = "",
        last_task: str = "",
        conversation_snapshot: list = None,
    ):
        """Save or update project memory for resuming later."""
        now = time.time()
        existing = await self.get_project_memory(project_name)
        if existing:
            await self._db.execute(
                """UPDATE project_memory
                   SET workspace=?, summary=?, files_list=?, tech_stack=?,
                       last_task=?, conversation_snapshot=?, updated_at=?
                   WHERE project_name=?""",
                (
                    workspace,
                    summary or existing.get("summary", ""),
                    json.dumps(files_list) if files_list is not None else existing.get("files_list", "[]"),
                    tech_stack or existing.get("tech_stack", ""),
                    last_task or existing.get("last_task", ""),
                    json.dumps(conversation_snapshot) if conversation_snapshot is not None else existing.get("conversation_snapshot", "[]"),
                    now,
                    project_name,
                ),
            )
        else:
            await self._db.execute(
                """INSERT INTO project_memory
                   (project_name, workspace, summary, files_list, tech_stack,
                    last_task, conversation_snapshot, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_name, workspace, summary,
                    json.dumps(files_list or []),
                    tech_stack, last_task,
                    json.dumps(conversation_snapshot or []),
                    now, now,
                ),
            )
        await self._db.commit()

    async def get_project_memory(self, project_name: str) -> Optional[Dict]:
        """Get project memory by name."""
        async with self._db.execute(
            "SELECT * FROM project_memory WHERE project_name = ?", (project_name,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(row)
                # Parse JSON fields
                try:
                    d["files_list"] = json.loads(d.get("files_list", "[]"))
                except Exception:
                    d["files_list"] = []
                try:
                    d["conversation_snapshot"] = json.loads(d.get("conversation_snapshot", "[]"))
                except Exception:
                    d["conversation_snapshot"] = []
                return d
            return None

    async def list_project_memories(self, limit: int = 50) -> List[Dict]:
        """List all saved project memories."""
        async with self._db.execute(
            "SELECT project_name, workspace, summary, tech_stack, last_task, updated_at FROM project_memory ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_project_memory(self, project_name: str):
        """Delete a project memory."""
        await self._db.execute("DELETE FROM project_memory WHERE project_name = ?", (project_name,))
        await self._db.commit()
