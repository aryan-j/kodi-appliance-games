import os
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
sys.modules.setdefault("xbmc", types.SimpleNamespace())
sys.modules.setdefault("xbmcgui", types.SimpleNamespace())
sys.modules.setdefault("xbmcplugin", types.SimpleNamespace())
if len(sys.argv) < 2 or not str(sys.argv[1]).isdigit():
    sys.argv.insert(1, "1")

from resources.lib import router


class RouterArtworkTests(unittest.TestCase):
    def test_refresh_surfaces_never_reloads_skin(self):
        with mock.patch.object(router.xbmc, "getCondVisibility", return_value=True, create=True):
            with mock.patch.object(router.xbmc, "executebuiltin", create=True) as execute:
                router._refresh_game_surfaces(reload_skin=True)
        self.assertEqual(execute.call_args_list, [mock.call("ReplaceWindow(1102)")])
        self.assertNotIn("ReloadSkin", " ".join(call.args[0] for call in execute.call_args_list))

    def test_download_retries_ordered_candidates_and_preserves_failed_role(self):
        with tempfile.TemporaryDirectory() as profile:
            previous_profile = router.metadata.PROFILE
            router.metadata.PROFILE = profile
            try:
                game = {"id": "g1", "name": "Example", "steamgriddb_id": "42"}
                artwork = {
                    "game_id": "42",
                    "game_name": "Example",
                    "cover": "steam-cover-2x.jpg",
                    "cover_candidates": ["steam-cover-2x.jpg", "steam-cover.jpg", "community-cover.jpg"],
                    "background": "failed-background.jpg",
                    "background_candidates": ["failed-background.jpg"],
                    "landscape": "steam-header-2x.jpg",
                    "landscape_candidates": ["steam-header-2x.jpg", "steam-header.jpg"],
                }
                attempted = []

                def download(url, destination):
                    attempted.append(url)
                    if "2x" in url or "failed" in url:
                        raise OSError("not found")
                    with open(destination, "wb") as stream:
                        stream.write(b"art")

                def crop(_source, destination):
                    with open(destination, "wb") as stream:
                        stream.write(b"cropped")
                    return True

                with mock.patch.object(router.database, "get_game", return_value=game):
                    with mock.patch.object(router.database, "update_artwork") as update:
                        with mock.patch.object(router.metadata, "_sgdb_key", return_value="key"):
                            with mock.patch.object(router.metadata, "steamgriddb_art", return_value=artwork):
                                with mock.patch.object(router.metadata, "download", side_effect=download):
                                    with mock.patch.object(router.metadata, "crop_landscape", side_effect=crop):
                                        result = router._refresh_steamgriddb_artwork("g1")

                self.assertEqual(attempted[:3], [
                    "steam-cover-2x.jpg", "steam-cover.jpg", "failed-background.jpg",
                ])
                self.assertIn("steam-header-2x.jpg", attempted)
                self.assertIn("steam-header.jpg", attempted)
                committed = update.call_args.args[1]
                self.assertIn("cover", committed)
                self.assertIn("icon", committed)
                self.assertNotIn("background", committed)
                self.assertRegex(os.path.basename(committed["cover"]), r"^cover-[0-9a-f]{12}\.jpg$")
                self.assertRegex(os.path.basename(committed["icon"]), r"^icon-[0-9a-f]{12}\.jpg$")
                self.assertEqual(result, artwork)
                self.assertFalse(any(name.endswith(".download") for name in os.listdir(os.path.join(profile, "media", "g1"))))
            finally:
                router.metadata.PROFILE = previous_profile

    def test_landscape_crop_keeps_native_16_9_frame_and_preserves_failed_destination(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "source.jpg")
            destination = os.path.join(folder, "landscape.jpg")
            Image.new("RGB", (460, 215), (20, 80, 140)).save(source)
            self.assertTrue(router.metadata.crop_landscape(source, destination))
            with Image.open(destination) as cropped:
                self.assertLess(cropped.width, 460)
                self.assertEqual(cropped.height, 215)
                self.assertAlmostEqual(cropped.width / cropped.height, 16 / 9, places=2)
            with open(destination, "wb") as stream:
                stream.write(b"existing")
            self.assertFalse(router.metadata.crop_landscape(os.path.join(folder, "missing.jpg"), destination))
            with open(destination, "rb") as stream:
                self.assertEqual(stream.read(), b"existing")


if __name__ == "__main__":
    unittest.main()
