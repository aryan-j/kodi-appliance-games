import os
import gc
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest import mock


class _Addon:
    def getAddonInfo(self, key):
        return tempfile.gettempdir()

    def getSettingString(self, _key):
        return ""


sys.modules.setdefault("xbmcaddon", types.SimpleNamespace(Addon=lambda: _Addon()))
sys.modules.setdefault("xbmcvfs", types.SimpleNamespace(translatePath=lambda value: value))

from resources.lib import database, metadata


class MetadataTests(unittest.TestCase):
    def test_normalize_rich_fields(self):
        values = metadata.normalize(
            {
                "id": 7,
                "name": "Example",
                "summary": "Summary",
                "storyline": "Story",
                "first_release_date": 946684800,
                "rating": 84.5,
                "rating_count": 123,
                "updated_at": 99,
                "franchise": {"name": "Series"},
                "franchises": [{"name": "Series"}, {"name": "Universe"}],
                "game_engines": [{"name": "Engine"}],
                "genres": [{"name": "Action"}],
                "platforms": [{"name": "PC"}],
                "game_modes": [{"name": "Single player"}],
                "player_perspectives": [{"name": "Third person"}],
                "themes": [{"name": "Science fiction"}],
                "involved_companies": [
                    {"publisher": True, "company": {"name": "Publisher"}},
                    {"developer": True, "company": {"name": "Developer"}},
                ],
            },
            {"hastily": 3600, "normally": 5400, "completely": 7200, "count": 10},
        )
        self.assertEqual(values["franchise"], "Series / Universe")
        self.assertEqual(values["publisher"], "Publisher")
        self.assertEqual(values["engines"], "Engine")
        self.assertEqual(values["community_score_count"], 123)
        self.assertEqual(values["time_to_beat_normally"], 5400)
        self.assertEqual(values["igdb_summary"], "Summary")

    def test_time_to_beat_uses_its_own_endpoint(self):
        with mock.patch.object(metadata, "_query", return_value=[{"normally": 120}]) as query:
            self.assertEqual(metadata.get_time_to_beat(7)["normally"], 120)
        self.assertEqual(query.call_args.kwargs["endpoint"], "game_time_to_beats")

    def test_persisted_steamgriddb_id_skips_title_search(self):
        def response(path):
            if path.startswith("/grids/"):
                return []
            return []
        with mock.patch.object(metadata, "steamgriddb_game", side_effect=AssertionError("title search used")):
            with mock.patch.object(metadata, "_sgdb_request", side_effect=response):
                result = metadata.steamgriddb_art("Renamed", "42")
        self.assertEqual(result["game_id"], "42")

    def test_steamgriddb_art_selects_distinct_near_16_9_landscape(self):
        def response(path):
            if "dimensions=600x900" in path:
                return [{"url": "cover.jpg", "width": 600, "height": 900, "upvotes": 1}]
            if "dimensions=460x215" in path:
                return [
                    {"url": "header.jpg", "width": 460, "height": 215, "upvotes": 1},
                ]
            if path.startswith("/heroes/"):
                return [{"url": "hero.jpg", "width": 1920, "height": 620, "upvotes": 2}]
            return []

        with mock.patch.object(metadata, "steamgriddb_game", side_effect=AssertionError("title search used")):
            with mock.patch.object(metadata, "_sgdb_request", side_effect=response):
                result = metadata.steamgriddb_art("Renamed", "42")
        self.assertEqual(result["background"], "hero.jpg")
        self.assertEqual(result["landscape"], "header.jpg")

    def test_landscape_dimension_400_falls_back_to_supported_size(self):
        def response(path):
            if "dimensions=600x900" in path:
                return []
            if "dimensions=460x215" in path:
                raise RuntimeError("HTTP 400")
            if "dimensions=460x259" in path:
                return [{"url": "fallback.jpg", "width": 460, "height": 259}]
            if path.startswith("/heroes/"):
                return []
            return []

        with mock.patch.object(metadata, "steamgriddb_game", side_effect=AssertionError("title search used")):
            with mock.patch.object(metadata, "_sgdb_request", side_effect=response):
                result = metadata.steamgriddb_art("Renamed", "42")
        self.assertEqual(result["landscape"], "fallback.jpg")

    def test_landscape_filter_failure_preserves_other_artwork_selection(self):
        def response(path):
            if "dimensions=460x215" in path or "dimensions=460x259" in path:
                raise RuntimeError("unsupported dimensions filter")
            if "dimensions=600x900" in path:
                return [{"url": "cover.jpg", "width": 600, "height": 900}]
            if path.startswith("/heroes/"):
                return [{"url": "hero.jpg", "width": 1920, "height": 620}]
            return []

        with mock.patch.object(metadata, "steamgriddb_game", side_effect=AssertionError("title search used")):
            with mock.patch.object(metadata, "_sgdb_request", side_effect=response):
                result = metadata.steamgriddb_art("Renamed", "42")
        self.assertEqual(result["cover"], "cover.jpg")
        self.assertEqual(result["background"], "hero.jpg")
        self.assertEqual(result["landscape"], "")


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous = database.DB_PATH
        self.previous_profile = database.PROFILE
        database.PROFILE = self.tempdir.name
        database.DB_PATH = os.path.join(self.tempdir.name, "games.db")

    def tearDown(self):
        database.DB_PATH = self.previous
        database.PROFILE = self.previous_profile
        gc.collect()
        self.tempdir.cleanup()

    def test_migration_is_idempotent_and_metadata_preserves_runtime_fields(self):
        database.connect().close()
        database.connect().close()
        with database.connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(games)")}
            self.assertIn("steamgriddb_id", columns)
            self.assertFalse(any("critic" in name for name in columns))
            conn.execute(
                """
                INSERT INTO games (
                    id, name, description, executable, cover, favorite, play_count,
                    playtime_seconds, source, source_id
                ) VALUES ('g1', 'Old', 'Curated plot', 'game.exe', 'old.jpg', 1, 4, 500, 'legacy', '1')
                """
            )
        values = {
            "name": "New", "description": "IGDB plot", "igdb_summary": "IGDB plot",
            "release_date": "2020-01-01",
            "year": 2020, "developer": "Dev", "publisher": "Pub",
            "genres": "Action", "platforms": "PC", "community_score": 80.0,
            "community_score_count": 20, "franchise": "Series", "engines": "Engine",
            "storyline": "Story", "game_modes": "Single player",
            "player_perspectives": "Third person", "themes": "Science fiction",
            "time_to_beat_hastily": 3600, "time_to_beat_normally": 5400,
            "time_to_beat_completely": 7200, "time_to_beat_count": 5,
            "igdb_updated_at": 100, "trailer": "", "igdb_id": "7",
        }
        database.add_or_update_metadata("g1", "", values)
        row = database.get_game("g1")
        self.assertEqual(row["name"], "New")
        self.assertEqual(row["description"], "Curated plot")
        self.assertEqual(row["igdb_summary"], "IGDB plot")
        self.assertEqual(row["cover"], "old.jpg")
        self.assertEqual(row["executable"], "game.exe")
        self.assertEqual((row["favorite"], row["play_count"], row["playtime_seconds"]), (1, 4, 500))

        database.add_or_update_metadata("g2", "new.exe", values)
        new_row = database.get_game("g2")
        self.assertEqual(new_row["description"], "IGDB plot")
        self.assertEqual(new_row["igdb_summary"], "IGDB plot")

    def test_artwork_and_related_filters_are_isolated(self):
        with database.connect() as conn:
            for row in (
                ("a", "Alpha", 2020, "Pub", "Action / RPG"),
                ("b", "Beta", 2020, "Other", "Action"),
                ("c", "Gamma", 2021, "Pub", "Puzzle"),
            ):
                conn.execute(
                    "INSERT INTO games (id,name,year,publisher,genres,executable) VALUES (?,?,?,?,?,?)",
                    (*row, "game.exe"),
                )
        database.update_artwork("a", {"cover": "new.jpg"}, "42")
        row = database.get_game("a")
        self.assertEqual((row["cover"], row["steamgriddb_id"], row["name"]), ("new.jpg", "42", "Alpha"))
        self.assertEqual([row["id"] for row in database.related_games("a", "year")], ["b"])
        self.assertEqual([row["id"] for row in database.related_games("a", "publisher")], ["c"])
        self.assertEqual([row["id"] for row in database.related_games("a", "genre")], ["b"])


if __name__ == "__main__":
    unittest.main()
