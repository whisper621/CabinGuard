import { cabinApiUrl } from "./apiBase";
import type { OccupantRole } from "./i18n/zh-CN";

export type TaskStatus = "pending" | "running" | "success" | "blocked" | "skipped";
export type RiskLevel = "low" | "medium" | "high";

export type TaskNode = {
  id: string;
  domain: string;
  title: string;
  description: string;
  dependencies: string[];
  risk: RiskLevel;
  permission: string;
  parallelizable: boolean;
  allowedTools: string[];
  expectedEvidence: string[];
  status: TaskStatus;
};

export type TaskPlan = {
  id: string;
  version: string;
  objective: string;
  nodes: TaskNode[];
  executionWaves: string[][];
  allowedTools: string[];
  requiresConfirmation: boolean;
};

export type VehicleStateV6 = {
  speed: number;
  gear: "P" | "R" | "N" | "D";
  battery: number;
  range: number;
  cabinTemperature: number;
  targetTemperature: number;
  fanLevel: number;
  circulation: string;
  weather: string;
  rainProbability: number;
  currentLocation: string;
  destination: string;
  sunroof: number;
  trunkOpen: boolean;
  windows?: Record<string, number>;
  seats?: Record<string, number>;
  routeDistanceKm?: number | null;
  routeEtaMinutes?: number | null;
};

export type AgentTraceV6 = {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  status: "success" | "blocked";
  planId?: string;
  taskId?: string;
  domain?: string;
  policyCode?: string;
  stateVersionBefore?: number;
  stateVersionAfter?: number;
};

export type EvidenceEvent = {
  id: string;
  sessionId: string;
  planId: string | null;
  taskId: string | null;
  eventType: "plan.created" | "policy.decision" | "tool.receipt" | "signal.injected" | string;
  stateVersion: number;
  payload: Record<string, unknown>;
  createdAt: string;
};

export type AgentResponseV6 = {
  message: string;
  sessionId: string;
  occupantRole: OccupantRole;
  stateVersion: number;
  vehicle: VehicleStateV6;
  traces: AgentTraceV6[];
  plan?: TaskPlan;
  model: string;
  turns: number;
  totalTokens: number;
};

export const domainLabels: Record<string, string> = {
  system: "系统感知",
  navigation: "导航领域",
  comfort: "舒适控制",
  body_safety: "车身安全",
  media: "媒体娱乐",
  memory: "会话记忆",
};

export const eventLabels: Record<string, string> = {
  "plan.created": "任务图已创建",
  "policy.decision": "策略核已裁决",
  "tool.receipt": "工具回执已写入",
  "signal.injected": "车辆信号已注入",
};

export const v6WebSocketUrl = (sessionId: string) => {
  const api = cabinApiUrl("");
  const base = api
    ? api.replace(/\/$/, "").replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  return `${base}/ws/cabin/signals/${sessionId}`;
};

export async function readJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) throw new Error(payload.error?.message || `请求失败（${response.status}）`);
  return payload;
}
