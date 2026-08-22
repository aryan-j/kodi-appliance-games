import os
import sqlite3
import time

import xbmcvfs


PROFILE = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.appliance.games")
DB_PATH = os.path.join(PROFILE, "games.db")
SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_name TEXT,
    description TEXT,
    igdb_summary TEXT,
    release_date TEXT,
    year INTEGER,
    developer TEXT,
    publisher TEXT,
    genres TEXT,
    platforms TEXT,
    community_score REAL,
    community_score_count INTEGER NOT NULL DEFAULT 0,
    franchise TEXT,
    engines TEXT,
    storyline TEXT,
    game_modes TEXT,
    player_perspectives TEXT,
    themes TEXT,
    time_to_beat_hastily INTEGER NOT NULL DEFAULT 0,
    time_to_beat_normally INTEGER NOT NULL DEFAULT 0,
    time_to_beat_completely INTEGER NOT NULL DEFAULT 0,
    time_to_beat_count INTEGER NOT NULL DEFAULT 0,
    steamgriddb_id TEXT,
    igdb_updated_at INTEGER NOT NULL DEFAULT 0,
    metadata_refreshed_at TEXT,
    artwork_refreshed_at TEXT,
    executable TEXT NOT NULL,
    arguments TEXT,
    working_directory TEXT,
    install_directory TEXT,
    cover TEXT,
    background TEXT,
    icon TEXT,
    logo TEXT,
    trailer TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    hidden INTEGER NOT NULL DEFAULT 0,
    installed INTEGER NOT NULL DEFAULT 1,
    play_count INTEGER NOT NULL DEFAULT 0,
    playtime_seconds INTEGER NOT NULL DEFAULT 0,
    last_played TEXT,
    source TEXT,
    source_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    ended_at TEXT,
    duration_seconds INTEGER,
    process_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_games_name ON games(name);
CREATE INDEX IF NOT EXISTS idx_games_last_played ON games(last_played);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
"""


def connect():
    os.makedirs(PROFILE, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(games)")}
    migrations = {
        "trailer": "TEXT",
        "igdb_summary": "TEXT",
        "community_score_count": "INTEGER NOT NULL DEFAULT 0",
        "franchise": "TEXT",
        "engines": "TEXT",
        "storyline": "TEXT",
        "game_modes": "TEXT",
        "player_perspectives": "TEXT",
        "themes": "TEXT",
        "time_to_beat_hastily": "INTEGER NOT NULL DEFAULT 0",
        "time_to_beat_normally": "INTEGER NOT NULL DEFAULT 0",
        "time_to_beat_completely": "INTEGER NOT NULL DEFAULT 0",
        "time_to_beat_count": "INTEGER NOT NULL DEFAULT 0",
        "steamgriddb_id": "TEXT",
        "igdb_updated_at": "INTEGER NOT NULL DEFAULT 0",
        "metadata_refreshed_at": "TEXT",
        "artwork_refreshed_at": "TEXT",
    }
    for name, declaration in migrations.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE games ADD COLUMN {name} {declaration}")
    return conn


def list_games(where="installed = 1 AND hidden = 0", params=(), order="name COLLATE NOCASE"):
    with connect() as conn:
        return conn.execute(f"SELECT * FROM games WHERE {where} ORDER BY {order}", params).fetchall()


def get_game(game_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()


def remove_game(game_id):
    """Stop tracking a game without touching its executable or install files."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        return row


def set_favorite(game_id, favorite):
    with connect() as conn:
        conn.execute(
            "UPDATE games SET favorite = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(bool(favorite)), game_id),
        )


def update_executable(game_id, executable):
    with connect() as conn:
        conn.execute(
            """
            UPDATE games
            SET executable = ?, working_directory = ?, installed = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (executable, os.path.dirname(executable), game_id),
        )


def add_or_update_metadata(game_id, executable, values):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO games (
                id, name, sort_name, description, igdb_summary, release_date, year,
                developer, publisher, genres, platforms, community_score,
                community_score_count, franchise, engines, storyline,
                game_modes, player_perspectives, themes,
                time_to_beat_hastily, time_to_beat_normally,
                time_to_beat_completely, time_to_beat_count, igdb_updated_at,
                executable, working_directory, install_directory,
                trailer, installed, source, source_id, metadata_refreshed_at
            ) VALUES (
                :id, :name, :name, :description, :igdb_summary, :release_date, :year,
                :developer, :publisher, :genres, :platforms, :community_score,
                :community_score_count, :franchise, :engines, :storyline,
                :game_modes, :player_perspectives, :themes,
                :time_to_beat_hastily, :time_to_beat_normally,
                :time_to_beat_completely, :time_to_beat_count, :igdb_updated_at,
                :executable, :working_directory, :working_directory,
                :trailer, 1, 'igdb', :source_id, CURRENT_TIMESTAMP
            )
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                sort_name=excluded.sort_name,
                description=CASE
                    WHEN games.description IS NULL OR games.description = '' THEN excluded.description
                    ELSE games.description
                END,
                igdb_summary=excluded.igdb_summary,
                release_date=excluded.release_date,
                year=excluded.year,
                developer=excluded.developer,
                publisher=excluded.publisher,
                genres=excluded.genres,
                platforms=excluded.platforms,
                community_score=excluded.community_score,
                community_score_count=excluded.community_score_count,
                franchise=excluded.franchise,
                engines=excluded.engines,
                storyline=excluded.storyline,
                game_modes=excluded.game_modes,
                player_perspectives=excluded.player_perspectives,
                themes=excluded.themes,
                time_to_beat_hastily=excluded.time_to_beat_hastily,
                time_to_beat_normally=excluded.time_to_beat_normally,
                time_to_beat_completely=excluded.time_to_beat_completely,
                time_to_beat_count=excluded.time_to_beat_count,
                igdb_updated_at=excluded.igdb_updated_at,
                executable=CASE WHEN excluded.executable != '' THEN excluded.executable ELSE games.executable END,
                working_directory=CASE WHEN excluded.executable != '' THEN excluded.working_directory ELSE games.working_directory END,
                install_directory=CASE WHEN excluded.executable != '' THEN excluded.working_directory ELSE games.install_directory END,
                trailer=CASE WHEN excluded.trailer != '' THEN excluded.trailer ELSE games.trailer END,
                source='igdb',
                source_id=excluded.source_id,
                metadata_refreshed_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            """,
            {
                "id": game_id,
                "name": values["name"],
                "description": values["description"],
                "igdb_summary": values.get("igdb_summary") or values["description"],
                "release_date": values["release_date"],
                "year": values["year"],
                "developer": values["developer"],
                "publisher": values["publisher"],
                "genres": values["genres"],
                "platforms": values["platforms"],
                "community_score": values["community_score"],
                "community_score_count": values["community_score_count"],
                "franchise": values["franchise"],
                "engines": values["engines"],
                "storyline": values["storyline"],
                "game_modes": values["game_modes"],
                "player_perspectives": values["player_perspectives"],
                "themes": values["themes"],
                "time_to_beat_hastily": values["time_to_beat_hastily"],
                "time_to_beat_normally": values["time_to_beat_normally"],
                "time_to_beat_completely": values["time_to_beat_completely"],
                "time_to_beat_count": values["time_to_beat_count"],
                "igdb_updated_at": values["igdb_updated_at"],
                "executable": executable,
                "working_directory": os.path.dirname(executable) if executable else "",
                "trailer": values.get("trailer") or "",
                "source_id": values["igdb_id"],
            },
        )


def update_artwork(game_id, artwork, steamgriddb_id):
    assignments = []
    values = []
    for role in ("cover", "background", "logo", "icon"):
        if artwork.get(role):
            assignments.append(f"{role} = ?")
            values.append(artwork[role])
    assignments.extend(
        ["steamgriddb_id = ?", "artwork_refreshed_at = CURRENT_TIMESTAMP", "updated_at = CURRENT_TIMESTAMP"]
    )
    values.extend([str(steamgriddb_id or ""), game_id])
    with connect() as conn:
        conn.execute(
            f"UPDATE games SET {', '.join(assignments)} WHERE id = ?",
            values,
        )


def related_games(game_id, field):
    game = get_game(game_id)
    if not game:
        return []
    if field == "year" and game["year"]:
        return list_games("installed = 1 AND hidden = 0 AND id != ? AND year = ?", (game_id, game["year"]))
    if field == "publisher" and game["publisher"]:
        return list_games(
            "installed = 1 AND hidden = 0 AND id != ? AND publisher = ?",
            (game_id, game["publisher"]),
        )
    if field == "genre" and game["genres"]:
        wanted = {part.strip().casefold() for part in game["genres"].split("/") if part.strip()}
        return [
            candidate for candidate in list_games("installed = 1 AND hidden = 0 AND id != ?", (game_id,))
            if wanted.intersection(
                part.strip().casefold() for part in (candidate["genres"] or "").split("/") if part.strip()
            )
        ]
    return []


def queue_launch_command(game_id, name, executable, arguments=""):
    """Create a hidden diagnostic entry that exercises the normal launch service."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO games (
                id, name, executable, arguments, working_directory,
                hidden, installed, source
            ) VALUES (?, ?, ?, ?, ?, 1, 1, 'diagnostic')
            ON CONFLICT(id) DO UPDATE SET
                executable=excluded.executable,
                arguments=excluded.arguments,
                working_directory=excluded.working_directory
            """,
            (game_id, name, executable, arguments, os.path.dirname(executable)),
        )
        cursor = conn.execute(
            "INSERT INTO sessions (game_id, status) VALUES (?, 'pending')",
            (game_id,),
        )
        return cursor.lastrowid


def queue_launch(game_id):
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (game_id, status) VALUES (?, 'pending')",
            (game_id,),
        )
        return cursor.lastrowid


def next_pending_session():
    with connect() as conn:
        row = conn.execute(
            """
            SELECT sessions.id AS session_id, games.*
            FROM sessions
            JOIN games ON games.id = sessions.game_id
            WHERE sessions.status = 'pending'
            ORDER BY sessions.id
            LIMIT 1
            """
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE sessions SET status = 'starting', started_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["session_id"],),
            )
        return row


def mark_running(session_id, process_id):
    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET status = 'running', process_id = ? WHERE id = ?",
            (process_id, session_id),
        )


def finish_session(session_id, game_id, started_monotonic, error=None):
    duration = max(0, int(time.monotonic() - started_monotonic))
    status = "failed" if error else "completed"
    with connect() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET status = ?, ended_at = CURRENT_TIMESTAMP, duration_seconds = ?, error = ?
            WHERE id = ?
            """,
            (status, duration, error, session_id),
        )
        if not error:
            conn.execute(
                """
                UPDATE games
                SET play_count = play_count + 1,
                    playtime_seconds = playtime_seconds + ?,
                    last_played = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (duration, game_id),
            )
