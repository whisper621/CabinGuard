import asyncio

import httpx
from cabinguard.media import MEDIA_SOURCE, MediaProvider, MediaToolExecutor
from cabinguard.models import VehicleState
from cabinguard.tools import ToolContext, execute_tool


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["media"] == "music"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "trackId": 101,
                        "trackName": "测试歌曲",
                        "artistName": "测试艺人",
                        "collectionName": "测试专辑",
                        "artworkUrl100": "https://example.com/100x100.jpg",
                        "previewUrl": "https://example.com/preview.m4a",
                        "trackTimeMillis": 201000,
                    },
                    {"trackId": 102, "trackName": "没有试听地址"},
                ]
            },
        )

    return httpx.MockTransport(handler)


def test_media_search_loads_real_preview_metadata() -> None:
    executor = MediaToolExecutor(MediaProvider(transport=_transport()))
    result = asyncio.run(
        executor.execute(
            "play_media",
            {"query": "轻音乐", "limit": 6},
            VehicleState(),
            ToolContext(),
        )
    )
    assert result.status == "success"
    assert result.vehicle.media.playing is True
    assert result.vehicle.media.current is not None
    assert result.vehicle.media.current.title == "测试歌曲"
    assert result.vehicle.media.current.preview_url.endswith("preview.m4a")
    assert result.output["provider"] == MEDIA_SOURCE
    assert result.output["preview_only"] is True

    requests: list[str] = []

    def fallback_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.host)
        if request.url.host == "itunes.apple.com":
            return httpx.Response(200, json={"resultCount": 0, "results": []})
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": 202,
                        "title": "真实试听",
                        "artist": {"name": "测试艺人"},
                        "album": {
                            "title": "测试专辑",
                            "cover_big": "https://example.com/cover.jpg",
                        },
                        "preview": "https://example.com/deezer-preview.mp3",
                        "duration": 180,
                    }
                ]
            },
        )

    fallback = MediaProvider(transport=httpx.MockTransport(fallback_handler))
    tracks = asyncio.run(fallback.search("轻音乐", 6))
    assert requests == ["itunes.apple.com", "api.deezer.com"]
    assert tracks[0].title == "真实试听"
    assert tracks[0].preview_url.endswith("deezer-preview.mp3")


def test_media_controls_are_deterministic() -> None:
    state = VehicleState()
    result = execute_tool("control_media", {"action": "set_volume", "value": 62}, state)
    assert result.status == "success"
    assert result.vehicle.media.volume == 62

    invalid = execute_tool("control_media", {"action": "set_volume"}, state)
    assert invalid.status == "blocked"
