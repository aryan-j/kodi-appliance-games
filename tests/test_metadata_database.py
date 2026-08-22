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

    def test_verified_steam_candidates_prefer_explicit_english_image2x(self):
        details = {
            "id": 42,
            "verified": True,
            "types": ["steam"],
            "external_platform_data": {
                "steam": [{
                    "id": "123",
                    "metadata": {
                        "library_capsule": {"en": {
                            "image": "library_600x900.jpg",
                            "image2x": "library_600x900_2x.jpg",
                        }},
                        "library_hero": {"en": "library_hero.jpg"},
                        "library_logo": {"en": "library_logo.png"},
                        "header": {"en": "header.jpg"},
                    },
                }],
            },
        }
        candidates = metadata._steam_asset_candidates(details)
        base = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/123/"
        self.assertEqual(candidates["cover"][0], base + "library_600x900_2x.jpg")
        self.assertEqual(candidates["cover"][1], base + "library_600x900.jpg")
        self.assertEqual(candidates["background"][0], base + "library_hero_2x.jpg")
        self.assertEqual(candidates["landscape"][0], base + "header_2x.jpg")

    def test_verified_steam_assets_do_not_append_community_fallback(self):
        details = {
            "verified": True,
            "types": ["steam"],
            "external_platform_data": {"steam": [{
                "id": "123",
                "metadata": {"library_logo": {"en": "logo.png"}},
            }]},
        }
        with mock.patch.object(metadata, "_sgdb_game_details", return_value=details):
            with mock.patch.object(metadata, "_sgdb_request", side_effect=lambda path: (
                [{"url": "cover.jpg", "width": 600, "height": 900}]
                if "dimensions=600x900" in path else
                [{"url": "hero.jpg", "width": 1920, "height": 620}]
                if path.startswith("/heroes/") else
                []
            )):
                result = metadata.steamgriddb_art("Example", "42")
        self.assertNotIn("cover_candidates", result)
        self.assertEqual(result["logo_candidates"][0].rsplit("/", 1)[-1], "logo_2x.png")

    def test_steam_asset_url_normalizes_existing_store_item_path(self):
        self.assertEqual(
            metadata._steam_asset_url(
                123,
                "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/123/header.jpg",
            ),
            "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/123/header.jpg",
        )

    def test_steam_candidates_ignore_non_english_when_english_exists(self):
        details = {
            "verified": True,
            "types": ["steam"],
            "external_platform_data": {"steam": [{
                "id": "123",
                "metadata": {"header": {
                    "de": "de/header.jpg",
                    "en": "en/header.jpg",
                }},
            }]},
        }
        self.assertEqual(
            metadata._steam_asset_candidates(details)["landscape"][0],
            "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/123/en/header_2x.jpg",
        )

    def test_steam_candidates_reject_wrong_language_aliases_and_asset_objects(self):
        details = {
            "verified": True,
            "types": ["steam"],
            "external_platform_data": {"steam": [{
                "id": "123",
                "metadata": {
                    "library_logo": [
                        {"language": "de", "url": "de/logo.png"},
                        {"language": "en", "url": "en/logo.png"},
                    ],
                    "header": {"de": "de/header.jpg", "en": "en/header.jpg"},
                    # The alias must not reintroduce a German path after the
                    # English header map has been selected.
                    "header_image": "de/header-alias.jpg",
                },
            }]},
        }
        candidates = metadata._steam_asset_candidates(details)
        base = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/123/"
        self.assertEqual(candidates["logo"][0], base + "en/logo_2x.png")
        self.assertEqual(candidates["landscape"][0], base + "en/header_2x.jpg")
        self.assertNotIn("de/header-alias.jpg", "".join(candidates["landscape"]))

    def test_steam_candidates_leave_role_empty_when_only_non_english_asset_exists(self):
        details = {
            "verified": True,
            "types": ["steam"],
            "external_platform_data": {"steam": [{
                "id": "123",
                "metadata": {"library_logo": {"de": "de/logo.png"}},
            }]},
        }
        self.assertNotIn("logo", metadata._steam_asset_candidates(details))

    def test_sgdb_fallback_prefers_english_images_when_present(self):
        images = [
            {"url": "unlabeled.jpg", "language": "", "width": 600, "height": 900, "upvotes": 99},
            {"url": "german.jpg", "language": "de", "width": 600, "height": 900, "upvotes": 100},
            {"url": "english.jpg", "language": "en", "width": 600, "height": 900, "upvotes": 1},
        ]
        self.assertEqual(metadata._best_image(images, orientation="portrait")["url"], "english.jpg")

    def test_unverified_or_non_steam_details_use_community_art(self):
        for details in (
            {"id": 42, "verified": False, "types": ["steam"]},
            {"id": 42, "verified": True, "types": ["gog"]},
        ):
            with mock.patch.object(metadata, "_sgdb_game_details", return_value=details):
                with mock.patch.object(metadata, "_sgdb_request", side_effect=lambda path: (
                    [{"url": "cover.jpg", "width": 600, "height": 900}]
                    if "dimensions=600x900" in path else
                    [{"url": "hero.jpg", "width": 1920, "height": 620}]
                    if path.startswith("/heroes/") else []
                )):
                    result = metadata.steamgriddb_art("Example", "42")
            self.assertEqual(result["cover"], "cover.jpg")
            self.assertEqual(result["background"], "hero.jpg")
            self.assertNotIn("cover_candidates", result)


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

    def test_remove_game_keeps_external_executable_and_cascades_sessions(self):
        executable = os.path.join(self.tempdir.name, "game.exe")
        with open(executable, "wb") as stream:
            stream.write(b"game")
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO games (id, name, executable) VALUES (?, ?, ?)",
                ("g1", "Example", executable),
            )
        database.queue_launch("g1")

        removed = database.remove_game("g1")

        self.assertEqual(removed["id"], "g1")
        self.assertIsNone(database.get_game("g1"))
        with database.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
        self.assertTrue(os.path.isfile(executable))


if __name__ == "__main__":
    unittest.main()
