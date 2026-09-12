from cabinguard.models import VehicleState
from cabinguard.tools import ToolContext, execute_tool


def vehicle() -> VehicleState:
    return VehicleState()


def test_rejects_unknown_tool() -> None:
    result = execute_tool("delete_vehicle", {}, vehicle())
    assert result.status == "blocked"
    assert result.output["code"] == "unknown_tool"


def test_rejects_invalid_arguments_without_coercion() -> None:
    original = vehicle()
    result = execute_tool(
        "set_climate",
        {
            "target_temperature_c": "23",
            "fan_level": 9,
            "circulation": "auto",
        },
        original,
        ToolContext(prior_successful_tools=("get_climate_state",)),
    )
    assert result.status == "blocked"
    assert result.output["code"] == "invalid_tool_arguments"
    assert result.vehicle == original


def test_rejects_extra_arguments() -> None:
    result = execute_tool("get_vehicle_state", {"admin": True}, vehicle())
    assert result.status == "blocked"


def test_enforces_climate_read_prerequisite() -> None:
    result = execute_tool(
        "set_climate",
        {
            "target_temperature_c": 23,
            "fan_level": 2,
            "circulation": "外循环",
        },
        vehicle(),
    )
    assert result.status == "blocked"
    assert result.vehicle.target_temperature == 24


def test_updates_climate_after_read() -> None:
    result = execute_tool(
        "set_climate",
        {
            "target_temperature_c": 23,
            "fan_level": 3,
            "circulation": "外循环",
        },
        vehicle(),
        ToolContext(prior_successful_tools=("get_climate_state",)),
    )
    assert result.status == "success"
    assert result.vehicle.target_temperature == 23
    assert result.vehicle.fan_level == 3
    assert result.vehicle.circulation == "外循环"


def test_reads_vehicle_state() -> None:
    result = execute_tool("get_vehicle_state", {}, vehicle())
    assert result.status == "success"
    assert result.output["gear"] == "D"
    assert result.output["battery_percent"] == 38
    assert result.output["current_location"]["source"] == "simulated"  # type: ignore[index]
    assert "latitude" not in result.output["current_location"]  # type: ignore[operator]


def test_requires_both_reads_before_sunroof() -> None:
    result = execute_tool(
        "control_sunroof",
        {"target_percent": 50, "confirmed": False},
        vehicle(),
        ToolContext(prior_successful_tools=("get_vehicle_state",)),
    )
    assert result.status == "blocked"
    assert result.output["retryable"] is True


def test_hard_blocks_sunroof_in_rain() -> None:
    rainy = vehicle().model_copy(update={"rain_probability": 70})
    result = execute_tool(
        "control_sunroof",
        {"target_percent": 30, "confirmed": False},
        rainy,
        ToolContext(prior_successful_tools=("get_vehicle_state", "get_weather")),
    )
    assert result.status == "blocked"
    assert result.vehicle.sunroof == 0


def test_model_confirmation_flag_does_not_authorize() -> None:
    pending: list[int] = []
    result = execute_tool(
        "control_sunroof",
        {"target_percent": 50, "confirmed": True},
        vehicle(),
        ToolContext(
            prior_successful_tools=("get_vehicle_state", "get_weather"),
            on_sunroof_confirmation_required=pending.append,
        ),
    )
    assert result.status == "blocked"
    assert pending == [50]
    assert result.vehicle.sunroof == 0


def test_server_confirmation_resume_executes() -> None:
    result = execute_tool(
        "control_sunroof",
        {"target_percent": 50, "confirmed": True},
        vehicle(),
        ToolContext(
            allow_high_speed_sunroof=True,
            bypass_read_prerequisites=True,
        ),
    )
    assert result.status == "success"
    assert result.vehicle.sunroof == 50
    assert result.vehicle.sunshade == 100


def test_blocks_trunk_while_moving() -> None:
    result = execute_tool(
        "control_trunk",
        {"action": "open"},
        vehicle(),
        ToolContext(prior_successful_tools=("get_vehicle_state",)),
    )
    assert result.status == "blocked"


def test_allows_trunk_while_parked() -> None:
    parked = vehicle().model_copy(update={"speed": 0})
    result = execute_tool(
        "control_trunk",
        {"action": "open"},
        parked,
        ToolContext(prior_successful_tools=("get_vehicle_state",)),
    )
    assert result.status == "success"


def test_filters_charging_stations_by_detour() -> None:
    result = execute_tool(
        "search_charging_stations",
        {"along_route": True, "max_detour_km": 2},
        vehicle(),
        ToolContext(prior_successful_tools=("get_vehicle_state",)),
    )
    assert result.status == "success"
    assert len(result.output["stations"]) == 1  # type: ignore[arg-type]
    station = result.output["stations"][0]  # type: ignore[index]
    assert station["latitude"] == 40.1672
    assert station["data_source"] == "CabinGuard demo catalog"


def test_blocks_search_without_vehicle_read() -> None:
    result = execute_tool(
        "search_charging_stations",
        {"along_route": True, "max_detour_km": 5},
        vehicle(),
    )
    assert result.status == "blocked"


def test_blocks_unauthorized_navigation() -> None:
    result = execute_tool(
        "start_navigation",
        {"destination": "顺义服务区超充站"},
        vehicle(),
        ToolContext(
            prior_successful_tools=("search_charging_stations",),
            allowed_navigation_destinations=("顺义服务区超充站",),
        ),
    )
    assert result.status == "blocked"
    assert result.output["code"] == "navigation_not_authorized"


def test_blocks_unverified_destination() -> None:
    result = execute_tool(
        "start_navigation",
        {"destination": "未知地点"},
        vehicle(),
        ToolContext(
            navigation_authorized=True,
            prior_successful_tools=("search_charging_stations",),
            allowed_navigation_destinations=("顺义服务区超充站",),
        ),
    )
    assert result.status == "blocked"
    assert result.output["code"] == "destination_not_verified"


def test_starts_verified_navigation() -> None:
    destination = "顺义服务区超充站"
    result = execute_tool(
        "start_navigation",
        {"destination": destination},
        vehicle(),
        ToolContext(
            navigation_authorized=True,
            prior_successful_tools=("search_charging_stations",),
            allowed_navigation_destinations=(destination,),
        ),
    )
    assert result.status == "success"
    assert result.vehicle.destination == destination
    assert result.vehicle.route_distance_km == 18.6
    assert result.vehicle.route_eta_minutes is not None
    assert len(result.vehicle.route_polyline) == 3
    assert result.output["route_provider"] == "CabinGuard navigation sandbox"


def test_browser_location_changes_route_estimate() -> None:
    located = vehicle().model_copy(
        update={
            "location_source": "browser_geolocation",
            "latitude": 40.1,
            "longitude": 116.55,
        }
    )
    destination = "顺义服务区超充站"
    result = execute_tool(
        "start_navigation",
        {"destination": destination},
        located,
        ToolContext(
            navigation_authorized=True,
            prior_successful_tools=("search_charging_stations",),
            allowed_navigation_destinations=(destination,),
        ),
    )
    assert result.status == "success"
    assert result.vehicle.route_distance_km != 18.6
