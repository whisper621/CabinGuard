from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Scenario = Literal[
    "default",
    "rain",
    "moving",
    "highway",
    "low_battery",
    "child",
    "pickup",
    "rest",
    "air_quality",
]
ToolStatus = Literal["success", "blocked"]


class GeoPoint(BaseModel):
    """A WGS84 point used by navigation providers."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RouteAlternative(BaseModel):
    label: str
    distance_km: float = Field(ge=0, alias="distanceKm")
    eta_minutes: int = Field(ge=0, alias="etaMinutes")


class WindowState(BaseModel):
    """Window opening percentages by seat row and side."""

    model_config = ConfigDict(populate_by_name=True)

    driver: int = Field(0, ge=0, le=100)
    passenger: int = Field(0, ge=0, le=100)
    rear_left: int = Field(0, ge=0, le=100, alias="rearLeft")
    rear_right: int = Field(0, ge=0, le=100, alias="rearRight")


class SeatComfortState(BaseModel):
    """Heating and ventilation levels exposed by the demo seat controller."""

    model_config = ConfigDict(populate_by_name=True)

    driver_heating: int = Field(0, ge=0, le=3, alias="driverHeating")
    passenger_heating: int = Field(0, ge=0, le=3, alias="passengerHeating")
    rear_left_heating: int = Field(0, ge=0, le=3, alias="rearLeftHeating")
    rear_right_heating: int = Field(0, ge=0, le=3, alias="rearRightHeating")
    driver_ventilation: int = Field(0, ge=0, le=3, alias="driverVentilation")
    passenger_ventilation: int = Field(0, ge=0, le=3, alias="passengerVentilation")
    rear_left_ventilation: int = Field(0, ge=0, le=3, alias="rearLeftVentilation")
    rear_right_ventilation: int = Field(0, ge=0, le=3, alias="rearRightVentilation")


class AmbientLightState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = False
    color: Literal["ice_blue", "warm_orange", "violet", "white"] = "ice_blue"
    brightness: int = Field(50, ge=0, le=100)


class DefrostState(BaseModel):
    front: bool = False
    rear: bool = False


class DoorState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    driver: bool = False
    passenger: bool = False
    rear_left: bool = Field(False, alias="rearLeft")
    rear_right: bool = Field(False, alias="rearRight")


class MirrorState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    driver_folded: bool = Field(False, alias="driverFolded")
    passenger_folded: bool = Field(False, alias="passengerFolded")
    driver_heating: bool = Field(False, alias="driverHeating")
    passenger_heating: bool = Field(False, alias="passengerHeating")


class AirQualityState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pm25: int = Field(18, ge=0, le=999)
    purifier_enabled: bool = Field(False, alias="purifierEnabled")
    purifier_level: int = Field(0, ge=0, le=3, alias="purifierLevel")
    fragrance: Literal["off", "forest", "ocean", "citrus"] = "off"


class MediaTrack(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    artist: str
    album: str = ""
    artwork_url: str = Field("", alias="artworkUrl")
    preview_url: str = Field("", alias="previewUrl")
    duration_seconds: int = Field(0, ge=0, alias="durationSeconds")


class MediaState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: Literal["none", "music", "radio", "podcast"] = "none"
    playing: bool = False
    volume: int = Field(35, ge=0, le=100)
    current_index: int = Field(0, ge=0, alias="currentIndex")
    current: MediaTrack | None = None
    queue: list[MediaTrack] = Field(default_factory=list)


class VehicleState(BaseModel):
    """Trusted server-side state for the simulated vehicle."""

    model_config = ConfigDict(populate_by_name=True)

    speed: float = 82
    gear: Literal["P", "R", "N", "D"] = "D"
    battery: float = 38
    range: float = 176
    cabin_temperature: float = Field(26.5, alias="cabinTemperature")
    target_temperature: float = Field(24, alias="targetTemperature")
    fan_level: int = Field(2, alias="fanLevel")
    circulation: Literal["内循环", "外循环"] = "内循环"
    sunroof: int = 0
    sunshade: int = 0
    windows: WindowState = Field(default_factory=WindowState)
    seats: SeatComfortState = Field(default_factory=SeatComfortState)
    ambient_light: AmbientLightState = Field(
        default_factory=AmbientLightState, alias="ambientLight"
    )
    defrost: DefrostState = Field(default_factory=DefrostState)
    doors: DoorState = Field(default_factory=DoorState)
    mirrors: MirrorState = Field(default_factory=MirrorState)
    wiper_mode: Literal["off", "auto", "slow", "medium", "high"] = Field(
        "off", alias="wiperMode"
    )
    air_quality: AirQualityState = Field(default_factory=AirQualityState, alias="airQuality")
    child_lock: bool = Field(False, alias="childLock")
    trunk_open: bool = Field(False, alias="trunkOpen")
    charge_port_open: bool = Field(False, alias="chargePortOpen")
    media: MediaState = Field(default_factory=MediaState)
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
    external_routing_consent: bool = Field(False, alias="externalRoutingConsent")
    destination: str = "未设置"
    destination_latitude: float | None = Field(None, ge=-90, le=90, alias="destinationLatitude")
    destination_longitude: float | None = Field(
        None, ge=-180, le=180, alias="destinationLongitude"
    )
    route_distance_km: float | None = Field(None, ge=0, alias="routeDistanceKm")
    route_eta_minutes: int | None = Field(None, ge=0, alias="routeEtaMinutes")
    route_polyline: list[GeoPoint] = Field(default_factory=list, alias="routePolyline")
    route_provider: str = Field("未启动", alias="routeProvider")
    route_data_freshness: str = Field("—", alias="routeDataFreshness")
    route_steps: list[str] = Field(default_factory=list, alias="routeSteps")
    route_alternatives: list[RouteAlternative] = Field(
        default_factory=list, alias="routeAlternatives"
    )
    navigation_url: str | None = Field(None, alias="navigationUrl")
    estimated_arrival_battery: float | None = Field(
        None, ge=0, le=100, alias="estimatedArrivalBattery"
    )

    def public_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)


class ToolExecution(BaseModel):
    output: dict[str, object]
    vehicle: VehicleState
    status: ToolStatus


class Trace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    input: dict[str, object]
    output: dict[str, object]
    status: ToolStatus
    plan_id: str | None = Field(default=None, alias="planId")
    task_id: str | None = Field(default=None, alias="taskId")
    domain: str | None = None
    policy_code: str | None = Field(default=None, alias="policyCode")
    state_version_before: int | None = Field(default=None, alias="stateVersionBefore")
    state_version_after: int | None = Field(default=None, alias="stateVersionAfter")

    def public_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, exclude_none=True)
