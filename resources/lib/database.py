import json
import os
import shutil
import sqlite3
import time

import xbmcvfs


PROFILE = xbmcvfs.translatePath("special://profile/addon_data/plugin.program.appliance.games")
DB_PATH = os.path.join(PROFILE, "games.db")
IMPORT_PATH = os.path.join(PROFILE, "playnite-export.json")
MEDIA_PATH = os.path.join(PROFILE, "media")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_name TEXT,
    description TEXT,
    release_date TEXT,
    year INTEGER,
    developer TEXT,
    publisher TEXT,
    genres TEXT,
    platforms TEXT,
    community_score REAL,
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
    if "trailer" not in columns:
        conn.execute("ALTER TABLE games ADD COLUMN trailer TEXT")
    return conn


def _text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " / ".join(str(item) for item in value if item)
    return str(value)


def _owned_artwork(game_id, role, source):
    """Copy imported artwork into Kodi storage and return only a Kodi path."""
    filename = "landscape" if role == "icon" else role
    directory = os.path.join(MEDIA_PATH, game_id)
    os.makedirs(directory, exist_ok=True)
    if source and os.path.isfile(source):
        extension = os.path.splitext(source)[1].lower() or ".img"
        destination = os.path.join(directory, filename + extension)
        if os.path.normcase(os.path.abspath(source)) != os.path.normcase(
            os.path.abspath(destination)
        ):
            temporary = destination + ".import"
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
        return destination
    for extension in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".ico", ".img"):
        existing = os.path.join(directory, filename + extension)
        if os.path.isfile(existing):
            return existing
    return ""


def import_export(path=IMPORT_PATH):
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    games = payload.get("games", payload if isinstance(payload, list) else [])
    count = 0
    with connect() as conn:
        for game in games:
            executable = game.get("executable", "")
            if not executable:
                continue
            values = {
                "id": game["id"],
                "name": game.get("name") or "Unknown game",
                "sort_name": game.get("sort_name") or game.get("name") or "",
                "description": game.get("description") or "",
                "release_date": game.get("release_date") or "",
                "year": game.get("year"),
                "developer": _text(game.get("developers")),
                "publisher": _text(game.get("publishers")),
                "genres": _text(game.get("genres")),
                "platforms": _text(game.get("platforms")),
                "community_score": game.get("community_score"),
                "executable": executable,
                "arguments": game.get("arguments") or "",
                "working_directory": game.get("working_directory") or os.path.dirname(executable),
                "install_directory": game.get("install_directory") or os.path.dirname(executable),
                "cover": _owned_artwork(game["id"], "cover", game.get("cover") or ""),
                "background": _owned_artwork(
                    game["id"], "background", game.get("background") or ""
                ),
                "icon": "",
                "logo": _owned_artwork(game["id"], "logo", game.get("logo") or ""),
                "trailer": game.get("trailer") or "",
                "favorite": int(bool(game.get("favorite"))),
                "hidden": int(bool(game.get("hidden"))),
                "installed": int(bool(game.get("installed", True))),
                "play_count": int(game.get("play_count") or 0),
                "playtime_seconds": int(game.get("playtime_seconds") or 0),
                "last_played": game.get("last_played"),
                "source": game.get("source") or "playnite-import",
                "source_id": game.get("source_id") or game["id"],
            }
            # Landscape is deliberately the same file content as background.
            values["icon"] = _owned_artwork(
                game["id"], "icon", values["background"]
            )
            columns = ", ".join(values)
            placeholders = ", ".join(":" + key for key in values)
            updates = ", ".join(
                f"{key}=excluded.{key}"
                for key in values
                if key not in {
                    "id",
                    "play_count",
                    "playtime_seconds",
                    "last_played",
                    "description",
                    "trailer",
                }
            )
            updates += (
                ", description=CASE WHEN games.description IS NULL "
                "OR games.description = '' THEN excluded.description "
                "ELSE games.description END"
                ", trailer=CASE WHEN excluded.trailer != '' "
                "THEN excluded.trailer ELSE games.trailer END"
            )
            conn.execute(
                f"INSERT INTO games ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}, updated_at=CURRENT_TIMESTAMP",
                values,
            )
            count += 1
    return count


def list_games(where="installed = 1 AND hidden = 0", params=(), order="name COLLATE NOCASE"):
    with connect() as conn:
        return conn.execute(f"SELECT * FROM games WHERE {where} ORDER BY {order}", params).fetchall()


def get_game(game_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()


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


def add_or_update_metadata(game_id, executable, values, cover="", background="", logo="", icon=""):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO games (
                id, name, sort_name, description, release_date, year,
                developer, publisher, genres, platforms, community_score,
                executable, working_directory, install_directory,
                cover, background, logo, icon, trailer, installed, source, source_id
            ) VALUES (
                :id, :name, :name, :description, :release_date, :year,
                :developer, :publisher, :genres, :platforms, :community_score,
                :executable, :working_directory, :working_directory,
                :cover, :background, :logo, :icon, :trailer, 1, 'igdb', :source_id
            )
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                sort_name=excluded.sort_name,
                description=excluded.description,
                release_date=excluded.release_date,
                year=excluded.year,
                developer=excluded.developer,
                publisher=excluded.publisher,
                genres=excluded.genres,
                platforms=excluded.platforms,
                community_score=excluded.community_score,
                executable=CASE WHEN excluded.executable != '' THEN excluded.executable ELSE games.executable END,
                working_directory=CASE WHEN excluded.executable != '' THEN excluded.working_directory ELSE games.working_directory END,
                install_directory=CASE WHEN excluded.executable != '' THEN excluded.working_directory ELSE games.install_directory END,
                cover=CASE WHEN excluded.cover != '' THEN excluded.cover ELSE games.cover END,
                background=CASE WHEN excluded.background != '' THEN excluded.background ELSE games.background END,
                logo=CASE WHEN excluded.logo != '' THEN excluded.logo ELSE games.logo END,
                icon=CASE WHEN excluded.icon != '' THEN excluded.icon ELSE games.icon END,
                trailer=CASE WHEN excluded.trailer != '' THEN excluded.trailer ELSE games.trailer END,
                source='igdb',
                source_id=excluded.source_id,
                updated_at=CURRENT_TIMESTAMP
            """,
            {
                "id": game_id,
                "name": values["name"],
                "description": values["description"],
                "release_date": values["release_date"],
                "year": values["year"],
                "developer": values["developer"],
                "publisher": values["publisher"],
                "genres": values["genres"],
                "platforms": values["platforms"],
                "community_score": values["community_score"],
                "executable": executable,
                "working_directory": os.path.dirname(executable) if executable else "",
                "cover": cover,
                "background": background,
                "logo": logo,
                "icon": icon,
                "trailer": values.get("trailer") or "",
                "source_id": values["igdb_id"],
            },
        )


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
