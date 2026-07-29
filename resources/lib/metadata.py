import json
import os
import time
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import xbmcaddon
import xbmcvfs


ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
TOKEN_PATH = os.path.join(PROFILE, "igdb-token.json")


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
    "id,name,summary,first_release_date,rating,"
    "cover.image_id,artworks.image_id,screenshots.image_id,genres.name,platforms.name,"
    "videos.name,videos.video_id,"
    "involved_companies.developer,involved_companies.publisher,"
    "involved_companies.company.name"
)


def _query(body):
    client_id, token = _token()
    return _json_request(
        "https://api.igdb.com/v4/games",
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


def image_url(image_id, size):
    if not image_id:
        return ""
    return f"https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"


def normalize(result):
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
        "release_date": release_date,
        "year": int(release_date[:4]) if release_date else None,
        "community_score": result.get("rating"),
        "genres": " / ".join(item.get("name", "") for item in result.get("genres") or [] if item.get("name")),
        "platforms": " / ".join(item.get("name", "") for item in result.get("platforms") or [] if item.get("name")),
        "developer": " / ".join(filter(None, developers)),
        "publisher": " / ".join(filter(None, publishers)),
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
    for result in results:
        if _normalized_title(result.get("name", "")) == wanted:
            return result
    return results[0] if results else None


def _best_image(images, orientation="any"):
    candidates = []
    for item in images:
        width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        if orientation == "portrait" and width >= height:
            continue
        if orientation == "landscape" and width <= height:
            continue
        score = int(item.get("upvotes") or 0) - int(item.get("downvotes") or 0)
        candidates.append((score, width * height, item))
    candidates.sort(key=lambda value: (value[0], value[1]), reverse=True)
    return candidates[0][2] if candidates else None


def steamgriddb_art(name):
    game = steamgriddb_game(name)
    if not game:
        return {}
    game_id = int(game["id"])
    common = "?types=static&nsfw=false&humor=false"
    portrait_grids = _sgdb_request(
        f"/grids/game/{game_id}?dimensions=600x900,342x482,660x930&types=static&nsfw=false&humor=false"
    )
    heroes = _sgdb_request(f"/heroes/game/{game_id}{common}")
    logos = _sgdb_request(f"/logos/game/{game_id}{common}")
    selected = {
        "cover": _best_image(portrait_grids, orientation="portrait"),
        "background": _best_image(heroes),
        "logo": _best_image(logos),
    }
    return {
        "game_id": str(game_id),
        "game_name": game.get("name") or name,
        **{key: (value or {}).get("url", "") for key, value in selected.items()},
    }


def extension_from_url(url, fallback=".png"):
    extension = os.path.splitext(urlparse(url).path)[1].lower()
    return extension if extension in {".png", ".jpg", ".jpeg", ".webp"} else fallback
