"""Real media discovery with an honest preview-only playback boundary."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from pydantic import ValidationError

from .models import MediaState, MediaTrack, ToolExecution, VehicleState
from .tools import PlayMediaInput, ToolContext

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"
MEDIA_SOURCE = "Apple iTunes Search API / Deezer API"


class MediaProviderError(RuntimeError):
    pass


def _blocked(vehicle: VehicleState, reason: str, **extra: object) -> ToolExecution:
    return ToolExecution(
        vehicle=vehicle,
        status="blocked",
        output={"executed": False, "blocked": True, "reason": reason, **extra},
    )


def _as_itunes_track(item: object) -> MediaTrack | None:
    if not isinstance(item, dict) or not item.get("previewUrl") or not item.get("trackId"):
        return None
    duration_ms = item.get("trackTimeMillis")
    duration = round(float(duration_ms) / 1000) if isinstance(duration_ms, (int, float)) else 0
    return MediaTrack(
        id=str(item["trackId"]),
        title=str(item.get("trackName") or "未知曲目"),
        artist=str(item.get("artistName") or "未知艺人"),
        album=str(item.get("collectionName") or ""),
        artworkUrl=str(item.get("artworkUrl100") or "").replace("100x100", "300x300"),
        previewUrl=str(item["previewUrl"]),
        durationSeconds=duration,
    )


def _as_deezer_track(item: object) -> MediaTrack | None:
    if not isinstance(item, dict) or not item.get("preview") or not item.get("id"):
        return None
    artist = item.get("artist")
    album = item.get("album")
    return MediaTrack(
        id=str(item["id"]),
        title=str(item.get("title") or "未知曲目"),
        artist=str(artist.get("name") if isinstance(artist, dict) else "未知艺人"),
        album=str(album.get("title") if isinstance(album, dict) else ""),
        artworkUrl=str(album.get("cover_big") if isinstance(album, dict) else ""),
        previewUrl=str(item["preview"]),
        durationSeconds=int(item.get("duration") or 0),
    )


class MediaProvider:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        fallback_endpoint: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint or os.getenv("CABINGUARD_MEDIA_URL", ITUNES_SEARCH_URL)
        self.fallback_endpoint = fallback_endpoint or os.getenv(
            "CABINGUARD_MEDIA_FALLBACK_URL", DEEZER_SEARCH_URL
        )
        self.transport = transport
        self._search_cache: dict[str, tuple[float, list[MediaTrack]]] = {}

    async def search(self, query: str, limit: int) -> list[MediaTrack]:
        cache_key = " ".join(query.lower().split())
        cached = self._search_cache.get(cache_key)
        if cached and cached[0] > time.time():
            return cached[1][:limit]
        errors: list[str] = []
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            transport=self.transport,
            trust_env=True,
        ) as client:
            try:
                response = await client.get(
                    self.endpoint,
                    params={
                        "term": query,
                        "media": "music",
                        "entity": "song",
                        "country": "CN",
                        "limit": str(limit),
                    },
                    headers={"User-Agent": "CabinGuard/0.8 (+https://github.com/whisper621/CabinGuard)"},
                )
                response.raise_for_status()
                payload: Any = response.json()
                results = payload.get("results") if isinstance(payload, dict) else None
                tracks = [
                    track
                    for item in (results or [])
                    if (track := _as_itunes_track(item)) is not None
                ]
                if tracks:
                    self._search_cache[cache_key] = (time.time() + 24 * 60 * 60, tracks)
                    return tracks
            except (httpx.HTTPError, ValueError) as error:
                errors.append(f"Apple: {error}")

            try:
                response = await client.get(
                    self.fallback_endpoint,
                    params={"q": query, "limit": str(limit)},
                    headers={"User-Agent": "CabinGuard/0.8 (+https://github.com/whisper621/CabinGuard)"},
                )
                response.raise_for_status()
                payload = response.json()
                results = payload.get("data") if isinstance(payload, dict) else None
                tracks = [
                    track
                    for item in (results or [])
                    if (track := _as_deezer_track(item)) is not None
                ]
                if tracks:
                    self._search_cache[cache_key] = (time.time() + 24 * 60 * 60, tracks)
                return tracks
            except (httpx.HTTPError, ValueError) as error:
                errors.append(f"Deezer: {error}")

        if errors:
            raise MediaProviderError("音乐目录暂时不可用：" + "；".join(errors))
        return []


class MediaToolExecutor:
    def __init__(self, provider: MediaProvider | None = None) -> None:
        self.provider = provider or MediaProvider()

    async def execute(
        self,
        name: str,
        raw_input: dict[str, object],
        vehicle: VehicleState,
        _context: ToolContext,
    ) -> ToolExecution:
        if name != "play_media":
            return _blocked(vehicle, f"未知媒体工具：{name}", code="unknown_media_tool")
        try:
            parsed = PlayMediaInput.model_validate(raw_input)
        except ValidationError as error:
            return _blocked(
                vehicle,
                "媒体工具参数无效",
                code="invalid_tool_arguments",
                issues=error.errors(include_url=False),
            )
        try:
            queue = await self.provider.search(parsed.query.strip(), parsed.limit)
        except MediaProviderError as error:
            return _blocked(vehicle, str(error), code="media_provider_unavailable")
        if not queue:
            return _blocked(
                vehicle,
                f"没有找到“{parsed.query}”的可播放试听内容",
                code="media_not_found",
            )
        media = MediaState(
            source="music",
            playing=True,
            volume=vehicle.media.volume,
            currentIndex=0,
            current=queue[0],
            queue=queue,
        )
        next_vehicle = vehicle.model_copy(update={"media": media})
        return ToolExecution(
            vehicle=next_vehicle,
            status="success",
            output={
                "executed": True,
                "playing": True,
                "query": parsed.query,
                "current": queue[0].model_dump(by_alias=True),
                "queue_size": len(queue),
                "provider": MEDIA_SOURCE,
                "preview_only": True,
                "copyright_notice": "音乐由目录服务提供 30 秒试听，未声称具备整曲版权。",
            },
        )
