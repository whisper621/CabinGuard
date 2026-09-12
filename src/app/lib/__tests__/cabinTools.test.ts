import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CabinVehicleState } from "../cabinSession";
import { executeCabinTool } from "../cabinTools";

const vehicleFixture = (): CabinVehicleState => ({
  speed: 82,
  battery: 38,
  range: 176,
  cabinTemperature: 26.5,
  targetTemperature: 24,
  fanLevel: 2,
  circulation: "内循环",
  sunroof: 0,
  sunshade: 0,
  weather: "多云",
  rainProbability: 20,
  destination: "未设置",
});

describe("executeCabinTool", () => {
  let vehicle: CabinVehicleState;

  beforeEach(() => {
    vehicle = vehicleFixture();
  });

  it("rejects invalid model arguments instead of silently coercing them", () => {
    const result = executeCabinTool("set_climate", {
      target_temperature_c: "23",
      fan_level: 9,
      circulation: "auto",
    }, vehicle, { priorSuccessfulTools: ["get_climate_state"] });

    expect(result.status).toBe("blocked");
    expect(result.output.code).toBe("invalid_tool_arguments");
    expect(result.vehicle).toEqual(vehicle);
  });

  it("enforces the climate read prerequisite", () => {
    const result = executeCabinTool("set_climate", {
      target_temperature_c: 23,
      fan_level: 2,
      circulation: "外循环",
    }, vehicle);
    expect(result.status).toBe("blocked");
    expect(result.vehicle.targetTemperature).toBe(24);
  });

  it("updates climate after a verified read", () => {
    const result = executeCabinTool("set_climate", {
      target_temperature_c: 23,
      fan_level: 3,
      circulation: "外循环",
    }, vehicle, { priorSuccessfulTools: ["get_climate_state"] });
    expect(result.status).toBe("success");
    expect(result.vehicle).toMatchObject({ targetTemperature: 23, fanLevel: 3, circulation: "外循环" });
  });

  it("requires both state and weather reads before opening the sunroof", () => {
    const result = executeCabinTool("control_sunroof", {
      target_percent: 50,
      confirmed: false,
    }, vehicle, { priorSuccessfulTools: ["get_vehicle_state"] });
    expect(result.status).toBe("blocked");
    expect(result.output.retryable).toBe(true);
  });

  it("hard-blocks sunroof opening in rain", () => {
    vehicle.rainProbability = 70;
    const result = executeCabinTool("control_sunroof", {
      target_percent: 30,
      confirmed: false,
    }, vehicle, { priorSuccessfulTools: ["get_vehicle_state", "get_weather"] });
    expect(result.status).toBe("blocked");
    expect(result.vehicle.sunroof).toBe(0);
  });

  it("creates a pending action instead of trusting the model confirmation flag", () => {
    const onConfirmation = vi.fn();
    const result = executeCabinTool("control_sunroof", {
      target_percent: 50,
      confirmed: true,
    }, vehicle, {
      priorSuccessfulTools: ["get_vehicle_state", "get_weather"],
      onSunroofConfirmationRequired: onConfirmation,
    });
    expect(result.status).toBe("blocked");
    expect(onConfirmation).toHaveBeenCalledWith(50);
    expect(result.vehicle.sunroof).toBe(0);
  });

  it("executes only through the server confirmation-resume path", () => {
    const result = executeCabinTool("control_sunroof", {
      target_percent: 50,
      confirmed: true,
    }, vehicle, { allowHighSpeedSunroof: true, bypassReadPrerequisites: true });
    expect(result.status).toBe("success");
    expect(result.vehicle.sunroof).toBe(50);
  });

  it("blocks opening the trunk while moving", () => {
    const result = executeCabinTool("control_trunk", { action: "open" }, vehicle, {
      priorSuccessfulTools: ["get_vehicle_state"],
    });
    expect(result.status).toBe("blocked");
  });

  it("filters charging stations by the requested detour", () => {
    const result = executeCabinTool("search_charging_stations", {
      along_route: true,
      max_detour_km: 2,
    }, vehicle, { priorSuccessfulTools: ["get_vehicle_state"] });
    expect(result.status).toBe("success");
    expect(result.output.stations).toHaveLength(1);
  });

  it("blocks navigation that the user did not authorize", () => {
    const result = executeCabinTool("start_navigation", {
      destination: "顺义服务区超充站",
    }, vehicle, {
      priorSuccessfulTools: ["search_charging_stations"],
      allowedNavigationDestinations: ["顺义服务区超充站"],
    });
    expect(result.status).toBe("blocked");
    expect(result.output.code).toBe("navigation_not_authorized");
  });

  it("blocks a destination not returned by the current search", () => {
    const result = executeCabinTool("start_navigation", {
      destination: "未知地点",
    }, vehicle, {
      navigationAuthorized: true,
      priorSuccessfulTools: ["search_charging_stations"],
      allowedNavigationDestinations: ["顺义服务区超充站"],
    });
    expect(result.status).toBe("blocked");
    expect(result.output.code).toBe("destination_not_verified");
  });

  it("starts navigation when intent and destination are both verified", () => {
    const result = executeCabinTool("start_navigation", {
      destination: "顺义服务区超充站",
    }, vehicle, {
      navigationAuthorized: true,
      priorSuccessfulTools: ["search_charging_stations"],
      allowedNavigationDestinations: ["顺义服务区超充站"],
    });
    expect(result.status).toBe("success");
    expect(result.vehicle.destination).toBe("顺义服务区超充站");
  });
});
