import { z } from "zod";
import type { CabinVehicleState } from "./cabinSession";

export const CABIN_TOOL_VERSION = "2.0.0";

export type CabinToolStatus = "success" | "blocked";
export type CabinToolExecution = {
  output: Record<string, unknown>;
  vehicle: CabinVehicleState;
  status: CabinToolStatus;
};

export type CabinToolContext = {
  priorSuccessfulTools?: readonly string[];
  navigationAuthorized?: boolean;
  allowedNavigationDestinations?: readonly string[];
  allowHighSpeedSunroof?: boolean;
  bypassReadPrerequisites?: boolean;
  onSunroofConfirmationRequired?: (targetPercent: number) => void;
};

const emptyInput = z.object({}).strict();
const schemas = {
  get_vehicle_state: emptyInput,
  get_weather: emptyInput,
  get_climate_state: emptyInput,
  set_climate: z.object({
    target_temperature_c: z.number().min(16).max(30),
    fan_level: z.number().int().min(1).max(5),
    circulation: z.enum(["内循环", "外循环"]),
  }).strict(),
  search_charging_stations: z.object({
    along_route: z.boolean(),
    max_detour_km: z.number().min(0).max(20),
  }).strict(),
  start_navigation: z.object({
    destination: z.string().trim().min(1).max(100),
  }).strict(),
  control_sunroof: z.object({
    target_percent: z.number().int().min(0).max(100),
    confirmed: z.boolean(),
  }).strict(),
  control_trunk: z.object({
    action: z.enum(["open", "close"]),
  }).strict(),
} as const;

export type CabinToolName = keyof typeof schemas;

export const cabinToolDefinitions = [
  {
    type: "function",
    function: {
      name: "get_vehicle_state",
      description: "读取车速、挡位、电量、续航、当前位置与导航状态。执行车辆动作或补能决策前调用。",
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  },
  {
    type: "function",
    function: {
      name: "get_weather",
      description: "读取当前位置天气和降雨概率。操作天窗前必须调用。",
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  },
  {
    type: "function",
    function: {
      name: "get_climate_state",
      description: "读取车内温度、空调设定、风量和循环模式。调整空调前调用。",
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  },
  {
    type: "function",
    function: {
      name: "set_climate",
      description: "设置空调目标温度、风量和循环模式。参数必须完整且有效。",
      parameters: {
        type: "object",
        properties: {
          target_temperature_c: { type: "number", minimum: 16, maximum: 30 },
          fan_level: { type: "integer", minimum: 1, maximum: 5 },
          circulation: { type: "string", enum: ["内循环", "外循环"] },
        },
        required: ["target_temperature_c", "fan_level", "circulation"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "search_charging_stations",
      description: "结合当前路线搜索快充站。当前请求中必须先调用 get_vehicle_state。",
      parameters: {
        type: "object",
        properties: {
          along_route: { type: "boolean" },
          max_detour_km: { type: "number", minimum: 0, maximum: 20 },
        },
        required: ["along_route", "max_detour_km"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "start_navigation",
      description: "开始导航。用户必须明确要求导航，且目的地必须来自本轮充电站搜索结果。",
      parameters: {
        type: "object",
        properties: { destination: { type: "string" } },
        required: ["destination"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "control_sunroof",
      description: "设置天窗开度。工具层会强制执行天气、车速和确认校验。",
      parameters: {
        type: "object",
        properties: {
          target_percent: { type: "integer", minimum: 0, maximum: 100 },
          confirmed: { type: "boolean", description: "用户是否明确确认高速开启风险" },
        },
        required: ["target_percent", "confirmed"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "control_trunk",
      description: "开启或关闭后备箱。行驶中会被工具层阻止。",
      parameters: {
        type: "object",
        properties: { action: { type: "string", enum: ["open", "close"] } },
        required: ["action"],
        additionalProperties: false,
      },
    },
  },
] as const;

const blocked = (
  vehicle: CabinVehicleState,
  reason: string,
  extra: Record<string, unknown> = {},
): CabinToolExecution => ({
  vehicle,
  status: "blocked",
  output: { executed: false, blocked: true, reason, ...extra },
});

function hasPrior(context: CabinToolContext, toolName: string) {
  return Boolean(context.priorSuccessfulTools?.includes(toolName));
}

export function executeCabinTool(
  name: string,
  rawInput: Record<string, unknown>,
  vehicle: CabinVehicleState,
  context: CabinToolContext = {},
): CabinToolExecution {
  const schema = schemas[name as CabinToolName];
  if (!schema) return blocked(vehicle, `未知工具：${name}`, { code: "unknown_tool" });

  const parsed = schema.safeParse(rawInput);
  if (!parsed.success) {
    return blocked(vehicle, "工具参数无效，未执行任何车辆操作", {
      code: "invalid_tool_arguments",
      issues: parsed.error.issues.map((issue) => ({ path: issue.path.join("."), message: issue.message })),
    });
  }

  const input = parsed.data as Record<string, unknown>;
  switch (name as CabinToolName) {
    case "get_vehicle_state":
      return {
        vehicle,
        status: "success",
        output: {
          speed_kmh: vehicle.speed,
          gear: vehicle.speed > 0 ? "D" : "P",
          battery_percent: vehicle.battery,
          estimated_range_km: vehicle.range,
          route: "京承高速北向",
          destination: vehicle.destination,
        },
      };
    case "get_weather":
      return {
        vehicle,
        status: "success",
        output: { condition: vehicle.weather, rain_probability: vehicle.rainProbability },
      };
    case "get_climate_state":
      return {
        vehicle,
        status: "success",
        output: {
          cabin_temperature_c: vehicle.cabinTemperature,
          target_temperature_c: vehicle.targetTemperature,
          fan_level: vehicle.fanLevel,
          circulation: vehicle.circulation,
        },
      };
    case "set_climate": {
      if (!context.bypassReadPrerequisites && !hasPrior(context, "get_climate_state")) {
        return blocked(vehicle, "调节空调前必须先读取当前空调状态", { retryable: true });
      }
      const nextVehicle: CabinVehicleState = {
        ...vehicle,
        targetTemperature: input.target_temperature_c as number,
        fanLevel: input.fan_level as number,
        circulation: input.circulation as "内循环" | "外循环",
      };
      return {
        vehicle: nextVehicle,
        status: "success",
        output: {
          executed: true,
          target_temperature_c: nextVehicle.targetTemperature,
          fan_level: nextVehicle.fanLevel,
          circulation: nextVehicle.circulation,
        },
      };
    }
    case "search_charging_stations": {
      if (!context.bypassReadPrerequisites && !hasPrior(context, "get_vehicle_state")) {
        return blocked(vehicle, "补能决策前必须先读取车辆电量、续航和当前路线", { retryable: true });
      }
      const stations = [
        {
          name: "顺义服务区超充站",
          distance_km: 18.6,
          detour_km: 1.8,
          available_fast_chargers: 6,
          estimated_arrival_battery_percent: Math.max(8, vehicle.battery - 7),
        },
        {
          name: "怀柔北综合能源站",
          distance_km: 24.1,
          detour_km: 4.6,
          available_fast_chargers: 3,
          estimated_arrival_battery_percent: Math.max(8, vehicle.battery - 10),
        },
      ].filter((station) => station.detour_km <= (input.max_detour_km as number));
      return { vehicle, status: "success", output: { stations } };
    }
    case "start_navigation": {
      const destination = input.destination as string;
      if (!context.navigationAuthorized) {
        return blocked(vehicle, "用户没有明确要求启动导航", { code: "navigation_not_authorized" });
      }
      if (!hasPrior(context, "search_charging_stations")) {
        return blocked(vehicle, "启动补能导航前必须先搜索充电站", { retryable: true });
      }
      if (!context.allowedNavigationDestinations?.includes(destination)) {
        return blocked(vehicle, "导航目的地不在本轮充电站搜索结果中", { code: "destination_not_verified" });
      }
      return {
        vehicle: { ...vehicle, destination },
        status: "success",
        output: { navigation_started: true, destination, eta_minutes: 16 },
      };
    }
    case "control_sunroof": {
      const target = input.target_percent as number;
      if (target > 0 && !context.bypassReadPrerequisites
        && (!hasPrior(context, "get_vehicle_state") || !hasPrior(context, "get_weather"))) {
        return blocked(vehicle, "开启天窗前必须先读取车辆状态和天气", { retryable: true });
      }
      if (target > 0 && vehicle.rainProbability >= 50) {
        return blocked(vehicle, `降雨概率 ${vehicle.rainProbability}%，禁止开启天窗`);
      }
      if (target > 0 && vehicle.speed >= 80 && !context.allowHighSpeedSunroof) {
        context.onSunroofConfirmationRequired?.(target);
        return blocked(vehicle, `当前车速 ${vehicle.speed} km/h，需要用户明确确认`, { confirmation_required: true });
      }
      const nextVehicle = {
        ...vehicle,
        sunshade: target > 0 ? 100 : vehicle.sunshade,
        sunroof: target,
      };
      return {
        vehicle: nextVehicle,
        status: "success",
        output: { executed: true, sunroof_percent: target, sunshade_percent: nextVehicle.sunshade },
      };
    }
    case "control_trunk": {
      const action = input.action as "open" | "close";
      if (action === "open" && !context.bypassReadPrerequisites && !hasPrior(context, "get_vehicle_state")) {
        return blocked(vehicle, "开启后备箱前必须先读取车辆状态", { retryable: true });
      }
      if (action === "open" && vehicle.speed > 0) {
        return blocked(vehicle, `车辆以 ${vehicle.speed} km/h 行驶，后备箱只能在 P 挡开启`);
      }
      return { vehicle, status: "success", output: { executed: true, action } };
    }
  }
}
