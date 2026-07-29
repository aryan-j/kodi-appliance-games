import os
import shutil
import sys
from urllib.parse import parse_qs, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from . import database, metadata


HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def url(action, **kwargs):
    return f"{BASE_URL}?{urlencode({'action': action, **kwargs})}"


def add_folder(label, target, art=None, dbtype=None):
    item = xbmcgui.ListItem(label=label)
    item.setArt(art or {})
    if dbtype:
        item.setProperty("DBType", dbtype)
    if dbtype == "genre":
        item.setProperty("appliance.genre", "true")
    xbmcplugin.addDirectoryItem(HANDLE, target, item, True)


def game_item(game, origin="list"):
    # Arctic Fuse may serve an older generated widget path that predates the
    # explicit origin parameter. Detect the actual Games hub while its widget
    # directory is being populated so hub cards always return to window 1102.
    if origin == "list" and xbmc.getCondVisibility("Window.IsActive(1102)"):
        origin = "hub"
    item = build_game_listitem(game)
    target = url("details", game_id=game["id"], origin=origin)
    # Treat the details route as an action rather than a folder. Kodi otherwise
    # replaces the hub with MyVideoNav while the modal info dialog is opening,
    # briefly exposing its Files / Playlists / Videos root.
    item.setProperty("IsPlayable", "true")
    favorite_action = "unfavorite" if game["favorite"] else "favorite"
    favorite_label = "Remove from Favorites" if game["favorite"] else "Add to Favorites"
    item.addContextMenuItems([
        (favorite_label, f"RunPlugin({url(favorite_action, game_id=game['id'])})"),
        ("Refresh Metadata", f"RunPlugin({url('refresh_metadata', game_id=game['id'])})"),
        ("Locate Executable", f"RunPlugin({url('locate', game_id=game['id'])})"),
    ])
    xbmcplugin.addDirectoryItem(HANDLE, target, item, False)


def build_game_listitem(game, path=""):
    item = xbmcgui.ListItem(label=game["name"], path=path)
    tag = item.getVideoInfoTag()
    # Leave DBType unset. Arctic Fuse overlays labels on generic "video"
    # poster items, while its movie and TV poster widgets remain artwork-only.
    # The VideoInfoTag still carries game details for dialogs and filtering.
    tag.setTitle(game["name"])
    tag.setSortTitle(game["sort_name"] or game["name"])
    tag.setPlot(game["description"] or "")
    if game["year"]:
        tag.setYear(int(game["year"]))
    genres = [value.strip() for value in (game["genres"] or "").split("/") if value.strip()]
    if genres:
        tag.setGenres(genres)
    studios = []
    for value in (game["developer"], game["publisher"]):
        value = (value or "").strip()
        if value and value.casefold() not in {studio.casefold() for studio in studios}:
            studios.append(value)
    if studios:
        tag.setStudios(studios)
    if game["community_score"]:
        # IGDB ratings use a 0-100 scale; Kodi and Arctic Fuse expect 0-10.
        tag.setRating(float(game["community_score"]) / 10.0, 0, "igdb", True)
    tag.setPlaycount(int(game["play_count"] or 0))
    tag.setDuration(int(game["playtime_seconds"] or 0))
    if game["created_at"]:
        tag.setDateAdded(game["created_at"])
    if game["last_played"]:
        tag.setLastPlayed(game["last_played"])
    if game["trailer"]:
        tag.setTrailer(game["trailer"])
    art = {
        "poster": game["cover"] or "",
        "thumb": game["icon"] or game["cover"] or "",
        "landscape": game["icon"] or game["background"] or game["cover"] or "",
        "fanart": game["background"] or "",
        "icon": game["icon"] or game["cover"] or "",
        "clearlogo": game["logo"] or "",
    }
    item.setArt({key: value for key, value in art.items() if value})
    item.setProperty("game.id", game["id"])
    item.setProperty("game.playtime", str(game["playtime_seconds"] or 0))
    item.setProperty("game.lastplayed", game["last_played"] or "")
    executable_available = bool(game["executable"] and os.path.isfile(os.path.expandvars(game["executable"])))
    item.setProperty("game.available", "true" if executable_available else "false")
    if not executable_available:
        item.setProperty("game.status", "Executable missing")
    return item


def root():
    add_folder("Recently Played", url("list", view="recent"))
    add_folder("Favorites", url("list", view="favorites"))
    add_folder("Recently Added", url("list", view="new"))
    add_folder("Genres", url("genres"))
    add_folder("All Games", url("list", view="all"))
    add_folder("Add Game", url("add_game"))
    add_folder("Metadata Settings", url("settings"))
    xbmcplugin.setContent(HANDLE, "games")
    xbmcplugin.endOfDirectory(HANDLE)


def listing(view, origin="list"):
    if view == "recent":
        games = database.list_games("installed = 1 AND hidden = 0 AND last_played IS NOT NULL", order="last_played DESC")
    elif view == "favorites":
        games = database.list_games("installed = 1 AND hidden = 0 AND favorite = 1")
    elif view == "new":
        games = database.list_games(order="created_at DESC")
    elif view == "featured":
        games = database.list_games(
            order="favorite DESC, play_count DESC, community_score DESC, name COLLATE NOCASE"
        )
    else:
        games = database.list_games()
    for game in games:
        game_item(game, origin=origin)
    xbmcplugin.setContent(HANDLE, "games")
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.endOfDirectory(HANDLE)


def genres():
    names = set()
    for game in database.list_games():
        names.update(part.strip() for part in (game["genres"] or "").split("/") if part.strip())
    for name in sorted(names):
        add_folder(name, url("genre", name=name), dbtype="genre")
    xbmcplugin.setContent(HANDLE, "genres")
    xbmcplugin.endOfDirectory(HANDLE)


def genre(name):
    for game in database.list_games("installed = 1 AND hidden = 0 AND genres LIKE ?", (f"%{name}%",)):
        game_item(game)
    xbmcplugin.setContent(HANDLE, "games")
    xbmcplugin.endOfDirectory(HANDLE)


def details(game_id, origin="list"):
    game = database.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification("Games", "Game not found", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    play_url = url("play", game_id=game_id)
    item = build_game_listitem(game, path=play_url)
    item.setProperty("IsPlayable", "true")
    xbmcgui.Dialog().info(item)
    # This is a non-folder plugin action, so complete it as an unsuccessful
    # playback resolution. The originating hub/list remains untouched.
    xbmcplugin.setResolvedUrl(HANDLE, False, item)


def play(game_id):
    game = database.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification("Games", "Game not found", xbmcgui.NOTIFICATION_ERROR)
        return
    executable = os.path.expandvars(game["executable"] or "")
    if not os.path.isfile(executable):
        xbmcgui.Dialog().notification(
            "Games",
            "Executable not found. Use Locate Executable from the context menu.",
            xbmcgui.NOTIFICATION_ERROR,
        )
        return
    database.queue_launch(game_id)
    xbmcgui.Dialog().notification("Games", f"Launching {game['name']}")


def walkthrough(game_id):
    game = database.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification("Games", "Game not found", xbmcgui.NOTIFICATION_ERROR)
        return
    query = f"{game['name']} full walkthrough no commentary"
    target = (
        "plugin://plugin.video.youtube/kodion/search/query/?"
        + urlencode({"q": query, "search_type": "notvalid"})
    )
    xbmc.log(f"[Kodi Appliance Games] Opening walkthrough search for {game['name']}", xbmc.LOGINFO)
    xbmc.executebuiltin(f"ActivateWindow(Videos,{target},return)")


def set_favorite(game_id, favorite):
    database.set_favorite(game_id, favorite)
    xbmcgui.Dialog().notification(
        "Games",
        "Added to Favorites" if favorite else "Removed from Favorites",
    )
    xbmc.executebuiltin("Container.Refresh")


def locate(game_id):
    game = database.get_game(game_id)
    if not game:
        return
    initial = game["install_directory"] or game["working_directory"] or ""
    selected = xbmcgui.Dialog().browseSingle(
        1,
        f"Locate {game['name']} executable",
        "files",
        ".exe",
        False,
        False,
        initial,
    )
    if selected and os.path.isfile(selected):
        database.update_executable(game_id, selected)
        xbmcgui.Dialog().notification("Games", "Executable updated")
        xbmc.executebuiltin("Container.Refresh")


def launch_self_test():
    executable = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    session_id = database.queue_launch_command(
        "__appliance_launch_test__",
        "Kodi Appliance Launch Test",
        executable,
        "/d /c exit 0",
    )
    xbmcgui.Dialog().notification("Games", f"Launch test queued ({session_id})")
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True)


def _choose_igdb(name):
    results = metadata.search(name)
    if not results:
        xbmcgui.Dialog().notification("Games", "No IGDB matches found")
        return None
    labels = []
    for result in results:
        normalized = metadata.normalize(result)
        suffix = f" ({normalized['year']})" if normalized["year"] else ""
        labels.append(f"{normalized['name']}{suffix}")
    selected = xbmcgui.Dialog().select("Choose the matching game", labels)
    return results[selected] if selected >= 0 else None


def _save_igdb(game_id, executable, result):
    values = metadata.normalize(result)
    media_folder = os.path.join(metadata.PROFILE, "media", game_id.replace(":", "_"))
    sgdb_art = {}
    if metadata._sgdb_key():
        try:
            sgdb_art = metadata.steamgriddb_art(values["name"])
            xbmc.log(
                "[Kodi Appliance Games] SteamGridDB artwork roles: "
                + ", ".join(
                    f"{role}={'yes' if sgdb_art.get(role) else 'no'}"
                    for role in ("cover", "background", "logo")
                ),
                xbmc.LOGINFO,
            )
        except Exception as exc:
            xbmc.log(
                f"[Kodi Appliance Games] SteamGridDB artwork fallback: {exc}",
                xbmc.LOGWARNING,
            )

    def fetch(role, primary_url, fallback_extension):
        source_url = sgdb_art.get(role) or primary_url
        if not source_url:
            return ""
        extension = metadata.extension_from_url(source_url, fallback_extension)
        return metadata.download(source_url, os.path.join(media_folder, f"{role}{extension}"))

    cover = fetch("cover", values["cover_url"], ".jpg")
    background = fetch("background", values["background_url"], ".jpg")
    logo = fetch("logo", "", ".png")
    # The appliance intentionally uses one identical image for fanart and
    # landscape cards. Keep this invariant during every metadata refresh.
    icon = ""
    if background:
        extension = os.path.splitext(background)[1].lower() or ".jpg"
        icon = os.path.join(media_folder, f"landscape{extension}")
        if os.path.normcase(background) != os.path.normcase(icon):
            shutil.copy2(background, icon)
    database.add_or_update_metadata(
        game_id,
        executable,
        values,
        cover,
        background,
        logo,
        icon,
    )
    return {
        "metadata": "IGDB",
        "artwork": "SteamGridDB" if sgdb_art else "IGDB",
        "steamgriddb_game": sgdb_art.get("game_name", ""),
    }


def add_game():
    executable = xbmcgui.Dialog().browseSingle(
        1,
        "Choose game executable",
        "files",
        ".exe",
        False,
        False,
        "",
    )
    if not executable or not os.path.isfile(executable):
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    default_name = os.path.splitext(os.path.basename(executable))[0]
    name = xbmcgui.Dialog().input("Game title", defaultt=default_name)
    if not name:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    try:
        result = _choose_igdb(name)
        if result:
            outcome = _save_igdb(f"igdb:{result['id']}", executable, result)
            xbmcgui.Dialog().notification(
                "Games",
                f"Game added · artwork: {outcome['artwork']}",
            )
    except Exception as exc:
        xbmcgui.Dialog().ok("Games metadata", str(exc))
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True)


def refresh_metadata(game_id):
    game = database.get_game(game_id)
    if not game:
        return
    try:
        result = None
        if game["source"] == "igdb" and str(game["source_id"] or "").isdigit():
            result = metadata.get(game["source_id"])
        if not result:
            result = _choose_igdb(game["name"])
        if result:
            outcome = _save_igdb(game_id, "", result)
            xbmcgui.Dialog().notification(
                "Games",
                f"Refreshed · artwork: {outcome['artwork']}",
            )
            xbmc.executebuiltin("Container.Refresh")
    except Exception as exc:
        xbmcgui.Dialog().ok("Games metadata", str(exc))


def test_metadata():
    try:
        results = metadata.search("Portal 2", limit=1)
        if results:
            xbmcgui.Dialog().notification("Games metadata", "IGDB connection successful")
            xbmc.log("[Kodi Appliance Games] IGDB connection test succeeded", xbmc.LOGINFO)
        else:
            raise RuntimeError("IGDB authenticated but returned no test result")
    except Exception as exc:
        xbmcgui.Dialog().ok("Games metadata test failed", str(exc))
        xbmc.log(f"[Kodi Appliance Games] IGDB connection test failed: {exc}", xbmc.LOGERROR)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True)


def test_steamgriddb():
    try:
        result = metadata.steamgriddb_art("Portal 2")
        if result.get("cover") and result.get("background"):
            xbmcgui.Dialog().notification("Games artwork", "SteamGridDB connection successful")
            xbmc.log(
                f"[Kodi Appliance Games] SteamGridDB test succeeded with game {result.get('game_id')}",
                xbmc.LOGINFO,
            )
        else:
            raise RuntimeError("SteamGridDB connected but did not return the required artwork")
    except Exception as exc:
        xbmcgui.Dialog().ok("SteamGridDB test failed", str(exc))
        xbmc.log(f"[Kodi Appliance Games] SteamGridDB test failed: {exc}", xbmc.LOGERROR)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True)


def configure_skin():
    settings = {
        "HomeSwitcher.1102.Toggle": "true",
        "HomeSwitcher.1102.Name": "Games",
        "HomeSwitcher.1102.Icon": "special://skin/extras/icons/gamepad.png",
        "HomeSwitcher.1102.Mode": "Standard",
        "HomeSwitcher.1102.Shortcut.Path": 'ActivateWindow(Videos,"plugin://plugin.program.appliance.games/",return)',
        "HomeSwitcher.1102.Spotlight.Label": "Featured Games",
        "HomeSwitcher.1102.Spotlight.Path": "plugin://plugin.program.appliance.games/?action=list&view=featured&origin=hub",
        "HomeSwitcher.1102.Spotlight.Target": "videos",
    }
    for key, value in settings.items():
        xbmc.executebuiltin(f"Skin.SetString({key},{value})")
    xbmc.executebuiltin("Skin.SetBool(Widgets.DisableNoResultsItem)")
    # Do not force a template rebuild here. Arctic Fuse watches its shortcut
    # nodes and performs a debounced rebuild itself. Forcing a rebuild during
    # skin startup can create a reload loop because each reload schedules the
    # same startup generator again.
    xbmcgui.Dialog().notification("Games", "Arctic Fuse Games hub configured")
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True)


def run():
    database.connect().close()
    params = parse_qs(sys.argv[2][1:] if len(sys.argv) > 2 else "")
    action = params.get("action", ["root"])[0]
    if action == "root":
        root()
    elif action == "list":
        listing(
            params.get("view", ["all"])[0],
            params.get("origin", ["list"])[0],
        )
    elif action == "genres":
        genres()
    elif action == "genre":
        genre(params.get("name", [""])[0])
    elif action == "details":
        details(
            params.get("game_id", [""])[0],
            params.get("origin", ["list"])[0],
        )
    elif action == "play":
        play(params.get("game_id", [""])[0])
    elif action == "walkthrough":
        walkthrough(params.get("game_id", [""])[0])
    elif action == "favorite":
        set_favorite(params.get("game_id", [""])[0], True)
    elif action == "unfavorite":
        set_favorite(params.get("game_id", [""])[0], False)
    elif action == "locate":
        locate(params.get("game_id", [""])[0])
    elif action == "selftest":
        launch_self_test()
    elif action == "add_game":
        add_game()
    elif action == "refresh_metadata":
        refresh_metadata(params.get("game_id", [""])[0])
    elif action == "settings":
        xbmc.executebuiltin("Addon.OpenSettings(plugin.program.appliance.games)")
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
    elif action == "test_metadata":
        test_metadata()
    elif action == "test_steamgriddb":
        test_steamgriddb()
    elif action == "configure":
        configure_skin()
