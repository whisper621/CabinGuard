"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ProductNav from "../components/ProductNav";
import { cabinApiUrl, usesExternalCabinApi } from "../lib/apiBase";
import { domainLabels, type AgentTraceV6, type TaskPlan } from "../lib/cabinV6";
import { zhCN, type OccupantRole } from "../lib/i18n/zh-CN";
import LiveRouteMap from "./LiveRouteMap";

type GeoPoint = { latitude: number; longitude: number };
type RouteAlternative = { label: string; distanceKm: number; etaMinutes: number };
type VehicleState = {
  speed: number; gear: "P" | "R" | "N" | "D"; battery: number; range: number; cabinTemperature: number;
  targetTemperature: number; fanLevel: number; circulation: "内循环" | "外循环";
  sunroof: number; sunshade: number; weather: string; rainProbability: number;
  currentLocation: string; latitude: number; longitude: number;
  locationSource: "simulated" | "browser_geolocation"; locationAccuracyMeters: number | null;
  externalRoutingConsent: boolean; destination: string; destinationLatitude: number | null;
  destinationLongitude: number | null; routeDistanceKm: number | null; routeEtaMinutes: number | null;
  routePolyline: GeoPoint[]; routeProvider: string; routeDataFreshness: string;
  routeSteps: string[]; routeAlternatives: RouteAlternative[]; navigationUrl: string | null;
  estimatedArrivalBattery: number | null;
  windows: { driver: number; passenger: number; rearLeft: number; rearRight: number };
  seats: { driverHeating: number; passengerHeating: number; rearLeftHeating: number; rearRightHeating: number; driverVentilation: number; passengerVentilation: number; rearLeftVentilation: number; rearRightVentilation: number };
  ambientLight: { enabled: boolean; color: "ice_blue" | "warm_orange" | "violet" | "white"; brightness: number };
  defrost: { front: boolean; rear: boolean }; childLock: boolean; trunkOpen: boolean;
};
type CabinScenario = "default" | "rain" | "moving";
type BrowserLocation = { latitude: number; longitude: number; accuracyMeters?: number; allowExternalRouting?: boolean };
type Panel = "assistant" | "plan" | "trace" | "policy";
type SpeechRecognitionLike = {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
  start: () => void; stop: () => void;
  onresult: ((event: { results: { length: number; [index: number]: { [index: number]: { transcript: string } } } }) => void) | null;
  onerror: ((event: { error: string }) => void) | null; onend: (() => void) | null;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type Message = { role: "user" | "assistant"; content: string; time: string };
type Trace = AgentTraceV6;
type AgentResponse = {
  message: string; sessionId: string; vehicle: VehicleState; traces: Trace[]; model: string;
  turns: number; totalTokens: number; promptVersion: string; toolVersion: string; plan?: TaskPlan;
  occupantRole: OccupantRole; stateVersion: number; error?: { message?: string };
};

const initialVehicle: VehicleState = {
  speed: 82, gear: "D", battery: 38, range: 176, cabinTemperature: 26.5, targetTemperature: 24,
  fanLevel: 2, circulation: "内循环", sunroof: 0, sunshade: 0, weather: "多云",
  rainProbability: 20, currentLocation: "京承高速模拟起点", latitude: 40.0415,
  longitude: 116.4836, locationSource: "simulated", locationAccuracyMeters: null,
  externalRoutingConsent: false, destination: "未设置", destinationLatitude: null,
  destinationLongitude: null, routeDistanceKm: null, routeEtaMinutes: null,
  routePolyline: [], routeProvider: "未启动", routeDataFreshness: "—", routeSteps: [],
  routeAlternatives: [], navigationUrl: null, estimatedArrivalBattery: null,
  windows: { driver: 0, passenger: 0, rearLeft: 0, rearRight: 0 },
  seats: { driverHeating: 0, passengerHeating: 0, rearLeftHeating: 0, rearRightHeating: 0, driverVentilation: 0, passengerVentilation: 0, rearLeftVentilation: 0, rearRightVentilation: 0 },
  ambientLight: { enabled: false, color: "ice_blue", brightness: 50 },
  defrost: { front: false, rear: false }, childLock: false, trunkOpen: false,
};
const prompts = ["导航到昌平区政府，同时把空调调到23度", "把主驾车窗打开一半，再开2挡座椅通风", "把氛围灯调成紫色、亮度40%", "记住我喜欢22度外循环", "你现在支持哪些能力？"];
const scenarioOptions: Array<{ value: CabinScenario; label: string; hint: string }> = [
  { value: "default", label: "高速巡航", hint: "82 km/h" },
  { value: "rain", label: "雨天驻车", hint: "P 挡 · 70%" },
  { value: "moving", label: "城区行驶", hint: "35 km/h" },
];
const policies = [
  ["目的地可信", "普通导航只能使用本会话实时检索返回的候选 ID。"],
  ["坐标隔离", "精确起点用于道路算路，不写入大模型工具回执。"],
  ["显式授权", "定位由浏览器询问；外部算路需用户点击授权入口。"],
  ["先读后写", "车控动作执行前必须读取对应车辆状态。"],
  ["驾驶安全", "行驶中禁开后备箱；高速开天窗要求二次确认。"],
  ["天气联锁", "高降雨概率时拒绝打开天窗。"],
  ["真实声明", "地图或算路服务失败时阻断，不生成虚假路线。"],
  ["最小披露", "模型只接收完成任务所需的最少上下文。"],
];
const now = () => new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date());

function getSpeechRecognitionConstructor() {
  if (typeof window === "undefined") return undefined;
  const speechWindow = window as typeof window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return <div className="rounded-2xl border border-white/10 bg-white/[0.045] px-4 py-3 shadow-sm"><p className="text-xs uppercase tracking-[0.15em] text-slate-500">{label}</p><p className={`mt-1 text-xl font-semibold tracking-tight ${accent ?? "text-slate-50"}`}>{value}</p></div>;
}

function TraceCard({ trace, index }: { trace: Trace; index: number }) {
  return <details className={`group rounded-xl border ${trace.status === "blocked" ? "border-rose-400/25 bg-rose-500/10" : "border-emerald-400/20 bg-emerald-500/[0.07]"}`}>
    <summary className="flex cursor-pointer list-none items-center gap-3 px-3 py-3 text-sm"><span className="flex h-6 w-6 items-center justify-center rounded-lg bg-white/10 text-xs text-slate-300">{index + 1}</span><span className={`h-2 w-2 rounded-full ${trace.status === "blocked" ? "bg-rose-400" : "bg-emerald-400"}`} /><span className="min-w-0 flex-1 truncate font-medium text-slate-100">{trace.name}</span><span className="text-xs text-slate-500 group-open:rotate-180">⌄</span></summary>
    <div className="space-y-3 border-t border-white/10 p-3 text-xs"><div className="flex flex-wrap gap-2 text-[11px] text-slate-500"><span>{domainLabels[trace.domain || "system"]}</span><span>策略 {trace.policyCode || "—"}</span><span>状态 v{trace.stateVersionBefore ?? "—"} → v{trace.stateVersionAfter ?? "—"}</span></div><div><p className="mb-1 font-medium text-slate-400">工具输入</p><pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950/80 p-2 text-slate-300">{JSON.stringify(trace.input, null, 2)}</pre></div><div><p className="mb-1 font-medium text-slate-400">策略输出</p><pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950/80 p-2 text-slate-300">{JSON.stringify(trace.output, null, 2)}</pre></div></div>
  </details>;
}

function TaskPlanPanel({ plan, traces, stateVersion }: { plan: TaskPlan | null; traces: Trace[]; stateVersion: number }) {
  if (!plan) return <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm leading-6 text-slate-500">下达任务后，这里会显示目标、依赖关系、风险等级、工具白名单和执行结果。</div>;
  return <div className="space-y-3"><div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.06] p-4"><p className="text-xs tracking-[0.14em] text-cyan-300">当前任务计划</p><p className="mt-2 text-sm font-medium leading-6 text-white">{plan.objective}</p><div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400"><span>{plan.nodes.length} 个任务</span><span>{plan.executionWaves.length} 个执行波次</span><span>状态 v{stateVersion}</span>{plan.requiresConfirmation && <span className="text-amber-300">包含需确认动作</span>}</div></div>{plan.nodes.map((node, index) => { const receipts = traces.filter((trace) => trace.taskId === node.id); const blocked = receipts.some((trace) => trace.status === "blocked"); const success = receipts.some((trace) => trace.status === "success"); return <article key={node.id} className={`rounded-2xl border p-3 ${blocked ? "border-rose-400/25 bg-rose-400/[0.06]" : success ? "border-emerald-400/20 bg-emerald-400/[0.05]" : "border-white/[0.07] bg-white/[0.03]"}`}><div className="flex items-start gap-3"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/[0.07] text-xs text-cyan-200">{index + 1}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-cyan-300">{domainLabels[node.domain] || node.domain}</p><span className={`rounded-full px-2 py-1 text-[10px] ${node.risk === "high" ? "bg-rose-400/10 text-rose-300" : node.risk === "medium" ? "bg-amber-400/10 text-amber-300" : "bg-emerald-400/10 text-emerald-300"}`}>{zhCN.risks[node.risk]}</span></div><h3 className="mt-1 text-sm font-medium text-white">{node.title}</h3><p className="mt-1 text-xs leading-5 text-slate-500">依赖：{node.dependencies.length ? node.dependencies.join("、") : "无"} · {success ? "已完成" : blocked ? "已阻止" : "待执行"}</p></div></div></article>; })}</div>;
}

export default function AgentLab() {
  const [vehicle, setVehicle] = useState(initialVehicle);
  const [sessionId, setSessionId] = useState("");
  const [scenario, setScenario] = useState<CabinScenario>("default");
  const [messages, setMessages] = useState<Message[]>([{ role: "assistant", content: "驾驶智能体已就绪。你可以导航到任意可检索地点、组合执行座舱任务，或测试安全拦截。", time: "已就绪" }]);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  const [role, setRole] = useState<OccupantRole>("driver");
  const [stateVersion, setStateVersion] = useState(1);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<Panel>("assistant");
  const [browserLocation, setBrowserLocation] = useState<BrowserLocation | null>(null);
  const [locationBusy, setLocationBusy] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [speechOutputSupported, setSpeechOutputSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceReply, setVoiceReply] = useState(true);
  const [voiceNotice, setVoiceNotice] = useState("点击麦克风后，说出中文任务");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const [meta, setMeta] = useState({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" });
  const hasLiveRoute = vehicle.routeProvider.includes("OSRM") && vehicle.routePolyline.length >= 2;
  const routeFreshness = useMemo(() => {
    if (!vehicle.routeDataFreshness || vehicle.routeDataFreshness === "—") return "尚未算路";
    const date = new Date(vehicle.routeDataFreshness);
    return Number.isNaN(date.getTime()) ? vehicle.routeDataFreshness : date.toLocaleTimeString("zh-CN", { hour12: false });
  }, [vehicle.routeDataFreshness]);

  const createSession = async (nextScenario: CabinScenario, location?: BrowserLocation, nextRole: OccupantRole = role) => {
    const response = await fetch(cabinApiUrl("/api/cabin/session"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: nextScenario, occupantRole: nextRole, ...(location ? { location } : {}) }) });
    const data = await response.json() as { sessionId?: string; vehicle?: VehicleState; stateVersion?: number; occupantRole?: OccupantRole; error?: { message?: string } };
    if (!response.ok || !data.sessionId || !data.vehicle) throw new Error(data.error?.message || "无法创建演示会话");
    setSessionId(data.sessionId); setRole(data.occupantRole ?? nextRole); setStateVersion(data.stateVersion ?? 1);
    window.localStorage.setItem("cabinguard-session-id", data.sessionId); window.localStorage.setItem("cabinguard-occupant-role", data.occupantRole ?? nextRole);
    setVehicle({ ...initialVehicle, ...data.vehicle, windows: { ...initialVehicle.windows, ...data.vehicle.windows }, seats: { ...initialVehicle.seats, ...data.vehicle.seats }, ambientLight: { ...initialVehicle.ambientLight, ...data.vehicle.ambientLight }, defrost: { ...initialVehicle.defrost, ...data.vehicle.defrost } });
  };

  useEffect(() => {
    setVoiceSupported(Boolean(getSpeechRecognitionConstructor())); setSpeechOutputSupported("speechSynthesis" in window);
    void createSession("default").catch((error) => { const message = error instanceof Error ? error.message : "无法创建演示会话"; setMessages((current) => [...current, { role: "assistant", content: `会话初始化失败：${message}`, time: now() }]); });
    return () => { recognitionRef.current?.stop(); window.speechSynthesis?.cancel(); };
  }, []);
  useEffect(() => {
    if (panel !== "assistant" || !chatScrollRef.current) return;
    chatScrollRef.current.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, panel]);

  const speak = (text: string) => {
    if (!voiceReply || !speechOutputSupported) return;
    window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = "zh-CN"; utterance.rate = 0.95; window.speechSynthesis.speak(utterance);
  };
  const toggleVoiceInput = () => {
    if (listening) { recognitionRef.current?.stop(); return; }
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) { setVoiceNotice("当前浏览器不支持语音识别，请使用 Chrome、Edge 或键盘输入"); return; }
    const recognition = new Recognition(); recognition.lang = "zh-CN"; recognition.continuous = false; recognition.interimResults = false; recognition.maxAlternatives = 1;
    recognition.onresult = (event) => { const result = event.results[event.results.length - 1]?.[0]?.transcript?.trim(); if (result) { setInput(result); setVoiceNotice("已识别，请核对后发送"); } };
    recognition.onerror = (event) => setVoiceNotice(event.error === "not-allowed" ? "麦克风权限被拒绝，请在地址栏开启" : `识别失败：${event.error}`);
    recognition.onend = () => { setListening(false); recognitionRef.current = null; }; recognitionRef.current = recognition; setListening(true); setVoiceNotice("正在聆听…");
    try { recognition.start(); } catch { setListening(false); setVoiceNotice("麦克风启动失败，请检查权限"); }
  };
  const useCurrentLocation = () => {
    if (!("geolocation" in navigator)) { setMessages((current) => [...current, { role: "assistant", content: "当前浏览器不支持定位，继续使用模拟起点。", time: now() }]); return; }
    if (!window.isSecureContext) { setMessages((current) => [...current, { role: "assistant", content: "定位要求 HTTPS 或 localhost，当前继续使用模拟起点。", time: now() }]); return; }
    setLocationBusy(true);
    navigator.geolocation.getCurrentPosition((position) => {
      const location: BrowserLocation = { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracyMeters: position.coords.accuracy, allowExternalRouting: true };
      void createSession(scenario, location, role).then(() => { setBrowserLocation(location); setMessages([{ role: "assistant", content: "定位与本次外部道路算路已授权。精确起点只发送给算路服务，不进入大模型工具回执。", time: now() }]); setTraces([]); setTaskPlan(null); setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" }); }).catch((error) => { const message = error instanceof Error ? error.message : "定位写入失败"; setMessages((current) => [...current, { role: "assistant", content: message, time: now() }]); }).finally(() => setLocationBusy(false));
    }, (error) => { const reason = error.code === error.PERMISSION_DENIED ? "定位权限被拒绝" : error.code === error.TIMEOUT ? "定位请求超时" : "无法获取位置"; setMessages((current) => [...current, { role: "assistant", content: `${reason}，继续使用模拟起点。`, time: now() }]); setLocationBusy(false); }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 });
  };

  const submit = async (rawText: string) => {
    const text = rawText.trim(); if (!text || busy || !sessionId) return;
    const history = messages.slice(-8).map(({ role, content }) => ({ role, content })); setMessages((current) => [...current, { role: "user", content: text, time: now() }]); setInput(""); setBusy(true); setPanel("assistant"); const started = performance.now();
    try {
      let response: Response | null = null;
      for (let attempt = 1; attempt <= 2; attempt += 1) { response = await fetch(cabinApiUrl("/api/deepseek/agent"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, sessionId, history }) }); if (response.ok || response.status !== 502 || attempt === 2) break; }
      if (!response) throw new Error("Agent 请求未发出"); const data = (await response.json()) as AgentResponse; if (!response.ok) throw new Error(data.error?.message || "Agent 请求失败");
      setVehicle(data.vehicle); setSessionId(data.sessionId); setRole(data.occupantRole ?? role); setStateVersion(data.stateVersion ?? stateVersion); setTaskPlan(data.plan ?? null); setTraces((current) => [...[...data.traces].reverse(), ...current]); setMessages((current) => [...current, { role: "assistant", content: data.message, time: now() }]); window.localStorage.setItem("cabinguard-session-id", data.sessionId); speak(data.message);
      setMeta({ model: data.model, turns: data.turns, tokens: data.totalTokens, latency: Math.round(performance.now() - started), promptVersion: data.promptVersion, toolVersion: data.toolVersion });
    } catch (error) { const message = error instanceof Error ? error.message : "未知错误"; setMessages((current) => [...current, { role: "assistant", content: `本次执行失败：${message}`, time: now() }]); } finally { setBusy(false); }
  };
  const onSubmit = (event: FormEvent) => { event.preventDefault(); void submit(input); };
  const reset = async () => {
    try { await createSession(scenario, browserLocation ?? undefined, role); setMessages([{ role: "assistant", content: "执行环境已重置，可以重新测试多步规划、澄清与安全拦截。", time: now() }]); setTraces([]); setTaskPlan(null); setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" }); }
    catch (error) { const message = error instanceof Error ? error.message : "无法创建会话"; setMessages((current) => [...current, { role: "assistant", content: `重置失败：${message}`, time: now() }]); }
  };
  const changeScenario = async (nextScenario: CabinScenario) => {
    if (busy || nextScenario === scenario) return; setBusy(true);
    try { await createSession(nextScenario, browserLocation ?? undefined, role); setScenario(nextScenario); setMessages([{ role: "assistant", content: `已切换到${scenarioOptions.find((item) => item.value === nextScenario)?.label}，会话状态和确认链已隔离。`, time: now() }]); setTraces([]); setTaskPlan(null); }
    catch (error) { const message = error instanceof Error ? error.message : "场景切换失败"; setMessages((current) => [...current, { role: "assistant", content: message, time: now() }]); } finally { setBusy(false); }
  };
  const changeRole = async (nextRole: OccupantRole) => {
    if (busy || nextRole === role) return; setBusy(true);
    try { await createSession(scenario, browserLocation ?? undefined, nextRole); setMessages([{ role: "assistant", content: `已切换为${zhCN.roles[nextRole]}身份并创建隔离会话。不同角色拥有不同的座舱控制权限。`, time: now() }]); setTraces([]); setTaskPlan(null); setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" }); }
    catch (error) { const message = error instanceof Error ? error.message : "角色切换失败"; setMessages((current) => [...current, { role: "assistant", content: message, time: now() }]); } finally { setBusy(false); }
  };

  return <main className="min-h-screen bg-[#070b14] text-slate-100">
    <ProductNav active="/" status={<span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${usesExternalCabinApi ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300" : "border-amber-400/25 bg-amber-400/10 text-amber-300"}`}>{usesExternalCabinApi ? "Python 核心在线" : "Python 核心未连接"}</span>} actions={<button className="whitespace-nowrap rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300 hover:bg-white/10" onClick={() => void reset()}>重置会话</button>} />

    <section className="mx-auto grid max-w-[1720px] gap-5 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_430px] xl:px-8"><div className="min-w-0 space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6"><Metric label="车速 / 挡位" value={`${vehicle.speed} km/h · ${vehicle.gear}`} accent="text-cyan-300" /><Metric label="动力电池" value={`${vehicle.battery}%`} accent={vehicle.battery < 20 ? "text-amber-300" : "text-emerald-300"} /><Metric label="预计续航" value={`${vehicle.range} km`} /><Metric label="车内温度" value={`${vehicle.cabinTemperature}℃`} /><Metric label="空调设定" value={`${vehicle.targetTemperature}℃ · ${vehicle.fanLevel}档`} /><Metric label="天气" value={`${vehicle.weather} · ${vehicle.rainProbability}%`} /></div>

      <section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">座舱域实时状态</h2><p className="mt-1 text-sm text-slate-500">由 Python 车辆沙箱回执驱动 · 可通过自然语言组合控制</p></div><span className="rounded-full border border-violet-400/20 bg-violet-400/[0.07] px-3 py-1 text-xs text-violet-300">VSS-aligned</span></div><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{[
        ["车窗", `主 ${vehicle.windows.driver}% · 副 ${vehicle.windows.passenger}% · 后 ${vehicle.windows.rearLeft}%/${vehicle.windows.rearRight}%`],
        ["座椅加热", `主 ${vehicle.seats.driverHeating}挡 · 副 ${vehicle.seats.passengerHeating}挡`],
        ["座椅通风", `主 ${vehicle.seats.driverVentilation}挡 · 副 ${vehicle.seats.passengerVentilation}挡`],
        ["氛围灯", vehicle.ambientLight.enabled ? `${vehicle.ambientLight.color} · ${vehicle.ambientLight.brightness}%` : "关闭"],
        ["前/后除霜", `${vehicle.defrost.front ? "ON" : "OFF"} / ${vehicle.defrost.rear ? "ON" : "OFF"}`],
        ["车身安全", `儿童锁 ${vehicle.childLock ? "ON" : "OFF"} · 尾门 ${vehicle.trunkOpen ? "开" : "关"}`],
      ].map(([label, value]) => <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-sm font-medium text-slate-200">{value}</p></div>)}</div></section>

      <section className="overflow-hidden rounded-3xl border border-white/10 bg-[#0b1220] shadow-2xl shadow-black/20"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4"><div><div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${hasLiveRoute ? "animate-pulse bg-emerald-400" : "bg-slate-600"}`} /><h2 className="font-semibold">实时道路导航</h2><span className="text-xs text-slate-500">{vehicle.routeProvider}</span></div><p className="mt-1 text-sm text-slate-400">{vehicle.destination === "未设置" ? "说出任意地址或地点，Agent 将检索并规划可驾驶路线" : `${vehicle.currentLocation} → ${vehicle.destination}`}</p></div><div className="flex flex-wrap items-center gap-2"><label className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-400"><span>乘员身份</span><select aria-label="乘员身份" value={role} disabled={busy} onChange={(event) => void changeRole(event.target.value as OccupantRole)} className="bg-transparent font-medium text-cyan-200 outline-none">{(Object.entries(zhCN.roles) as Array<[OccupantRole, string]>).map(([value, label]) => <option key={value} value={value} className="bg-slate-900 text-white">{label}</option>)}</select></label><div className="flex rounded-xl border border-white/10 bg-black/20 p-1">{scenarioOptions.map((option) => <button key={option.value} disabled={busy} title={option.hint} onClick={() => void changeScenario(option.value)} className={`rounded-lg px-3 py-2 text-xs transition ${scenario === option.value ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-200"}`}>{option.label}</button>)}</div><button type="button" disabled={busy || locationBusy} onClick={useCurrentLocation} className="rounded-xl bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 hover:bg-blue-400 disabled:opacity-50">{locationBusy ? "正在定位…" : vehicle.locationSource === "browser_geolocation" ? "已使用当前位置" : "使用我的当前位置"}</button></div></div>
        <div className="relative h-[480px]"><LiveRouteMap latitude={vehicle.latitude} longitude={vehicle.longitude} destinationLatitude={vehicle.destinationLatitude} destinationLongitude={vehicle.destinationLongitude} destination={vehicle.destination} routePolyline={vehicle.routePolyline} />
          <div className="absolute left-4 top-4 z-[500] max-w-[320px] rounded-2xl border border-white/10 bg-slate-950/85 p-4 shadow-xl backdrop-blur-xl"><div className="flex items-center justify-between gap-4"><p className="text-xs tracking-[0.16em] text-slate-500">路线智能</p><span className={`rounded-full px-2 py-1 text-[11px] ${hasLiveRoute ? "bg-emerald-400/15 text-emerald-300" : "bg-white/10 text-slate-400"}`}>{hasLiveRoute ? "实时路线" : "等待路线"}</span></div><p className="mt-2 truncate text-base font-semibold text-white">{vehicle.destination}</p><div className="mt-3 grid grid-cols-3 gap-4"><div><p className="text-xs text-slate-500">距离</p><p className="mt-1 font-semibold">{vehicle.routeDistanceKm === null ? "—" : `${vehicle.routeDistanceKm} 公里`}</p></div><div><p className="text-xs text-slate-500">用时</p><p className="mt-1 font-semibold">{vehicle.routeEtaMinutes === null ? "—" : `${vehicle.routeEtaMinutes} 分钟`}</p></div><div><p className="text-xs text-slate-500">到达电量</p><p className={`mt-1 font-semibold ${vehicle.estimatedArrivalBattery !== null && vehicle.estimatedArrivalBattery < 10 ? "text-amber-300" : "text-emerald-300"}`}>{vehicle.estimatedArrivalBattery === null ? "—" : `${vehicle.estimatedArrivalBattery}%`}</p></div></div>{vehicle.navigationUrl && <a href={vehicle.navigationUrl} target="_blank" rel="noreferrer" className="mt-4 block rounded-xl bg-white/10 px-3 py-2 text-center text-sm font-medium text-cyan-300 hover:bg-white/15">在 OpenStreetMap 查看完整路线 ↗</a>}</div>
          <div className="absolute bottom-4 left-4 z-[500] rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-xs text-slate-300 backdrop-blur">{vehicle.locationSource === "browser_geolocation" ? `浏览器定位 ±${Math.round(vehicle.locationAccuracyMeters ?? 0)} m` : "模拟起点"} · 路线更新 {routeFreshness}</div>
        </div><div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 px-5 py-3 text-xs text-slate-500"><p>地图 © OpenStreetMap contributors · 路线 OSRM · 无实时路况与车道级引导</p><p>{vehicle.locationSource === "browser_geolocation" ? "坐标仅在授权后发送给算路服务，不进入模型回执" : "可使用模拟位置体验，无需提供个人坐标"}</p></div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]"><section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">路线决策</h2><p className="mt-1 text-sm text-slate-500">步骤、备选路线与能耗预测</p></div><span className="rounded-full bg-white/5 px-3 py-1 text-xs text-slate-400">{vehicle.routeSteps.length} 步</span></div><div className="mt-4 grid gap-4 md:grid-cols-2"><div className="space-y-2">{(vehicle.routeSteps.length ? vehicle.routeSteps : ["等待 Agent 完成目的地检索与道路算路"]).map((step, index) => <div key={`${step}-${index}`} className="flex gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-3 text-sm text-slate-300"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-blue-500/15 text-xs font-semibold text-blue-300">{index + 1}</span><p className="leading-6">{step}</p></div>)}</div><div className="space-y-2"><p className="mb-2 text-xs tracking-[0.14em] text-slate-500">备选路线</p>{(vehicle.routeAlternatives.length ? vehicle.routeAlternatives : [{ label: "等待路线", distanceKm: 0, etaMinutes: 0 }]).map((route, index) => <div key={`${route.label}-${index}`} className={`rounded-xl border p-3 ${index === 0 && hasLiveRoute ? "border-cyan-400/25 bg-cyan-400/[0.07]" : "border-white/[0.07] bg-white/[0.03]"}`}><div className="flex items-center justify-between gap-3"><p className="text-sm font-medium text-slate-200">{route.label}</p>{index === 0 && hasLiveRoute && <span className="text-xs text-cyan-300">当前</span>}</div><p className="mt-2 text-sm text-slate-500">{route.distanceKm ? `${route.distanceKm} km · ${route.etaMinutes} 分钟` : "完成算路后显示"}</p></div>)}</div></div></section>
        <section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">Agent 运行态</h2><p className="mt-1 text-sm text-slate-500">规划质量与系统可观测性</p></div><span className={`h-2.5 w-2.5 rounded-full ${sessionId ? "bg-emerald-400" : "animate-pulse bg-amber-400"}`} /></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm">{[["模型", meta.model], ["工具调用", `${traces.length}`], ["规划轮次", `${meta.turns}`], ["端到端延迟", meta.latency ? `${meta.latency} ms` : "—"], ["车辆状态版本", `v${stateVersion}`], ["当前身份", zhCN.roles[role]]].map(([label, value]) => <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 truncate font-medium text-slate-200">{value}</dd></div>)}</dl><div className="mt-4 rounded-xl border border-blue-400/15 bg-blue-400/[0.06] p-3 text-sm leading-6 text-blue-200"><span className="font-medium">执行链：</span>意图识别 → 任务图编排 → 权限与策略裁决 → 确定性工具 → 状态版本更新 → 证据回执</div></section>
      </div>
    </div>

    <aside className="min-w-0 xl:sticky xl:top-[94px] xl:h-[calc(100vh-114px)]"><section className="flex h-[760px] max-h-[calc(100vh-114px)] min-h-[640px] flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#0b1220] shadow-2xl shadow-black/30"><div className="border-b border-white/10 px-4 pt-4"><div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="font-semibold">座舱主智能体</h2><p className="mt-0.5 text-xs text-slate-500">统一交互 · 多领域编排 · 策略核执行</p></div><button type="button" disabled={!speechOutputSupported} aria-pressed={voiceReply} onClick={() => { window.speechSynthesis?.cancel(); setVoiceReply((current) => !current); }} className={`rounded-lg border px-2.5 py-1.5 text-xs ${voiceReply ? "border-cyan-400/25 bg-cyan-400/10 text-cyan-300" : "border-white/10 text-slate-500"}`}>语音播报 {voiceReply ? "开" : "关"}</button></div><div className="grid grid-cols-4 gap-1 rounded-xl bg-black/20 p-1">{([["assistant", "对话"], ["plan", `任务 ${taskPlan?.nodes.length ?? 0}`], ["trace", `记录 ${traces.length}`], ["policy", "安全"]] as Array<[Panel, string]>).map(([value, label]) => <button key={value} onClick={() => setPanel(value)} className={`rounded-lg px-2 py-2 text-sm font-medium ${panel === value ? "bg-white/10 text-white shadow" : "text-slate-500 hover:text-slate-200"}`}>{label}</button>)}</div></div>
      {panel === "assistant" && <><div ref={chatScrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">{messages.map((message, index) => <div key={`${message.time}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-br-md bg-blue-500 text-white" : "rounded-bl-md border border-white/[0.06] bg-white/[0.05] text-slate-200"}`}><p>{message.content}</p><p className={`mt-1 text-[11px] ${message.role === "user" ? "text-blue-100" : "text-slate-600"}`}>{message.time}</p></div></div>)}{busy && <div className="w-fit rounded-2xl rounded-bl-md border border-cyan-400/15 bg-cyan-400/[0.07] px-4 py-3 text-sm text-cyan-200"><span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-300" />正在规划并执行工具链…</div>}</div><div className="border-t border-white/10 p-4"><div className="mb-3 flex gap-2 overflow-x-auto pb-1">{prompts.map((prompt) => <button key={prompt} disabled={busy || !sessionId} onClick={() => void submit(prompt)} className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-400 hover:border-cyan-400/30 hover:text-cyan-200 disabled:opacity-40">{prompt}</button>)}</div><p className={`mb-2 text-xs ${listening ? "text-rose-300" : "text-slate-600"}`}>{voiceSupported ? voiceNotice : "当前浏览器不支持语音识别，键盘输入可用"}</p><form className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/20 p-2 focus-within:border-blue-400/40" onSubmit={onSubmit}><button type="button" disabled={busy || !voiceSupported} aria-label={listening ? "停止语音输入" : "开始中文语音输入"} onClick={toggleVoiceInput} className={`h-10 rounded-xl px-3 text-sm font-medium ${listening ? "bg-rose-500/20 text-rose-300" : "bg-white/5 text-slate-300"}`}>{listening ? "停止" : "语音"}</button><input value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} placeholder="例如：导航到昌平区政府" className="min-w-0 flex-1 bg-transparent px-2 py-2 text-sm text-white outline-none placeholder:text-slate-600" /><button disabled={busy || !sessionId || !input.trim()} className="h-10 rounded-xl bg-blue-500 px-4 text-sm font-semibold text-white hover:bg-blue-400 disabled:opacity-30">发送</button></form></div></>}
      {panel === "plan" && <div className="flex-1 overflow-y-auto p-4"><TaskPlanPanel plan={taskPlan} traces={traces} stateVersion={stateVersion} /></div>}
      {panel === "trace" && <div className="flex-1 space-y-3 overflow-y-auto p-4">{!traces.length && <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm leading-6 text-slate-500">执行任务后，这里会展示模型选择的工具、严格参数、策略结果和执行回执。</div>}{traces.map((trace, index) => <TraceCard key={`${trace.id}-${index}`} trace={trace} index={index} />)}</div>}
      {panel === "policy" && <div className="flex-1 space-y-3 overflow-y-auto p-4"><div className="rounded-2xl border border-cyan-400/15 bg-cyan-400/[0.06] p-4 text-sm leading-6 text-cyan-100">当前演示身份：<strong>{zhCN.roles[role]}</strong>。模型负责规划，确定性策略层掌握最终执行权；页面角色用于演示 ABAC，不等同于生产环境可信身份认证。</div>{policies.map(([title, description], index) => <div key={title} className="flex gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-400/10 text-xs font-semibold text-emerald-300">P{index + 1}</span><div><p className="text-sm font-medium text-slate-200">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{description}</p></div></div>)}</div>}
    </section></aside></section>
  </main>;
}
