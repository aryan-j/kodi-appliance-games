import json
import os
import re
import time
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import xbmcaddon
import xbmcvfs


ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
TOKEN_PATH = os.path.join(PROFILE, "igdb-token.json")
STEAM_ASSET_BASE = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps"


def _json_request(url, data=None, headers=None):
    request = Request(
        url,
        data=data.encode("utf-8") if isinstance(data, str) else data,
        headers=headers or {},
        method="POST" if data is not None else "GET",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _credentials():
    client_id = ADDON.getSettingString("igdb_client_id").strip()
    client_secret = ADDON.getSettingString("igdb_client_secret").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Configure the IGDB client ID and secret in Games settings")
    return client_id, client_secret


def _token():
    client_id, client_secret = _credentials()
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as stream:
            cached = json.load(stream)
        if cached.get("client_id") == client_id and cached.get("expires_at", 0) > time.time() + 60:
            return client_id, cached["access_token"]
    except (OSError, ValueError, KeyError):
        pass
    query = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    })
    payload = _json_request(f"https://id.twitch.tv/oauth2/token?{query}", data=b"")
    os.makedirs(PROFILE, exist_ok=True)
    payload["client_id"] = client_id
    payload["expires_at"] = time.time() + int(payload.get("expires_in", 0))
    with open(TOKEN_PATH, "w", encoding="utf-8") as stream:
        json.dump(payload, stream)
    return client_id, payload["access_token"]


FIELDS = (
    "id,name,summary,storyline,first_release_date,rating,rating_count,updated_at,"
    "cover.image_id,artworks.image_id,screenshots.image_id,genres.name,platforms.name,"
    "franchise.name,franchises.name,game_engines.name,game_modes.name,"
    "player_perspectives.name,themes.name,"
    "videos.name,videos.video_id,"
    "involved_companies.developer,involved_companies.publisher,"
    "involved_companies.company.name"
)


def _query(body, endpoint="games"):
    client_id, token = _token()
    return _json_request(
        f"https://api.igdb.com/v4/{endpoint}",
        data=body,
        headers={
            "Accept": "application/json",
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}",
        },
    )


def search(name, limit=10):
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return _query(
        f'search "{escaped}"; fields {FIELDS}; '
        f"where version_parent = null; limit {int(limit)};"
    )


def get(igdb_id):
    results = _query(f"fields {FIELDS}; where id = {int(igdb_id)}; limit 1;")
    return results[0] if results else None


def get_time_to_beat(igdb_id):
    results = _query(
        "fields game_id,hastily,normally,completely,count,updated_at; "
        f"where game_id = {int(igdb_id)}; limit 1;",
        endpoint="game_time_to_beats",
    )
    return results[0] if results else {}


def image_url(image_id, size):
    if not image_id:
        return ""
    return f"https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"


def _names(items):
    seen = set()
    values = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            values.append(name)
    return " / ".join(values)


def normalize(result, time_to_beat=None):
    companies = result.get("involved_companies") or []
    developers = [
        entry.get("company", {}).get("name", "")
        for entry in companies if entry.get("developer")
    ]
    publishers = [
        entry.get("company", {}).get("name", "")
        for entry in companies if entry.get("publisher")
    ]
    release_timestamp = result.get("first_release_date")
    release_date = time.strftime("%Y-%m-%d", time.gmtime(release_timestamp)) if release_timestamp else ""
    franchises = list(result.get("franchises") or [])
    if result.get("franchise"):
        franchises.insert(0, result["franchise"])
    time_to_beat = time_to_beat or {}
    artworks = result.get("artworks") or []
    screenshots = result.get("screenshots") or []
    trailer_candidates = []
    for video in result.get("videos") or []:
        video_id = video.get("video_id") or ""
        if not video_id:
            continue
        name = (video.get("name") or "").lower()
        if "official trailer" in name:
            priority = 3
        elif "trailer" in name:
            priority = 2
        elif "teaser" in name:
            priority = 1
        else:
            priority = 0
        trailer_candidates.append((priority, video_id))
    trailer_candidates.sort(reverse=True)
    trailer_id = trailer_candidates[0][1] if trailer_candidates else ""
    return {
        "igdb_id": str(result["id"]),
        "name": result.get("name") or "Unknown game",
        "description": result.get("summary") or "",
        "igdb_summary": result.get("summary") or "",
        "storyline": result.get("storyline") or "",
        "release_date": release_date,
        "year": int(release_date[:4]) if release_date else None,
        "community_score": result.get("rating"),
        "community_score_count": int(result.get("rating_count") or 0),
        "genres": _names(result.get("genres")),
        "platforms": _names(result.get("platforms")),
        "franchise": _names(franchises),
        "engines": _names(result.get("game_engines")),
        "game_modes": _names(result.get("game_modes")),
        "player_perspectives": _names(result.get("player_perspectives")),
        "themes": _names(result.get("themes")),
        "developer": " / ".join(filter(None, developers)),
        "publisher": " / ".join(filter(None, publishers)),
        "time_to_beat_hastily": int(time_to_beat.get("hastily") or 0),
        "time_to_beat_normally": int(time_to_beat.get("normally") or 0),
        "time_to_beat_completely": int(time_to_beat.get("completely") or 0),
        "time_to_beat_count": int(time_to_beat.get("count") or 0),
        "igdb_updated_at": int(result.get("updated_at") or 0),
        "cover_url": image_url((result.get("cover") or {}).get("image_id"), "cover_big"),
        "background_url": image_url(
            (artworks[0] if artworks else {}).get("image_id"),
            "1080p",
        ),
        "landscape_url": image_url(
            (screenshots[0] if screenshots else {}).get("image_id"),
            "1080p",
        ),
        "trailer": (
            f"plugin://plugin.video.youtube/play/?video_id={trailer_id}"
            if trailer_id else ""
        ),
    }


def download(url, destination):
    if not url:
        return ""
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    request = Request(url, headers={"User-Agent": "Kodi-Appliance-Games/0.1"})
    with urlopen(request, timeout=30) as response, open(destination, "wb") as stream:
        stream.write(response.read())
    return destination


def _sgdb_key():
    return ADDON.getSettingString("steamgriddb_api_key").strip()


def _sgdb_request(path):
    key = _sgdb_key()
    if not key:
        raise RuntimeError("Configure the SteamGridDB API key in Games settings")
    payload = _json_request(
        f"https://www.steamgriddb.com/api/v2{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "Kodi-Appliance-Games/0.1",
        },
    )
    if not payload.get("success"):
        raise RuntimeError(", ".join(payload.get("errors") or ["SteamGridDB request failed"]))
    return payload.get("data") or []


def _normalized_title(value):
    return "".join(character.lower() for character in value if character.isalnum())


def steamgriddb_game(name):
    results = _sgdb_request(f"/search/autocomplete/{quote(name)}")
    wanted = _normalized_title(name)
    # SGDB is still the resolver for community artwork.  Prefer its verified
    # Steam entry when one is available so the optional Steam originals are
    # tied to a trustworthy app id, but retain the existing community fallback
    # for non-Steam or unverified games.
    verified_steam = [result for result in results if _is_verified_steam_game(result)]
    for result in verified_steam:
        if _normalized_title(result.get("name", "")) == wanted:
            return result
    for result in results:
        if _normalized_title(result.get("name", "")) == wanted:
            return result
    return verified_steam[0] if verified_steam else (results[0] if results else None)


def _is_verified_steam_game(game):
    if not isinstance(game, dict) or not game.get("verified"):
        return False
    types = game.get("types") or ()
    if isinstance(types, str):
        types = (types,)
    return "steam" in {str(value).casefold() for value in types}


def _sgdb_game_details(game_id):
    try:
        details = _sgdb_request(f"/games/id/{int(game_id)}?platformdata=steam")
    except Exception:
        return {}
    if isinstance(details, list):
        details = details[0] if details and isinstance(details[0], dict) else {}
    if isinstance(details, dict) and isinstance(details.get("data"), dict):
        details = details["data"]
    return details if isinstance(details, dict) else {}


def _steam_record(details):
    if not _is_verified_steam_game(details):
        return {}
    external = (
        details.get("external_platform_data")
        or details.get("platform_data")
        or details.get("platformdata")
        or {}
    )
    records = external.get("steam") if isinstance(external, dict) else external
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, (list, tuple)):
        records = []
    for record in records:
        if isinstance(record, dict) and str(
            record.get("platform") or record.get("platform_name") or "steam"
        ).casefold() == "steam":
            return record
    return {}


def _steam_section_paths(metadata, section_names):
    """Return (explicit image2x paths, standard paths) for an asset section."""
    explicit, standard = [], []
    seen = set()
    if not isinstance(metadata, dict):
        return explicit, standard

    def add(path, target):
        if not isinstance(path, str):
            return
        path = path.strip()
        # Platform data sometimes includes bare locale markers such as
        # ``header_image: en``. They are not downloadable asset paths.
        parsed_path = urlparse(path).path
        if not path or (not os.path.splitext(parsed_path)[1] and "/" not in parsed_path):
            return
        if path not in seen:
            seen.add(path)
            target.append(path)

    def collect(value, target, language=False):
        if isinstance(value, str):
            add(value, target)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                collect(item, target, language=language)
            return
        if not isinstance(value, dict):
            return
        locale_keys = [
            (str(key).casefold().replace("-", "_"), item)
            for key, item in value.items()
            if re.match(r"^[a-z]{2}(?:_[a-z]{2})?$", str(key).casefold().replace("-", "_"))
        ]
        english_locales = [
            (key, item) for key, item in locale_keys
            if key in {"en", "en_us", "en_gb"}
        ]
        if english_locales:
            for _key, item in english_locales:
                collect(item, target, language=True)
            return
        for key, item in value.items():
            normalized = str(key).casefold().replace("-", "_")
            is_high = (
                "image2x" in normalized
                or "image_2x" in normalized
                or normalized in {"2x", "full2x", "full_2x", "high_res", "highres"}
                or ("2x" in normalized and ("en" in normalized or "english" in normalized))
            )
            is_english = normalized in {"en", "en_us", "english", "eng"} or normalized.startswith("en_")
            if is_high:
                collect(item, explicit, language=is_english or language)
            elif is_english or normalized in {
                "image", "full", "path", "url", "standard", "original", "asset"
            }:
                collect(item, target, language=is_english or language)
            elif isinstance(item, (dict, list, tuple)):
                # Preserve nested platform-data wrappers without treating
                # their labels as paths.
                collect(item, target, language=language)

    for section in section_names:
        value = metadata.get(section)
        if value in (None, ""):
            continue
        collect(value, standard)
    return explicit, standard


def _steam_2x_sibling(path):
    root, extension = os.path.splitext(path)
    if not extension or root.casefold().endswith("_2x"):
        return path
    return f"{root}_2x{extension}"


def _steam_asset_url(app_id, path):
    """Build a Steam CDN URL while retaining nested/hash asset paths."""
    if not isinstance(path, str) or not path.strip():
        return ""
    path = path.strip()
    parsed = urlparse(path)
    if parsed.scheme in {"http", "https"}:
        marker = "/store_item_assets/steam/apps/"
        if marker not in parsed.path:
            return path
        path = parsed.path.split(marker, 1)[1]
    path = path.lstrip("/")
    marker = "store_item_assets/steam/apps/"
    if path.startswith(marker):
        path = path[len(marker):]
    if path.startswith(f"{int(app_id)}/"):
        path = path[len(str(int(app_id))) + 1:]
    if not path:
        return ""
    return f"{STEAM_ASSET_BASE}/{int(app_id)}/{quote(path, safe='/._-')}"


def _steam_asset_candidates(details):
    """Return ordered Steam-original candidates, or {} for an unsafe match."""
    record = _steam_record(details)
    if not record:
        return {}
    app_id = record.get("id") or record.get("appid") or record.get("app_id") or record.get("steam_appid")
    try:
        app_id = int(str(app_id).strip())
    except (TypeError, ValueError):
        return {}
    metadata = (
        record.get("metadata")
        or record.get("assets")
        or record.get("images")
        or record.get("artwork")
        or record.get("data")
        or record
    )
    sections = {
        "cover": ("library_capsule", "library_capsule_full"),
        "background": ("library_hero", "library_hero_full"),
        "logo": ("library_logo", "library_logo_full", "logo"),
        "landscape": ("header", "header_image", "header_image_full"),
    }
    candidates = {}
    for role, section_names in sections.items():
        explicit, standard = _steam_section_paths(metadata, section_names)
        ordered = []
        for path in explicit:
            url = _steam_asset_url(app_id, path)
            if url and url not in ordered:
                ordered.append(url)
        for path in standard:
            for candidate in (_steam_2x_sibling(path), path):
                url = _steam_asset_url(app_id, candidate)
                if url and url not in ordered:
                    ordered.append(url)
        if ordered:
            candidates[role] = ordered
    return candidates


def _best_image(
    images,
    orientation="any",
    target_ratio=None,
    excluded_urls=(),
    max_ratio_distance=None,
    language="en",
    styles=(),
):
    candidates = []
    excluded_urls = set(excluded_urls)
    images = list(images or [])
    if language:
        localized = [
            item for item in images
            if str(item.get("language") or "").casefold() == language.casefold()
        ]
        if localized:
            images = localized
        else:
            untagged = [item for item in images if not item.get("language")]
            if untagged:
                images = untagged
    if styles:
        approved = []
        for item in images:
            value = item.get("style") or item.get("styles") or ()
            if isinstance(value, str):
                value = (value,)
            if {str(style).casefold() for style in value} & {style.casefold() for style in styles}:
                approved.append(item)
        if approved:
            images = approved
    for item in images:
        width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        image_url = item.get("url") or ""
        if image_url in excluded_urls:
            continue
        if orientation == "portrait" and width and height and width >= height:
            continue
        if orientation == "landscape" and width and height and width <= height:
            continue
        if target_ratio and (not width or not height):
            continue
        score = int(item.get("upvotes") or 0) - int(item.get("downvotes") or 0)
        ratio_distance = abs((width / height) - target_ratio) if target_ratio else 0
        if max_ratio_distance is not None and ratio_distance > max_ratio_distance:
            continue
        candidates.append((ratio_distance, score, width * height, item))
    candidates.sort(key=lambda value: (value[0], -value[1], -value[2]))
    return candidates[0][3] if candidates else None


def steamgriddb_art(name, game_id=""):
    game = {"id": int(game_id), "name": name} if str(game_id).isdigit() else steamgriddb_game(name)
    if not game:
        return {}
    game_id = int(game["id"])
    details = _sgdb_game_details(game_id)
    common = "?types=static&nsfw=false&humor=false"
    portrait_grids = _sgdb_request(
        f"/grids/game/{game_id}?dimensions=600x900,342x482,660x930&types=static&nsfw=false&humor=false"
    )
    # SteamGridDB accepts one dimensions value per request.  Passing a comma
    # separated list returns HTTP 400, which previously caused this role to be
    # silently skipped and left the old hero copied into ``landscape``.
    landscape_grids = []
    landscape_target_ratio = 460 / 215
    for dimensions, target_ratio in (("460x215", 460 / 215), ("460x259", 16 / 9)):
        try:
            landscape_grids = _sgdb_request(
                f"/grids/game/{game_id}?dimensions={dimensions}&types=static&nsfw=false&humor=false"
            )
        except Exception:
            landscape_grids = []
        if landscape_grids:
            landscape_target_ratio = target_ratio
            break
    if not landscape_grids:
        # Older or sparse games may not have either preferred size.  An
        # unfiltered static-grid request still lets us select a usable image
        # without reusing the hero/background role.
        try:
            landscape_grids = _sgdb_request(
                f"/grids/game/{game_id}?types=static&nsfw=false&humor=false"
            )
            landscape_target_ratio = 16 / 9
        except Exception:
            # A rejected/temporarily unavailable landscape request must not
            # make the existing cover, hero, or logo refresh fail.
            landscape_grids = []
    heroes = _sgdb_request(f"/heroes/game/{game_id}{common}")
    logos = _sgdb_request(f"/logos/game/{game_id}{common}")
    selected = {
        "cover": _best_image(portrait_grids, orientation="portrait"),
        "background": _best_image(heroes),
        "logo": _best_image(logos, styles={"official"}),
    }
    background_url = (selected["background"] or {}).get("url", "")
    # Prefer a separate near-16:9 grid for the widget landscape role. If the
    # service has no such asset, leave the role empty so the caller preserves
    # the existing landscape artwork instead of reusing the hero.
    selected["landscape"] = _best_image(
        landscape_grids,
        orientation="landscape",
        target_ratio=landscape_target_ratio,
        excluded_urls={background_url},
        max_ratio_distance=0.18,
    )
    community = {
        "game_id": str(game_id),
        "game_name": game.get("name") or name,
        **{key: (value or {}).get("url", "") for key, value in selected.items()},
    }
    # SGDB remains the source of truth for resolving the game and for all
    # community fallbacks.  Steam originals are opt-in only for a verified
    # Steam match with usable platform data; each role retains its SGDB URL as
    # the final candidate.
    for role, candidates in _steam_asset_candidates(details).items():
        community_url = community.get(role) or ""
        if community_url and community_url not in candidates:
            candidates = [*candidates, community_url]
        community[f"{role}_candidates"] = candidates
        community[role] = candidates[0]
    return community


def extension_from_url(url, fallback=".png"):
    extension = os.path.splitext(urlparse(url).path)[1].lower()
    return extension if extension in {".png", ".jpg", ".jpeg", ".webp"} else fallback
