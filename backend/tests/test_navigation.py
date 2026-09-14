import asyncio
import json

import httpx
from cabinguard.navigation import NavigationProvider, NavigationToolExecutor
from cabinguard.session import SessionStore
from cabinguard.tools import ToolContext


def provider_transport(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/search"):
        assert request.url.params["q"] == "昌平区人民政府"
        return httpx.Response(
            200,
            json=[
                {
                    "osm_type": "relation",
                    "osm_id": 12345,
                    "lat": "40.2207",
                    "lon": "116.2312",
                    "name": "昌平区人民政府",
                    "display_name": "昌平区人民政府, 政府街, 昌平区, 北京市, 中国",
                    "type": "government",
                    "importance": 0.62,
                }
            ],
        )
    if "/route/v1/driving/" in request.url.path:
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [
                    {
                        "distance": 39120,
                        "duration": 2880,
                        "geometry": {
                            "coordinates": [
                                [116.4836, 40.0415],
                                [116.35, 40.12],
                                [116.2312, 40.2207],
                            ]
                        },
                        "legs": [
                            {
                                "steps": [
                                    {
                                        "distance": 900,
                                        "name": "京承高速",
                                        "maneuver": {"type": "depart", "modifier": "straight"},
                                    },
                                    {
                                        "distance": 38220,
                                        "name": "京藏高速",
                                        "maneuver": {"type": "turn", "modifier": "left"},
                                    },
                                ]
                            }
                        ],
                    },
                    {
                        "distance": 42100,
                        "duration": 3120,
                        "geometry": {"coordinates": []},
                        "legs": [],
                    },
                ],
            },
        )
    return httpx.Response(404)


def test_search_and_plan_live_route_without_exposing_coordinates_to_model() -> None:
    store = SessionStore()
    session = store.create_session()
    executor = NavigationToolExecutor(
        NavigationProvider(transport=httpx.MockTransport(provider_transport))
    )

    search = asyncio.run(
        executor.execute(
            "search_places",
            {"query": "昌平区政府", "limit": 3},
            session.vehicle,
            session,
            ToolContext(navigation_authorized=True),
        )
    )
    assert search.status == "success"
    candidate = search.output["candidates"][0]  # type: ignore[index]
    assert candidate["name"] == "昌平区人民政府"
    assert "latitude" not in candidate
    assert "longitude" not in candidate

    planned = asyncio.run(
        executor.execute(
            "plan_navigation",
            {"destination_id": candidate["id"], "route_preference": "fastest"},
            search.vehicle,
            session,
            ToolContext(
                navigation_authorized=True,
                prior_successful_tools=("get_vehicle_state", "search_places"),
            ),
        )
    )
    assert planned.status == "success"
    assert planned.vehicle.destination == "昌平区人民政府"
    assert planned.vehicle.route_provider == "OSRM · OpenStreetMap"
    assert planned.vehicle.route_distance_km == 39.1
    assert planned.vehicle.route_eta_minutes == 48
    assert len(planned.vehicle.route_polyline) == 3
    assert len(planned.vehicle.route_alternatives) == 2
    assert planned.vehicle.estimated_arrival_battery is not None
    assert "latitude" not in planned.output
    assert "longitude" not in planned.output
    assert "116.4836" not in json.dumps(planned.output, ensure_ascii=False)


def test_browser_location_requires_external_routing_consent() -> None:
    store = SessionStore()
    session = store.create_session(
        latitude=31.2304,
        longitude=121.4737,
        allow_external_routing=False,
    )
    executor = NavigationToolExecutor(
        NavigationProvider(transport=httpx.MockTransport(provider_transport))
    )
    search = asyncio.run(
        executor.execute(
            "search_places",
            {"query": "昌平区政府", "limit": 1},
            session.vehicle,
            session,
            ToolContext(navigation_authorized=True),
        )
    )
    candidate = search.output["candidates"][0]  # type: ignore[index]
    result = asyncio.run(
        executor.execute(
            "plan_navigation",
            {"destination_id": candidate["id"], "route_preference": "fastest"},
            session.vehicle,
            session,
            ToolContext(
                navigation_authorized=True,
                prior_successful_tools=("get_vehicle_state", "search_places"),
            ),
        )
    )
    assert result.status == "blocked"
    assert result.output["code"] == "external_routing_consent_required"
    assert result.vehicle.route_polyline == []


def test_provider_failure_is_blocked_instead_of_fabricating_route() -> None:
    def failing_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    store = SessionStore()
    session = store.create_session()
    executor = NavigationToolExecutor(
        NavigationProvider(transport=httpx.MockTransport(failing_transport))
    )
    result = asyncio.run(
        executor.execute(
            "search_places",
            {"query": "昌平区政府", "limit": 1},
            session.vehicle,
            session,
            ToolContext(navigation_authorized=True),
        )
    )
    assert result.status == "blocked"
    assert result.output["code"] == "place_provider_unavailable"
    assert result.vehicle.route_polyline == []
