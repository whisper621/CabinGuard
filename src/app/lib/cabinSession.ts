import { randomUUID } from "crypto";

export type CabinScenario = "default" | "rain" | "moving";
export type BrowserLocation = {
  latitude: number;
  longitude: number;
  accuracyMeters?: number;
};

export type GeoPoint = {
  latitude: number;
  longitude: number;
};

export type CabinVehicleState = {
  speed: number;
  battery: number;
  range: number;
  cabinTemperature: number;
  targetTemperature: number;
  fanLevel: number;
  circulation: "内循环" | "外循环";
  sunroof: number;
  sunshade: number;
  weather: string;
  rainProbability: number;
  currentLocation: string;
  latitude: number;
  longitude: number;
  locationSource: "simulated" | "browser_geolocation";
  locationAccuracyMeters: number | null;
  destination: string;
  routeDistanceKm: number | null;
  routeEtaMinutes: number | null;
  routePolyline: GeoPoint[];
};

type PendingSunroofAction = {
  kind: "sunroof";
  targetPercent: number;
  expiresAt: number;
};

export type CabinSession = {
  id: string;
  scenario: CabinScenario;
  vehicle: CabinVehicleState;
  createdAt: number;
  expiresAt: number;
  pendingAction?: PendingSunroofAction;
};

type RateWindow = { startedAt: number; count: number };

const SESSION_TTL_MS = 30 * 60 * 1000;
const CONFIRMATION_TTL_MS = 2 * 60 * 1000;
const RATE_WINDOW_MS = 5 * 60 * 1000;
const RATE_LIMIT = 30;
const MAX_SESSIONS = 300;

type CabinStore = {
  sessions: Map<string, CabinSession>;
  rateWindows: Map<string, RateWindow>;
};

const globalStore = globalThis as typeof globalThis & { __cabinGuardStore?: CabinStore };
const store = globalStore.__cabinGuardStore ?? {
  sessions: new Map<string, CabinSession>(),
  rateWindows: new Map<string, RateWindow>(),
};

globalStore.__cabinGuardStore = store;

const baseVehicle = (): CabinVehicleState => ({
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
  currentLocation: "京承高速模拟起点",
  latitude: 40.0415,
  longitude: 116.4836,
  locationSource: "simulated",
  locationAccuracyMeters: null,
  destination: "未设置",
  routeDistanceKm: null,
  routeEtaMinutes: null,
  routePolyline: [],
});

const buildScenario = (
  scenario: CabinScenario,
  location?: BrowserLocation,
): CabinVehicleState => {
  const vehicle = location
    ? {
        ...baseVehicle(),
        currentLocation: "浏览器授权位置",
        latitude: location.latitude,
        longitude: location.longitude,
        locationSource: "browser_geolocation" as const,
        locationAccuracyMeters: location.accuracyMeters ?? null,
      }
    : baseVehicle();
  if (scenario === "rain") return { ...vehicle, speed: 0, weather: "小雨", rainProbability: 70 };
  if (scenario === "moving") return { ...vehicle, speed: 35 };
  return vehicle;
};

function prune() {
  const now = Date.now();
  for (const [id, session] of store.sessions) {
    if (session.expiresAt <= now) store.sessions.delete(id);
  }
  for (const [key, window] of store.rateWindows) {
    if (window.startedAt + RATE_WINDOW_MS <= now) store.rateWindows.delete(key);
  }
  while (store.sessions.size >= MAX_SESSIONS) {
    const oldest = store.sessions.keys().next().value;
    if (!oldest) break;
    store.sessions.delete(oldest);
  }
}

export function createCabinSession(
  scenario: CabinScenario = "default",
  location?: BrowserLocation,
) {
  prune();
  const now = Date.now();
  const session: CabinSession = {
    id: randomUUID(),
    scenario,
    vehicle: buildScenario(scenario, location),
    createdAt: now,
    expiresAt: now + SESSION_TTL_MS,
  };
  store.sessions.set(session.id, session);
  return session;
}

export function getCabinSession(id: string) {
  prune();
  const session = store.sessions.get(id);
  if (!session) return null;
  session.expiresAt = Date.now() + SESSION_TTL_MS;
  if (session.pendingAction && session.pendingAction.expiresAt <= Date.now()) {
    delete session.pendingAction;
  }
  return session;
}

export function updateCabinSession(session: CabinSession, vehicle: CabinVehicleState) {
  session.vehicle = vehicle;
  session.expiresAt = Date.now() + SESSION_TTL_MS;
  store.sessions.set(session.id, session);
}

export function createSunroofConfirmation(session: CabinSession, targetPercent: number) {
  session.pendingAction = {
    kind: "sunroof",
    targetPercent,
    expiresAt: Date.now() + CONFIRMATION_TTL_MS,
  };
  store.sessions.set(session.id, session);
}

export function takeSunroofConfirmation(session: CabinSession) {
  const pending = session.pendingAction;
  if (!pending || pending.kind !== "sunroof" || pending.expiresAt <= Date.now()) {
    delete session.pendingAction;
    return null;
  }
  delete session.pendingAction;
  store.sessions.set(session.id, session);
  return pending;
}

export function clearPendingAction(session: CabinSession) {
  delete session.pendingAction;
  store.sessions.set(session.id, session);
}

export function consumeRateLimit(key: string) {
  prune();
  const now = Date.now();
  const existing = store.rateWindows.get(key);
  if (!existing || existing.startedAt + RATE_WINDOW_MS <= now) {
    store.rateWindows.set(key, { startedAt: now, count: 1 });
    return { allowed: true, retryAfterSeconds: 0 };
  }
  if (existing.count >= RATE_LIMIT) {
    return {
      allowed: false,
      retryAfterSeconds: Math.max(1, Math.ceil((existing.startedAt + RATE_WINDOW_MS - now) / 1000)),
    };
  }
  existing.count += 1;
  return { allowed: true, retryAfterSeconds: 0 };
}

export const isCabinScenario = (value: unknown): value is CabinScenario =>
  value === "default" || value === "rain" || value === "moving";

export const isBrowserLocation = (value: unknown): value is BrowserLocation => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const location = value as Record<string, unknown>;
  const keys = Object.keys(location);
  if (keys.some((key) => !["latitude", "longitude", "accuracyMeters"].includes(key))) return false;
  const latitude = location.latitude;
  const longitude = location.longitude;
  const accuracy = location.accuracyMeters;
  return typeof latitude === "number"
    && Number.isFinite(latitude)
    && latitude >= -90
    && latitude <= 90
    && typeof longitude === "number"
    && Number.isFinite(longitude)
    && longitude >= -180
    && longitude <= 180
    && (accuracy === undefined
      || (typeof accuracy === "number" && Number.isFinite(accuracy) && accuracy >= 0));
};

export const sessionTtlSeconds = Math.floor(SESSION_TTL_MS / 1000);
