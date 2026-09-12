import { RealtimeAgent, tool } from '@openai/agents/realtime';

export const cabinPilotCompanyName = 'CabinGuard';

const demoState = {
  speedKmh: 82,
  gear: 'D',
  batteryPercent: 38,
  estimatedRangeKm: 176,
  cabinTemperatureC: 26.5,
  targetTemperatureC: 24,
  fanLevel: 2,
  circulation: 'inside',
  sunroofPercent: 0,
  sunshadePercent: 0,
  weather: 'cloudy',
  rainProbability: 20,
  destination: '',
};

const getVehicleState = tool({
  name: 'get_vehicle_state',
  description: 'Read current speed, gear, battery, range and navigation state. Call this before any action affected by vehicle state or safety.',
  parameters: {
    type: 'object',
    properties: {},
    required: [],
    additionalProperties: false,
  },
  execute: async () => ({
    speed_kmh: demoState.speedKmh,
    gear: demoState.gear,
    battery_percent: demoState.batteryPercent,
    estimated_range_km: demoState.estimatedRangeKm,
    destination: demoState.destination || null,
  }),
});

const getWeather = tool({
  name: 'get_weather',
  description: 'Read weather and rain probability at the vehicle location. Always call before opening the sunroof.',
  parameters: {
    type: 'object',
    properties: {
      location: { type: 'string', description: 'Location to check. Use current_location when the user does not specify one.' },
    },
    required: ['location'],
    additionalProperties: false,
  },
  execute: async () => ({
    condition: demoState.weather,
    rain_probability: demoState.rainProbability,
  }),
});

const getClimateState = tool({
  name: 'get_climate_state',
  description: 'Read cabin temperature, target temperature, fan level and circulation mode before changing comfort settings.',
  parameters: {
    type: 'object',
    properties: {},
    required: [],
    additionalProperties: false,
  },
  execute: async () => ({
    cabin_temperature_c: demoState.cabinTemperatureC,
    target_temperature_c: demoState.targetTemperatureC,
    fan_level: demoState.fanLevel,
    circulation: demoState.circulation,
  }),
});

const setClimate = tool({
  name: 'set_climate',
  description: 'Set target temperature, fan level and circulation. Use only after the user intent is clear.',
  parameters: {
    type: 'object',
    properties: {
      target_temperature_c: { type: 'number', minimum: 16, maximum: 30 },
      fan_level: { type: 'number', minimum: 1, maximum: 7 },
      circulation: { type: 'string', enum: ['inside', 'outside'] },
    },
    required: ['target_temperature_c', 'fan_level', 'circulation'],
    additionalProperties: false,
  },
  execute: async (input: any) => {
    const { target_temperature_c, fan_level, circulation } = input as {
      target_temperature_c: number;
      fan_level: number;
      circulation: 'inside' | 'outside';
    };
    demoState.targetTemperatureC = target_temperature_c;
    demoState.fanLevel = fan_level;
    demoState.circulation = circulation;
    return { executed: true, target_temperature_c, fan_level, circulation };
  },
});

const controlSunroof = tool({
  name: 'control_sunroof',
  description: 'Open or close the sunroof. This tool enforces weather and high-speed safety checks.',
  parameters: {
    type: 'object',
    properties: {
      target_percent: { type: 'number', minimum: 0, maximum: 100 },
      high_speed_confirmed: {
        type: 'boolean',
        description: 'True only when the user explicitly confirmed after being told the current high speed and wind-noise risk.',
      },
    },
    required: ['target_percent', 'high_speed_confirmed'],
    additionalProperties: false,
  },
  execute: async (input: any) => {
    const { target_percent, high_speed_confirmed } = input as {
      target_percent: number;
      high_speed_confirmed: boolean;
    };
    if (target_percent > 0 && demoState.rainProbability >= 50) {
      return { executed: false, reason: 'rain_risk', rain_probability: demoState.rainProbability };
    }
    if (target_percent > 0 && demoState.speedKmh >= 80 && !high_speed_confirmed) {
      return { executed: false, reason: 'confirmation_required', speed_kmh: demoState.speedKmh };
    }
    demoState.sunshadePercent = target_percent > 0 ? 100 : demoState.sunshadePercent;
    demoState.sunroofPercent = target_percent;
    return {
      executed: true,
      sunroof_percent: demoState.sunroofPercent,
      sunshade_percent: demoState.sunshadePercent,
    };
  },
});

const searchChargingStations = tool({
  name: 'search_charging_stations',
  description: 'Search fast charging stations along the active route and return detour, availability and arrival battery estimates.',
  parameters: {
    type: 'object',
    properties: {
      along_route: { type: 'boolean' },
      max_detour_km: { type: 'number', minimum: 0, maximum: 30 },
    },
    required: ['along_route', 'max_detour_km'],
    additionalProperties: false,
  },
  execute: async () => ({
    stations: [
      {
        name: '顺义服务区超充站',
        distance_km: 18.6,
        detour_km: 1.8,
        available_fast_chargers: 6,
        estimated_arrival_battery_percent: 31,
      },
      {
        name: '后沙峪公共快充站',
        distance_km: 14.2,
        detour_km: 4.7,
        available_fast_chargers: 2,
        estimated_arrival_battery_percent: 33,
      },
    ],
  }),
});

const startNavigation = tool({
  name: 'start_navigation',
  description: 'Start navigation to a destination returned by the charging-station search.',
  parameters: {
    type: 'object',
    properties: {
      destination: { type: 'string' },
    },
    required: ['destination'],
    additionalProperties: false,
  },
  execute: async (input: any) => {
    const { destination } = input as { destination: string };
    demoState.destination = destination;
    return { navigation_started: true, destination, eta_minutes: 16 };
  },
});

const controlTrunk = tool({
  name: 'control_trunk',
  description: 'Open the trunk only while the vehicle is parked in P gear. The tool blocks unsafe requests.',
  parameters: {
    type: 'object',
    properties: {
      action: { type: 'string', enum: ['open', 'close'] },
    },
    required: ['action'],
    additionalProperties: false,
  },
  execute: async (input: any) => {
    const { action } = input as { action: 'open' | 'close' };
    if (action === 'open' && (demoState.speedKmh > 0 || demoState.gear !== 'P')) {
      return {
        executed: false,
        reason: 'vehicle_not_parked',
        speed_kmh: demoState.speedKmh,
        gear: demoState.gear,
      };
    }
    return { executed: true, trunk: action === 'open' ? 'open' : 'closed' };
  },
});

export const cabinPilotAgent = new RealtimeAgent({
  name: 'cabinPilot',
  voice: 'sage',
  handoffDescription: 'A context-aware and safety-conscious cockpit task agent.',
  instructions: `
你是 CabinGuard，一名中文可信座舱任务 Agent。你的目标是帮助驾驶者完成座舱控制、车辆状态查询和补能导航，并确保每个结果可验证。

行为规则：
1. 默认使用简洁自然的中文，先理解用户要完成的任务，再调用工具。
2. 任何受车辆状态影响的动作，先调用 get_vehicle_state。打开天窗前还必须调用 get_weather。
3. 当前车速达到 80 km/h 时，打开天窗前必须说明当前车速和风噪风险，得到用户明确确认后才能把 high_speed_confirmed 设为 true。
4. 用户只说“调舒服一点”等模糊表达时，先追问是偏热、偏冷还是空气闷，不要猜测。
5. 搜索充电站前查询电量和续航；比较绕行距离、空闲快充和预计到达电量，解释选择后再导航。
6. 行驶中请求打开后备箱时调用 control_trunk 获取可核验的拦截结果，并明确说明没有执行。
7. 只有工具返回 executed: true 或 navigation_started: true 时，才可以说“已经完成”。工具失败或能力不存在时，必须如实说明。
8. 不要声称控制了未提供工具的车辆功能，也不要编造传感器状态、执行结果或安全规则。
`,
  tools: [
    getVehicleState,
    getWeather,
    getClimateState,
    setClimate,
    controlSunroof,
    searchChargingStations,
    startNavigation,
    controlTrunk,
  ],
  handoffs: [],
});

export const cabinPilotScenario = [cabinPilotAgent];
