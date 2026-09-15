import asyncio

import httpx
from cabinguard.charging import ChargingToolExecutor
from cabinguard.models import VehicleState
from cabinguard.tools import ToolContext


def test_live_charging_poi_adapter_labels_public_source_and_unknown_availability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "overpass-api.de"
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 123,
                        "lat": 40.045,
                        "lon": 116.49,
                        "tags": {"name": "测试公共充电站"},
                    }
                ]
            },
        )

    vehicle = VehicleState(externalRoutingConsent=True)
    result = asyncio.run(
        ChargingToolExecutor(httpx.MockTransport(handler)).execute(
            {"along_route": True, "max_detour_km": 20},
            vehicle,
            ToolContext(prior_successful_tools=("get_vehicle_state",)),
        )
    )

    assert result.status == "success"
    assert result.output["liveProviderUsed"] is True
    assert result.output["stations"][0]["available_fast_chargers"] is None
    assert result.output["stations"][0]["data_source"] == "OpenStreetMap Overpass POI"


def test_charging_adapter_explicitly_labels_demo_fallback_without_consent() -> None:
    result = asyncio.run(
        ChargingToolExecutor().execute(
            {"along_route": True, "max_detour_km": 20},
            VehicleState(),
            ToolContext(prior_successful_tools=("get_vehicle_state",)),
        )
    )

    assert result.status == "success"
    assert result.output["provider"] == "CabinGuard demo catalog"
    assert result.output["liveProviderUsed"] is False
