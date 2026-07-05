import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "memory.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                date        TEXT NOT NULL,
                project     TEXT,
                started_at  TEXT NOT NULL,
                ended_at    TEXT,
                model       TEXT,
                turn_count  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL REFERENCES sessions(id),
                turn_index  INTEGER NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT,
                tool_name   TEXT,
                created_at  TEXT NOT NULL
            );
        """)
        # Add columns to existing DBs that predate this schema change.
        for col, definition in [("date", "TEXT NOT NULL DEFAULT ''"), ("project", "TEXT")]:
            try:
                con.execute(f"ALTER TABLE sessions ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass  # column already exists


def find_session(date: str, project: str | None) -> dict | None:
    """Return session metadata for the given date+project, or None if not found."""
    with _conn() as con:
        row = con.execute(
            "SELECT id, date, project, started_at, model, turn_count FROM sessions "
            "WHERE date = ? AND project IS ? ORDER BY started_at DESC LIMIT 1",
            (date, project),
        ).fetchone()
    return dict(row) if row else None


def save_session(
    session_id: str,
    messages: list[dict],
    model: str,
    date: str,
    project: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    user_turns = sum(1 for m in messages if m["role"] == "user")

    with _conn() as con:
        con.execute(
            """
            INSERT INTO sessions (id, date, project, started_at, ended_at, model, turn_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                ended_at   = excluded.ended_at,
                turn_count = excluded.turn_count
            """,
            (session_id, date, project, now, now, model, user_turns),
        )
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        con.executemany(
            """
            INSERT INTO messages (session_id, turn_index, role, content, tool_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (session_id, i, m["role"], m.get("content", ""), m.get("tool_name"), now)
                for i, m in enumerate(messages)
            ],
        )


def load_session(session_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content, tool_name FROM messages "
            "WHERE session_id = ? ORDER BY turn_index",
            (session_id,),
        ).fetchall()
    if not rows:
        return []
    return [
        {k: row[k] for k in ("role", "content", "tool_name") if row[k] is not None}
        for row in rows
    ]


def list_sessions() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, date, project, started_at, ended_at, model, turn_count "
            "FROM sessions ORDER BY started_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
