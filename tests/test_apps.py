import os
import sys
import tempfile
import types
import unittest
from unittest import mock


class _Addon:
    def getAddonInfo(self, key):
        if key == "profile":
            return tempfile.gettempdir()
        return os.path.dirname(os.path.dirname(__file__))

    def getSettingString(self, _key):
        return ""

    def getSettingBool(self, _key):
        return False


class _Item:
    def __init__(self, label="", path=""):
        self.label = label
        self.path = path
        self.art = {}
        self.properties = {}

    def setArt(self, art):
        self.art = art

    def setProperty(self, key, value):
        self.properties[key] = value


class _Dialog:
    def notification(self, *_args):
        return None


sys.modules.setdefault("xbmcaddon", types.SimpleNamespace(Addon=_Addon))
sys.modules.setdefault("xbmcvfs", types.SimpleNamespace(translatePath=lambda value: value))
sys.modules.setdefault(
    "xbmc",
    types.SimpleNamespace(
        LOGERROR=4,
        LOGWARNING=3,
        LOGINFO=1,
        getCondVisibility=lambda _value: False,
        executebuiltin=lambda _value: None,
        log=lambda *_args: None,
    ),
)
sys.modules.setdefault(
    "xbmcgui",
    types.SimpleNamespace(
        ListItem=_Item,
        Dialog=_Dialog,
        NOTIFICATION_ERROR=2,
    ),
)
sys.modules.setdefault(
    "xbmcplugin",
    types.SimpleNamespace(
        addDirectoryItem=lambda *_args: None,
        setContent=lambda *_args: None,
        endOfDirectory=lambda *_args, **_kwargs: None,
    ),
)
if len(sys.argv) < 2 or not str(sys.argv[1]).isdigit():
    sys.argv.insert(1, "1")

from resources.lib import apps, router


class ApplicationDefinitionTests(unittest.TestCase):
    def setUp(self):
        apps._registered_app_available.cache_clear()

    def test_catalog_is_static_and_has_distinct_artwork(self):
        self.assertEqual([application.key for application in apps.all_applications()], ["hydra", "chatgpt"])
        self.assertEqual(apps.get_application("hydra").app_id, apps.HYDRA_APP_ID)
        self.assertEqual(apps.get_application("chatgpt").app_id, apps.CHATGPT_APP_ID)
        self.assertEqual(apps.CHATGPT_APP_ID, "OpenAI.Codex_2p2nqsd0c76g0!App")
        self.assertNotEqual(
            apps.get_application("hydra").artwork,
            apps.get_application("chatgpt").artwork,
        )

    def test_registered_app_command_is_preferred(self):
        hydra = apps.get_application("hydra")
        chatgpt = apps.get_application("chatgpt")
        with mock.patch.object(apps, "_fallback_available", return_value=True):
            self.assertEqual(
                apps.command_for(hydra, registered_available=True),
                ["explorer.exe", "shell:AppsFolder\\gg.hydralauncher.hydra"],
            )
            self.assertEqual(
                apps.command_for(chatgpt, registered_available=True),
                ["explorer.exe", "shell:AppsFolder\\OpenAI.Codex_2p2nqsd0c76g0!App"],
            )

    def test_hydra_fallback_is_runtime_only_and_missing_target_is_none(self):
        hydra = apps.get_application("hydra")
        with mock.patch.object(apps, "_registered_app_available", return_value=False):
            with mock.patch.object(apps.os.path, "isfile", return_value=True):
                self.assertEqual(apps.command_for(hydra), [apps.HYDRA_EXECUTABLE])
            with mock.patch.object(apps.os.path, "isfile", return_value=False):
                self.assertIsNone(apps.command_for(hydra))

    def test_launch_uses_popen_without_shell(self):
        chatgpt = apps.get_application("chatgpt")
        process = object()
        popen = mock.Mock(return_value=process)
        with mock.patch.object(apps, "command_for", return_value=["explorer.exe", "shell:AppsFolder\\id"]):
            self.assertIs(apps.launch(chatgpt, popen=popen), process)
        self.assertEqual(popen.call_args.args[0], ["explorer.exe", "shell:AppsFolder\\id"])
        self.assertEqual(popen.call_args.kwargs["cwd"], None)
        self.assertNotIn("shell", popen.call_args.kwargs)


class ApplicationRouteTests(unittest.TestCase):
    def test_root_exposes_applications_folder(self):
        with mock.patch.object(router, "add_folder") as add_folder:
            router.root()
        labels = [call.args[0] for call in add_folder.call_args_list]
        self.assertIn("Applications", labels)

    def test_apps_route_adds_non_folder_items_with_distinct_art(self):
        added = []

        def add_item(_handle, target, item, is_folder):
            added.append((target, item, is_folder))

        with mock.patch.object(router.xbmcplugin, "addDirectoryItem", side_effect=add_item):
            with mock.patch.object(router.apps, "is_available", return_value=True):
                router.applications()
        self.assertEqual([item.label for _target, item, _folder in added], ["Hydra", "ChatGPT"])
        self.assertEqual([is_folder for _target, _item, is_folder in added], [False, False])
        self.assertNotEqual(added[0][1].art["icon"], added[1][1].art["icon"])
        self.assertTrue(all(item.properties["IsPlayable"] == "true" for _target, item, _folder in added))

    def test_apps_run_does_not_open_games_database(self):
        with mock.patch.object(router.database, "connect") as connect:
            with mock.patch.object(router.apps, "is_available", return_value=False):
                with mock.patch.object(router, "applications"):
                    previous_argv = sys.argv[:]
                    try:
                        sys.argv[:] = ["addon.py", "1", "?action=apps"]
                        router.run()
                    finally:
                        sys.argv[:] = previous_argv
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
