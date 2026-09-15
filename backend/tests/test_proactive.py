from cabinguard.models import VehicleState, WindowState
from cabinguard.proactive import derive_proactive_suggestions


def ids(vehicle: VehicleState) -> set[str]:
    return {item.id for item in derive_proactive_suggestions(vehicle)}


def test_proactive_suggestions_cover_power_weather_air_and_perception_events() -> None:
    assert "low_battery_charge" in ids(VehicleState(battery=12, range=48))
    assert "rain_window_visibility" in ids(
        VehicleState(rain_probability=80, windows=WindowState(driver=20))
    )
    assert "air_quality_purify" in ids(VehicleState(airQuality={"pm25": 168}))
    assert "vision_visibility_defrost" in ids(
        VehicleState(perceptionEvent="windshield_visibility_low")
    )


def test_proactive_suggestions_never_claim_automatic_execution() -> None:
    suggestions = derive_proactive_suggestions(VehicleState(battery=10, range=30))
    assert suggestions
    assert all(item.requires_human_confirmation for item in suggestions)
