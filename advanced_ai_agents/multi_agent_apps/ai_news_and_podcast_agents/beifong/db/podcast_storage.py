import fcntl
import json
from pathlib import Path
import sqlite3

from agno.db.base import SessionType
from agno.db.migrations.v1_to_v2 import parse_agent_sessions
from agno.db.sqlite import SqliteDb


def _decode(value):
    while isinstance(value, str):
        value = json.loads(value)
    return value


def get_podcast_db(filename):
    filename = str(Path(filename).resolve())
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    db = SqliteDb(db_file=filename, session_table="podcast_sessions_v2")
    with open(filename + ".migration.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with sqlite3.connect(filename) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                "SELECT type FROM sqlite_master WHERE name = 'podcast_sessions'"
            ).fetchone()
            if existing and existing["type"] == "view":
                return db
            db._get_table(table_type="sessions", create_table_if_not_found=True)
            if existing:
                for row in connection.execute("SELECT * FROM podcast_sessions").fetchall():
                    source = dict(row)
                    for key in ("memory", "session_data", "agent_data", "extra_data"):
                        if source.get(key) is not None:
                            source[key] = _decode(source[key])
                    expected_runs = (source.get("memory") or {}).get("runs") or []
                    if source.get("memory") and not expected_runs:
                        source["memory"]["runs"] = None
                    sessions = parse_agent_sessions([source])
                    if len(sessions) != 1:
                        raise ValueError(f"Cannot migrate session {source['session_id']}")
                    if len(sessions[0].runs or []) != len(expected_runs):
                        raise ValueError(f"Migration would lose runs for {source['session_id']}")
                    db.upsert_sessions(sessions, preserve_updated_at=True)
                    saved = db.get_session(source["session_id"], SessionType.AGENT)
                    if saved is None or len(saved.runs or []) != len(expected_runs):
                        raise ValueError(f"Migration verification failed for {source['session_id']}")
                    if saved.session_data != sessions[0].session_data:
                        raise ValueError(f"Migration would change state for {source['session_id']}")
            connection.execute("BEGIN IMMEDIATE")
            if existing:
                connection.execute("ALTER TABLE podcast_sessions RENAME TO podcast_sessions_v1_backup")
            connection.execute("""
                CREATE VIEW podcast_sessions AS
                SELECT session_id, agent_id, user_id, created_at, updated_at,
                    CASE WHEN json_type(session_data) = 'text'
                        THEN json_extract(session_data, '$') ELSE session_data END AS session_data,
                    json_object('runs', json(CASE WHEN json_type(runs) = 'text'
                        THEN json_extract(runs, '$') ELSE COALESCE(runs, '[]') END)) AS memory
                FROM podcast_sessions_v2 WHERE session_type = 'agent'
            """)
            connection.execute("""
                CREATE TRIGGER delete_podcast_session INSTEAD OF DELETE ON podcast_sessions
                BEGIN
                    DELETE FROM podcast_sessions_v2 WHERE session_id = OLD.session_id;
                END
            """)
            connection.commit()
    return db
