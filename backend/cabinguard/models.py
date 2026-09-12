from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scenario = Literal["default", "rain", "moving"]
ToolStatus = Literal["success", "blocked"]


class GeoPoint(BaseModel):
    """A WGS84 point used by the navigation sandbox."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class VehicleState(BaseModel):
    """Trusted server-side state for the simulated vehicle."""

    model_config = ConfigDict(populate_by_name=True)

    speed: float = 82
    battery: float = 38
    range: float = 176
    cabin_temperature: float = Field(26.5, alias="cabinTemperature")
    target_temperature: float = Field(24, alias="targetTemperature")
    fan_level: int = Field(2, alias="fanLevel")
    circulation: Literal["内循环", "外循环"] = "内循环"
    sunroof: int = 0
    sunshade: int = 0
    weather: str = "多云"
    rain_probability: float = Field(20, alias="rainProbability")
    current_location: str = Field("京承高速模拟起点", alias="currentLocation")
    latitude: float = Field(40.0415, ge=-90, le=90)
    longitude: float = Field(116.4836, ge=-180, le=180)
    location_source: Literal["simulated", "browser_geolocation"] = Field(
        "simulated", alias="locationSource"
    )
    location_accuracy_meters: float | None = Field(
        None, ge=0, alias="locationAccuracyMeters"
    )
    destination: str = "未设置"
    route_distance_km: float | None = Field(None, ge=0, alias="routeDistanceKm")
    route_eta_minutes: int | None = Field(None, ge=0, alias="routeEtaMinutes")
    route_polyline: list[GeoPoint] = Field(default_factory=list, alias="routePolyline")

    def public_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)


class ToolExecution(BaseModel):
    output: dict[str, object]
    vehicle: VehicleState
    status: ToolStatus


class Trace(BaseModel):
    id: str
    name: str
    input: dict[str, object]
    output: dict[str, object]
    status: ToolStatus

    def public_dict(self) -> dict[str, object]:
        return self.model_dump()
