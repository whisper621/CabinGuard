"use client";

import { FormEvent, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Image from "next/image";
import ProductNav from "../components/ProductNav";
import { cabinApiUrl, usesExternalCabinApi } from "../lib/apiBase";
import { domainLabels, v6WebSocketUrl, type AgentTraceV6, type TaskPlan } from "../lib/cabinV6";
import { readConversationArchive, upsertConversation, type ConversationRecord } from "../lib/conversationArchive";
import { zhCN, type OccupantRole } from "../lib/i18n/zh-CN";
import { appendSpeechSegment } from "../lib/utterance";
import LiveRouteMap from "./LiveRouteMap";

type GeoPoint = { latitude: number; longitude: number };
type RouteAlternative = { label: string; distanceKm: number; etaMinutes: number };
type MediaTrack = { id: string; title: string; artist: string; album: string; artworkUrl: string; previewUrl: string; durationSeconds: number };
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
  defrost: { front: boolean; rear: boolean };
  doors: { driver: boolean; passenger: boolean; rearLeft: boolean; rearRight: boolean };
  mirrors: { driverFolded: boolean; passengerFolded: boolean; driverHeating: boolean; passengerHeating: boolean };
  wiperMode: "off" | "auto" | "slow" | "medium" | "high";
  airQuality: { pm25: number; purifierEnabled: boolean; purifierLevel: number; fragrance: "off" | "forest" | "ocean" | "citrus" };
  childLock: boolean; trunkOpen: boolean; chargePortOpen: boolean;
  media: { source: "none" | "music" | "radio" | "podcast"; playing: boolean; volume: number; currentIndex: number; current: MediaTrack | null; queue: MediaTrack[] };
};
type CabinScenario = "default" | "rain" | "moving" | "highway" | "low_battery" | "child" | "pickup" | "rest" | "air_quality";
type BrowserLocation = { latitude: number; longitude: number; accuracyMeters?: number; allowExternalRouting?: boolean };
type Panel = "assistant" | "plan" | "trace" | "policy" | "history";
type MapDrawer = "scenes" | "vehicle" | "route" | null;
type SpeechRecognitionLike = {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number;
  start: () => void; stop: () => void;
  onresult: ((event: { results: { length: number; [index: number]: { isFinal?: boolean; [index: number]: { transcript: string } } } }) => void) | null;
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
type SessionResponse = {
  sessionId?: string; scenario?: CabinScenario; vehicle?: VehicleState; stateVersion?: number;
  occupantRole?: OccupantRole; error?: { message?: string };
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
  defrost: { front: false, rear: false },
  doors: { driver: false, passenger: false, rearLeft: false, rearRight: false },
  mirrors: { driverFolded: false, passengerFolded: false, driverHeating: false, passengerHeating: false },
  wiperMode: "off", airQuality: { pm25: 18, purifierEnabled: false, purifierLevel: 0, fragrance: "off" },
  childLock: false, trunkOpen: false, chargePortOpen: false,
  media: { source: "none", playing: false, volume: 35, currentIndex: 0, current: null, queue: [] },
};
const prompts = ["导航到昌平区政府，同时把空调调到23度", "嗯，打开自动雨刷和后视镜加热，再播放轻音乐", "把四个车窗都打开20%，开启2挡空气净化", "打开右后车门", "你现在支持哪些能力？"];
const scenarioOptions: Array<{ value: CabinScenario; label: string; hint: string; description: string; prompt: string }> = [
  { value: "default", label: "智能通勤", hint: "跨域协同", description: "导航、舒适与媒体并行编排", prompt: "导航到昌平区政府，同时把空调调到23度，再播放轻音乐" },
  { value: "rain", label: "雨雾安全", hint: "降雨 70%", description: "雨刷、除霜与后视镜联动", prompt: "嗯，打开自动雨刷、前后除霜和后视镜加热" },
  { value: "highway", label: "高速巡航", hint: "110 km/h", description: "高速条件下验证安全拦截", prompt: "打开天窗一半，再把主驾车窗打开20%" },
  { value: "low_battery", label: "低电补能", hint: "电量 12%", description: "沿途补能检索与能耗预测", prompt: "帮我找沿途绕行最少的充电站并导航过去" },
  { value: "child", label: "儿童乘车", hint: "儿童锁开启", description: "后排权限与危险动作隔离", prompt: "打开右后车门并把右后车窗降到一半" },
  { value: "pickup", label: "临时上下客", hint: "P 挡驻车", description: "车门一次性确认与状态回执", prompt: "打开右后车门" },
  { value: "rest", label: "停车休息", hint: "舒适座舱", description: "座椅、温度、香氛和音乐联动", prompt: "开启主驾座椅通风2挡，空调调到22度，打开森林香氛并播放轻音乐" },
  { value: "air_quality", label: "空气守护", hint: "PM2.5 168", description: "空气异常感知与净化执行", prompt: "车里空气不好，打开3挡净化器并切换森林香氛" },
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
const CONVERSATION_STORAGE_KEY = "cabinguard-conversations-v1";
const welcomeMessages: Message[] = [{ role: "assistant", content: "驾驶智能体已就绪。你可以导航到任意可检索地点、组合执行座舱任务，或测试安全拦截。", time: "已就绪" }];

function mergeVehicle(vehicle: VehicleState): VehicleState {
  return { ...initialVehicle, ...vehicle, windows: { ...initialVehicle.windows, ...vehicle.windows }, seats: { ...initialVehicle.seats, ...vehicle.seats }, ambientLight: { ...initialVehicle.ambientLight, ...vehicle.ambientLight }, defrost: { ...initialVehicle.defrost, ...vehicle.defrost }, doors: { ...initialVehicle.doors, ...vehicle.doors }, mirrors: { ...initialVehicle.mirrors, ...vehicle.mirrors }, airQuality: { ...initialVehicle.airQuality, ...vehicle.airQuality }, media: { ...initialVehicle.media, ...vehicle.media, queue: vehicle.media?.queue ?? [] } };
}

function getSpeechRecognitionConstructor() {
  if (typeof window === "undefined") return undefined;
  const speechWindow = window as typeof window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
}

function StatusItem({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return <div className="min-w-[112px] flex-1 border-r border-white/[0.07] px-3 last:border-r-0"><p className="text-[10px] tracking-[0.12em] text-slate-500">{label}</p><p className={`mt-1 truncate text-sm font-semibold ${accent ?? "text-slate-100"}`}>{value}</p></div>;
}

function DockButton({ active, label, value, onClick }: { active?: boolean; label: string; value: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`min-w-[68px] rounded-2xl px-3 py-2 text-center transition ${active ? "bg-cyan-400/15 text-cyan-200" : "text-slate-300 hover:bg-white/10"}`}><span className="block text-sm font-semibold">{value}</span><span className="mt-0.5 block text-[10px] text-slate-500">{label}</span></button>;
}

function DrawerShell({ title, subtitle, onClose, children }: { title: string; subtitle: string; onClose: () => void; children: ReactNode }) {
  return <section className="absolute inset-y-4 right-4 z-[700] flex w-[min(430px,calc(100%-32px))] flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#09111f]/95 shadow-2xl shadow-black/60 backdrop-blur-2xl"><header className="flex items-start justify-between gap-4 border-b border-white/10 p-5"><div><h3 className="font-semibold text-white">{title}</h3><p className="mt-1 text-xs text-slate-500">{subtitle}</p></div><button type="button" aria-label="关闭抽屉" onClick={onClose} className="grid h-8 w-8 place-items-center rounded-full bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white">×</button></header><div className="flex-1 overflow-y-auto p-4">{children}</div></section>;
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
  const [messages, setMessages] = useState<Message[]>(welcomeMessages);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  const [role, setRole] = useState<OccupantRole>("driver");
  const [stateVersion, setStateVersion] = useState(1);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<Panel>("assistant");
  const [mapDrawer, setMapDrawer] = useState<MapDrawer>(null);
  const [browserLocation, setBrowserLocation] = useState<BrowserLocation | null>(null);
  const [locationBusy, setLocationBusy] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [speechOutputSupported, setSpeechOutputSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceReply, setVoiceReply] = useState(true);
  const [voiceNotice, setVoiceNotice] = useState("点击麦克风后，说出中文任务");
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [archiveReady, setArchiveReady] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const voicePrefixRef = useRef("");
  const latestInputRef = useRef("");
  const keepListeningRef = useRef(false);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [meta, setMeta] = useState({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" });
  const hasLiveRoute = vehicle.routeProvider.includes("OSRM") && vehicle.routePolyline.length >= 2;
  const routeFreshness = useMemo(() => {
    if (!vehicle.routeDataFreshness || vehicle.routeDataFreshness === "—") return "尚未算路";
    const date = new Date(vehicle.routeDataFreshness);
    return Number.isNaN(date.getTime()) ? vehicle.routeDataFreshness : date.toLocaleTimeString("zh-CN", { hour12: false });
  }, [vehicle.routeDataFreshness]);

  const createSession = async (nextScenario: CabinScenario, location?: BrowserLocation, nextRole: OccupantRole = role) => {
    const response = await fetch(cabinApiUrl("/api/cabin/session"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: nextScenario, occupantRole: nextRole, ...(location ? { location } : {}) }) });
    const data = await response.json() as SessionResponse;
    if (!response.ok || !data.sessionId || !data.vehicle) throw new Error(data.error?.message || "无法创建演示会话");
    setSessionId(data.sessionId); setScenario(data.scenario ?? nextScenario); setRole(data.occupantRole ?? nextRole); setStateVersion(data.stateVersion ?? 1);
    window.localStorage.setItem("cabinguard-session-id", data.sessionId); window.localStorage.setItem("cabinguard-occupant-role", data.occupantRole ?? nextRole);
    setVehicle(mergeVehicle(data.vehicle));
    return data.sessionId;
  };

  useEffect(() => {
    setVoiceSupported(Boolean(getSpeechRecognitionConstructor())); setSpeechOutputSupported("speechSynthesis" in window);
    const storedConversations = readConversationArchive(window.localStorage.getItem(CONVERSATION_STORAGE_KEY));
    setConversations(storedConversations); setArchiveReady(true);
    const storedSessionId = window.localStorage.getItem("cabinguard-session-id");
    const storedRole = window.localStorage.getItem("cabinguard-occupant-role") as OccupantRole | null;
    void (async () => {
      if (storedSessionId) {
        const response = await fetch(cabinApiUrl(`/api/cabin/session/${storedSessionId}`));
        const data = await response.json() as SessionResponse;
        if (response.ok && data.sessionId && data.vehicle) {
          setSessionId(data.sessionId); setScenario(data.scenario ?? "default"); setRole(data.occupantRole ?? "driver"); setStateVersion(data.stateVersion ?? 1); setVehicle(mergeVehicle(data.vehicle));
          const archived = storedConversations.find((record) => record.sessionId === data.sessionId);
          if (archived?.messages.length) setMessages(archived.messages);
          return;
        }
      }
      await createSession("default", undefined, storedRole && Object.hasOwn(zhCN.roles, storedRole) ? storedRole : "driver");
    })().catch((error) => { const message = error instanceof Error ? error.message : "无法创建演示会话"; setMessages((current) => [...current, { role: "assistant", content: `会话初始化失败：${message}`, time: now() }]); });
    return () => { keepListeningRef.current = false; recognitionRef.current?.stop(); window.speechSynthesis?.cancel(); };
  }, []);
  useEffect(() => { latestInputRef.current = input; }, [input]);
  useEffect(() => {
    if (!archiveReady || !sessionId || !messages.length) return;
    const firstUserMessage = messages.find((message) => message.role === "user")?.content;
    const record: ConversationRecord = { sessionId, title: (firstUserMessage || "新对话").slice(0, 28), messages, scenario, occupantRole: role, updatedAt: new Date().toISOString() };
    setConversations((current) => upsertConversation(current, record));
  }, [archiveReady, messages, role, scenario, sessionId]);
  useEffect(() => {
    if (archiveReady) window.localStorage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(conversations));
  }, [archiveReady, conversations]);
  useEffect(() => {
    if (!sessionId) return;
    const socket = new WebSocket(v6WebSocketUrl(sessionId));
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { type?: string; vehicle?: VehicleState; stateVersion?: number };
        if (payload.type === "vehicle.state" && payload.vehicle) { setVehicle(mergeVehicle(payload.vehicle)); setStateVersion(payload.stateVersion ?? 1); }
      } catch { /* Ignore malformed telemetry frames; REST remains authoritative. */ }
    };
    return () => socket.close();
  }, [sessionId]);
  useEffect(() => {
    if (panel !== "assistant" || !chatScrollRef.current) return;
    chatScrollRef.current.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, panel]);
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !vehicle.media.current?.previewUrl) return;
    audio.volume = vehicle.media.volume / 100;
    if (vehicle.media.playing) void audio.play().catch(() => undefined);
    else audio.pause();
  }, [vehicle.media.current?.previewUrl, vehicle.media.playing, vehicle.media.volume]);

  const speak = (text: string) => {
    if (!voiceReply || !speechOutputSupported) return;
    window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = "zh-CN"; utterance.rate = 0.95; window.speechSynthesis.speak(utterance);
  };
  const toggleVoiceInput = () => {
    if (listening) { keepListeningRef.current = false; recognitionRef.current?.stop(); setVoiceNotice("已停止聆听，请核对后发送"); return; }
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) { setVoiceNotice("当前浏览器不支持语音识别，请使用 Chrome、Edge 或键盘输入"); return; }
    const recognition = new Recognition(); recognition.lang = "zh-CN"; recognition.continuous = true; recognition.interimResults = true; recognition.maxAlternatives = 1; voicePrefixRef.current = input; keepListeningRef.current = true;
    recognition.onresult = (event) => { const segments: string[] = []; for (let index = 0; index < event.results.length; index += 1) { const segment = event.results[index]?.[0]?.transcript?.trim(); if (segment) segments.push(segment); } const result = segments.join("，"); if (result) { const combined = appendSpeechSegment(voicePrefixRef.current, result); latestInputRef.current = combined; setInput(combined); setVoiceNotice("持续聆听中；说完后请点击“停止”再发送"); } };
    recognition.onerror = (event) => { if (event.error === "aborted" && !keepListeningRef.current) return; if (event.error === "not-allowed" || event.error === "service-not-allowed") keepListeningRef.current = false; setVoiceNotice(event.error === "not-allowed" ? "麦克风权限被拒绝，请在地址栏开启" : event.error === "no-speech" ? "没有听到声音，正在继续聆听…" : `识别出现问题：${event.error}`); };
    recognition.onend = () => { if (keepListeningRef.current) { voicePrefixRef.current = latestInputRef.current; setVoiceNotice("检测到停顿，正在自动继续聆听…"); window.setTimeout(() => { if (!keepListeningRef.current) return; try { recognition.start(); } catch { keepListeningRef.current = false; setListening(false); setVoiceNotice("无法继续聆听，请再次点击语音"); } }, 150); return; } setListening(false); recognitionRef.current = null; };
    recognitionRef.current = recognition; setListening(true); setVoiceNotice("持续聆听已开启；说完后点击“停止”");
    try { recognition.start(); } catch { keepListeningRef.current = false; setListening(false); setVoiceNotice("麦克风启动失败，请检查权限"); }
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
  const startNewConversation = async () => {
    try { await createSession(scenario, browserLocation ?? undefined, role); setMessages([{ role: "assistant", content: "已新建对话。上一段对话保留在“历史”中，可以继续测试多步规划、补参澄清与安全拦截。", time: now() }]); setTraces([]); setTaskPlan(null); setPanel("assistant"); setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" }); }
    catch (error) { const message = error instanceof Error ? error.message : "无法创建会话"; setMessages((current) => [...current, { role: "assistant", content: `新建对话失败：${message}`, time: now() }]); }
  };
  const changeScenario = async (nextScenario: CabinScenario) => {
    if (busy || nextScenario === scenario) return; setBusy(true);
    try { const option = scenarioOptions.find((item) => item.value === nextScenario); await createSession(nextScenario, browserLocation ?? undefined, role); setScenario(nextScenario); setMessages([{ role: "assistant", content: `已切换到${option?.label}。场景状态和确认链已隔离，推荐任务已放入输入框，可直接发送体验。`, time: now() }]); setInput(option?.prompt ?? ""); setTraces([]); setTaskPlan(null); setMapDrawer(null); }
    catch (error) { const message = error instanceof Error ? error.message : "场景切换失败"; setMessages((current) => [...current, { role: "assistant", content: message, time: now() }]); } finally { setBusy(false); }
  };
  const changeRole = async (nextRole: OccupantRole) => {
    if (busy || nextRole === role) return; setBusy(true);
    try { await createSession(scenario, browserLocation ?? undefined, nextRole); setMessages([{ role: "assistant", content: `已切换为${zhCN.roles[nextRole]}身份并创建隔离会话。不同角色拥有不同的座舱控制权限。`, time: now() }]); setTraces([]); setTaskPlan(null); setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" }); }
    catch (error) { const message = error instanceof Error ? error.message : "角色切换失败"; setMessages((current) => [...current, { role: "assistant", content: message, time: now() }]); } finally { setBusy(false); }
  };

  return <main className="min-h-screen bg-[#070b14] text-slate-100">
    <ProductNav active="/" status={<span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${usesExternalCabinApi ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300" : "border-amber-400/25 bg-amber-400/10 text-amber-300"}`}>{usesExternalCabinApi ? "Python 核心在线" : "Python 核心未连接"}</span>} actions={<button className="whitespace-nowrap rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300 hover:bg-white/10" onClick={() => void startNewConversation()}>新建对话</button>} />

    <section className="mx-auto grid max-w-[1840px] gap-4 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_430px] xl:px-6"><div className="min-w-0 space-y-3">
      <section aria-label="车辆关键状态" className="flex min-h-[58px] overflow-x-auto rounded-2xl border border-white/[0.08] bg-[#0b1220]/95 py-3 shadow-lg shadow-black/10">
        <StatusItem label="车速 / 挡位" value={vehicle.speed + " km/h · " + vehicle.gear} accent="text-cyan-300" />
        <StatusItem label="动力电池" value={vehicle.battery + "% · " + vehicle.range + " km"} accent={vehicle.battery < 20 ? "text-amber-300" : "text-emerald-300"} />
        <StatusItem label="座舱温度" value={vehicle.cabinTemperature + "℃ → " + vehicle.targetTemperature + "℃"} />
        <StatusItem label="天气" value={vehicle.weather + " · 降雨 " + vehicle.rainProbability + "%"} />
        <StatusItem label="空气质量" value={"PM2.5 " + vehicle.airQuality.pm25 + " · " + (vehicle.airQuality.purifierEnabled ? "净化 " + vehicle.airQuality.purifierLevel + "挡" : "净化关闭")} accent={vehicle.airQuality.pm25 > 75 ? "text-amber-300" : "text-emerald-300"} />
        <StatusItem label="主动安全" value={(vehicle.childLock ? "儿童锁 ON" : "儿童锁 OFF") + " · 雨刷 " + vehicle.wiperMode} />
      </section>

      <section className="overflow-hidden rounded-3xl border border-white/10 bg-[#0b1220] shadow-2xl shadow-black/30">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-3">
          <div className="min-w-0"><div className="flex items-center gap-2"><span className={"h-2.5 w-2.5 rounded-full " + (hasLiveRoute ? "animate-pulse bg-emerald-400" : "bg-slate-600")} /><h1 className="font-semibold">智能座舱 · 地图工作台</h1><span className="rounded-full border border-violet-400/15 bg-violet-400/[0.06] px-2 py-1 text-[10px] text-violet-300">VSS-aligned</span></div><p className="mt-1 truncate text-xs text-slate-500">{vehicle.currentLocation} · {vehicle.locationSource === "browser_geolocation" ? "真实定位" : "沙箱坐标"}</p></div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-400"><span>身份</span><select aria-label="乘员身份" value={role} disabled={busy} onChange={(event) => void changeRole(event.target.value as OccupantRole)} className="bg-transparent font-medium text-cyan-200 outline-none">{(Object.entries(zhCN.roles) as Array<[OccupantRole, string]>).map(([value, label]) => <option key={value} value={value} className="bg-slate-900 text-white">{label}</option>)}</select></label>
            <button type="button" disabled={busy || locationBusy} onClick={useCurrentLocation} className="rounded-xl bg-blue-500 px-3.5 py-2 text-xs font-semibold text-white shadow-lg shadow-blue-500/20 hover:bg-blue-400 disabled:opacity-50">{locationBusy ? "正在定位…" : vehicle.locationSource === "browser_geolocation" ? "定位已授权" : "使用当前位置"}</button>
          </div>
        </header>

        <div className="relative h-[clamp(640px,calc(100vh-218px),880px)] min-h-[640px]">
          <LiveRouteMap latitude={vehicle.latitude} longitude={vehicle.longitude} destinationLatitude={vehicle.destinationLatitude} destinationLongitude={vehicle.destinationLongitude} destination={vehicle.destination} routePolyline={vehicle.routePolyline} />

          <section className="absolute left-4 top-4 z-[500] w-[min(330px,calc(100%-32px))] rounded-2xl border border-white/10 bg-slate-950/[0.88] p-4 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center justify-between gap-3"><p className="text-[10px] tracking-[0.16em] text-slate-500">ROUTE INTELLIGENCE</p><span className={"rounded-full px-2 py-1 text-[10px] " + (hasLiveRoute ? "bg-emerald-400/15 text-emerald-300" : "bg-white/10 text-slate-400")}>{hasLiveRoute ? "联网道路路线" : "等待目的地"}</span></div>
            <p className="mt-2 truncate text-base font-semibold text-white">{vehicle.destination}</p>
            <div className="mt-3 grid grid-cols-3 gap-3 text-sm"><div><p className="text-[10px] text-slate-500">距离</p><p className="mt-1 font-semibold">{vehicle.routeDistanceKm === null ? "—" : vehicle.routeDistanceKm + " km"}</p></div><div><p className="text-[10px] text-slate-500">用时</p><p className="mt-1 font-semibold">{vehicle.routeEtaMinutes === null ? "—" : vehicle.routeEtaMinutes + " 分"}</p></div><div><p className="text-[10px] text-slate-500">到达电量</p><p className={"mt-1 font-semibold " + (vehicle.estimatedArrivalBattery !== null && vehicle.estimatedArrivalBattery < 10 ? "text-amber-300" : "text-emerald-300")}>{vehicle.estimatedArrivalBattery === null ? "—" : vehicle.estimatedArrivalBattery + "%"}</p></div></div>
            {vehicle.navigationUrl && <a href={vehicle.navigationUrl} target="_blank" rel="noreferrer" className="mt-3 block rounded-xl bg-white/10 px-3 py-2 text-center text-xs font-medium text-cyan-300 hover:bg-white/15">在 OpenStreetMap 核对 ↗</a>}
          </section>

          <div className="absolute right-4 top-4 z-[500] hidden max-w-[280px] rounded-2xl border border-white/10 bg-slate-950/[0.82] p-3 backdrop-blur-xl md:block"><p className="text-[10px] tracking-[0.14em] text-slate-500">CONTEXT AWARENESS</p><div className="mt-2 flex flex-wrap gap-1.5 text-[10px]"><span className="rounded-full bg-white/[0.07] px-2 py-1">雨刷 {vehicle.wiperMode}</span><span className="rounded-full bg-white/[0.07] px-2 py-1">车门 {Object.values(vehicle.doors).filter(Boolean).length ? "有开启" : "全关"}</span><span className="rounded-full bg-white/[0.07] px-2 py-1">香氛 {vehicle.airQuality.fragrance}</span><span className="rounded-full bg-white/[0.07] px-2 py-1">状态 v{stateVersion}</span><span className="rounded-full bg-cyan-400/10 px-2 py-1 text-cyan-300">{meta.model}{meta.latency ? ` · ${meta.latency}ms` : ""}</span></div></div>

          {vehicle.media.current && <section className="absolute bottom-24 left-4 z-[500] flex w-[min(350px,calc(100%-32px))] items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/[0.88] p-3 shadow-xl backdrop-blur-xl">{vehicle.media.current.artworkUrl ? <Image unoptimized src={vehicle.media.current.artworkUrl} alt="专辑封面" width={48} height={48} className="h-12 w-12 rounded-xl object-cover" /> : <div className="grid h-12 w-12 place-items-center rounded-xl bg-violet-500/20 text-violet-200">♫</div>}<div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-white">{vehicle.media.current.title}</p><p className="truncate text-xs text-slate-500">{vehicle.media.current.artist} · 30 秒真实试听</p></div><button type="button" disabled={busy} onClick={() => void submit(vehicle.media.playing ? "暂停音乐" : "继续播放音乐")} className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/10 text-sm text-white hover:bg-white/20">{vehicle.media.playing ? "Ⅱ" : "▶"}</button></section>}
          {vehicle.media.current?.previewUrl && <audio ref={audioRef} src={vehicle.media.current.previewUrl} preload="metadata" onEnded={() => void submit("下一首")} />}

          {mapDrawer === "scenes" && <DrawerShell title="场景中心" subtitle="8 组可执行座舱任务，不是静态演示卡片" onClose={() => setMapDrawer(null)}><div className="grid grid-cols-2 gap-3">{scenarioOptions.map((option) => <button type="button" key={option.value} disabled={busy} onClick={() => void changeScenario(option.value)} className={"rounded-2xl border p-4 text-left transition " + (scenario === option.value ? "border-cyan-400/35 bg-cyan-400/[0.09]" : "border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.07]")}><div className="flex items-center justify-between gap-2"><p className="text-sm font-semibold text-white">{option.label}</p>{scenario === option.value && <span className="text-[10px] text-cyan-300">当前</span>}</div><p className="mt-1 text-[10px] text-cyan-300">{option.hint}</p><p className="mt-2 text-xs leading-5 text-slate-500">{option.description}</p></button>)}</div><p className="mt-4 rounded-xl bg-white/[0.04] p-3 text-xs leading-5 text-slate-500">切换场景会创建隔离车辆会话，并把推荐任务放入右侧输入框。旧对话仍保留在历史中。</p></DrawerShell>}

          {mapDrawer === "vehicle" && <DrawerShell title="车辆控制中心" subtitle="所有快捷操作仍经过 Agent、权限与策略核" onClose={() => setMapDrawer(null)}><div className="space-y-4">
            <div><p className="mb-2 text-xs text-slate-500">舒适与空气</p><div className="grid grid-cols-2 gap-2">{[["空调 22℃", "把空调调到22度"], ["座椅通风", "打开主驾座椅通风2挡"], ["空气净化", "打开2挡空气净化器"], ["森林香氛", "打开森林香氛"]].map(([label, command]) => <button type="button" key={label} onClick={() => void submit(command)} disabled={busy} className="rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-3 text-sm text-slate-200 hover:bg-white/[0.07]">{label}</button>)}</div></div>
            <div><p className="mb-2 text-xs text-slate-500">视野与车身</p><div className="grid grid-cols-2 gap-2">{[["自动雨刷", "打开自动雨刷"], ["后视镜加热", "打开两侧后视镜加热"], ["四窗 20%", "把四个车窗都打开20%"], ["儿童锁", vehicle.childLock ? "关闭儿童锁" : "打开儿童锁"], ["右后车门", vehicle.doors.rearRight ? "关闭右后车门" : "打开右后车门"], ["充电口", vehicle.chargePortOpen ? "关闭充电口" : "打开充电口"]].map(([label, command]) => <button type="button" key={label} onClick={() => void submit(command)} disabled={busy} className="rounded-xl border border-white/[0.08] bg-white/[0.03] px-3 py-3 text-sm text-slate-200 hover:bg-white/[0.07]">{label}</button>)}</div></div>
            <dl className="grid grid-cols-2 gap-2 text-xs">{[["四门", Object.values(vehicle.doors).some(Boolean) ? "存在开启" : "全部关闭"], ["后视镜", vehicle.mirrors.driverFolded ? "已折叠" : "已展开"], ["净化器", vehicle.airQuality.purifierEnabled ? vehicle.airQuality.purifierLevel + " 挡" : "关闭"], ["充电口", vehicle.chargePortOpen ? "开启" : "关闭"]].map(([label, value]) => <div key={label} className="rounded-xl bg-black/20 p-3"><dt className="text-slate-600">{label}</dt><dd className="mt-1 text-slate-300">{value}</dd></div>)}</dl>
          </div></DrawerShell>}

          {mapDrawer === "route" && <DrawerShell title="路线详情" subtitle={vehicle.routeProvider + " · 更新 " + routeFreshness} onClose={() => setMapDrawer(null)}><div className="space-y-4"><div className="grid grid-cols-3 gap-2">{[[vehicle.routeDistanceKm === null ? "—" : vehicle.routeDistanceKm + " km", "距离"], [vehicle.routeEtaMinutes === null ? "—" : vehicle.routeEtaMinutes + " 分钟", "预计用时"], [vehicle.estimatedArrivalBattery === null ? "—" : vehicle.estimatedArrivalBattery + "%", "到达电量"]].map(([value, label]) => <div key={label} className="rounded-xl bg-white/[0.04] p-3"><p className="text-sm font-semibold text-white">{value}</p><p className="mt-1 text-[10px] text-slate-500">{label}</p></div>)}</div><div className="space-y-2">{(vehicle.routeSteps.length ? vehicle.routeSteps : ["等待 Agent 完成目的地检索与道路算路"]).map((step, index) => <div key={step + "-" + index} className="flex gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-3 text-sm text-slate-300"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-blue-500/15 text-xs text-blue-300">{index + 1}</span><p className="leading-6">{step}</p></div>)}</div><div className="space-y-2">{vehicle.routeAlternatives.map((route, index) => <div key={route.label} className={"rounded-xl border p-3 " + (index === 0 ? "border-cyan-400/25 bg-cyan-400/[0.07]" : "border-white/[0.07] bg-white/[0.03]")}><p className="text-sm font-medium">{route.label}</p><p className="mt-1 text-xs text-slate-500">{route.distanceKm} km · {route.etaMinutes} 分钟</p></div>)}</div></div></DrawerShell>}

          <nav aria-label="座舱快捷控制" className="absolute bottom-4 left-1/2 z-[600] flex max-w-[calc(100%-32px)] -translate-x-1/2 items-center gap-1 overflow-x-auto rounded-[22px] border border-white/10 bg-slate-950/[0.88] p-1.5 shadow-2xl shadow-black/50 backdrop-blur-2xl">
            <DockButton active={mapDrawer === "scenes"} label="体验模式" value="场景" onClick={() => setMapDrawer((current) => current === "scenes" ? null : "scenes")} />
            <DockButton label={"风量 " + vehicle.fanLevel + "挡"} value={vehicle.targetTemperature + "℃"} onClick={() => void submit("把空调调到22度")} />
            <button type="button" disabled={!voiceSupported || busy} aria-label={listening ? "停止语音输入" : "开始语音输入"} onClick={toggleVoiceInput} className={"mx-1 grid h-14 w-14 shrink-0 place-items-center rounded-full border text-sm font-semibold shadow-lg transition " + (listening ? "border-rose-300/40 bg-rose-500 text-white shadow-rose-500/25" : "border-cyan-300/30 bg-blue-500 text-white shadow-blue-500/25 hover:bg-blue-400")}>{listening ? "停止" : "语音"}</button>
            <DockButton label={vehicle.media.playing ? "正在播放" : "试听目录"} value={vehicle.media.current ? (vehicle.media.playing ? "暂停" : "播放") : "音乐"} onClick={() => void submit(vehicle.media.current ? (vehicle.media.playing ? "暂停音乐" : "继续播放音乐") : "播放轻音乐")} />
            <DockButton active={mapDrawer === "vehicle"} label="设备与状态" value="车辆" onClick={() => setMapDrawer((current) => current === "vehicle" ? null : "vehicle")} />
            <DockButton active={mapDrawer === "route"} label={hasLiveRoute ? "路线已就绪" : "等待算路"} value="路线" onClick={() => setMapDrawer((current) => current === "route" ? null : "route")} />
          </nav>
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.07] px-5 py-2 text-[10px] text-slate-600"><p>地图 © OpenStreetMap · 道路路线 OSRM · 音乐试听 Apple / Deezer 公共目录</p><p>{vehicle.locationSource === "browser_geolocation" ? "定位精度约 ±" + Math.round(vehicle.locationAccuracyMeters ?? 0) + " m；坐标不进入模型回执" : "当前使用沙箱坐标，授权后可从真实位置算路"}</p></footer>
      </section>
    </div>

    <aside className="min-w-0 xl:sticky xl:top-[94px] xl:h-[calc(100vh-114px)]"><section className="flex h-[760px] max-h-[calc(100vh-114px)] min-h-[640px] flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#0b1220] shadow-2xl shadow-black/30"><div className="border-b border-white/10 px-4 pt-4"><div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="font-semibold">座舱主智能体</h2><p className="mt-0.5 text-xs text-slate-500">统一交互 · 多领域编排 · 策略核执行</p></div><button type="button" disabled={!speechOutputSupported} aria-pressed={voiceReply} onClick={() => { window.speechSynthesis?.cancel(); setVoiceReply((current) => !current); }} className={`rounded-lg border px-2.5 py-1.5 text-xs ${voiceReply ? "border-cyan-400/25 bg-cyan-400/10 text-cyan-300" : "border-white/10 text-slate-500"}`}>语音播报 {voiceReply ? "开" : "关"}</button></div><div className="grid grid-cols-5 gap-1 rounded-xl bg-black/20 p-1">{([["assistant", "对话"], ["plan", `任务 ${taskPlan?.nodes.length ?? 0}`], ["trace", `记录 ${traces.length}`], ["policy", "安全"], ["history", `历史 ${conversations.length}`]] as Array<[Panel, string]>).map(([value, label]) => <button key={value} onClick={() => setPanel(value)} className={`rounded-lg px-1 py-2 text-xs font-medium ${panel === value ? "bg-white/10 text-white shadow" : "text-slate-500 hover:text-slate-200"}`}>{label}</button>)}</div></div>
      {panel === "assistant" && <><div ref={chatScrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">{messages.map((message, index) => <div key={`${message.time}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-br-md bg-blue-500 text-white" : "rounded-bl-md border border-white/[0.06] bg-white/[0.05] text-slate-200"}`}><p>{message.content}</p><p className={`mt-1 text-[11px] ${message.role === "user" ? "text-blue-100" : "text-slate-600"}`}>{message.time}</p></div></div>)}{busy && <div className="w-fit rounded-2xl rounded-bl-md border border-cyan-400/15 bg-cyan-400/[0.07] px-4 py-3 text-sm text-cyan-200"><span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-300" />正在规划并执行工具链…</div>}</div><div className="border-t border-white/10 p-4"><div className="mb-3 flex gap-2 overflow-x-auto pb-1">{prompts.map((prompt) => <button key={prompt} disabled={busy || !sessionId || listening} onClick={() => void submit(prompt)} className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-400 hover:border-cyan-400/30 hover:text-cyan-200 disabled:opacity-40">{prompt}</button>)}</div><p className={`mb-2 text-xs ${listening ? "text-rose-300" : "text-slate-600"}`}>{voiceSupported ? voiceNotice : "当前浏览器不支持语音识别，键盘输入可用"}</p><form className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/20 p-2 focus-within:border-blue-400/40" onSubmit={onSubmit}><button type="button" disabled={busy || !voiceSupported} aria-label={listening ? "停止语音输入" : "开始中文语音输入"} onClick={toggleVoiceInput} className={`h-10 rounded-xl px-3 text-sm font-medium ${listening ? "bg-rose-500/20 text-rose-300" : "bg-white/5 text-slate-300"}`}>{listening ? "停止" : "语音"}</button><input value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} placeholder="例如：打开主驾通风2挡，再导航到昌平区政府" className="min-w-0 flex-1 bg-transparent px-2 py-2 text-sm text-white outline-none placeholder:text-slate-600" />{input && <button type="button" disabled={busy} onClick={() => setInput("")} className="h-10 px-2 text-xs text-slate-500 hover:text-slate-200">清空</button>}<button disabled={busy || listening || !sessionId || !input.trim()} className="h-10 rounded-xl bg-blue-500 px-4 text-sm font-semibold text-white hover:bg-blue-400 disabled:opacity-30">发送</button></form></div></>}
      {panel === "plan" && <div className="flex-1 overflow-y-auto p-4"><TaskPlanPanel plan={taskPlan} traces={traces} stateVersion={stateVersion} /></div>}
      {panel === "trace" && <div className="flex-1 space-y-3 overflow-y-auto p-4">{!traces.length && <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm leading-6 text-slate-500">执行任务后，这里会展示模型选择的工具、严格参数、策略结果和执行回执。</div>}{traces.map((trace, index) => <TraceCard key={`${trace.id}-${index}`} trace={trace} index={index} />)}</div>}
      {panel === "policy" && <div className="flex-1 space-y-3 overflow-y-auto p-4"><div className="rounded-2xl border border-cyan-400/15 bg-cyan-400/[0.06] p-4 text-sm leading-6 text-cyan-100">当前演示身份：<strong>{zhCN.roles[role]}</strong>。模型负责规划，确定性策略层掌握最终执行权；页面角色用于演示 ABAC，不等同于生产环境可信身份认证。</div>{policies.map(([title, description], index) => <div key={title} className="flex gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-400/10 text-xs font-semibold text-emerald-300">P{index + 1}</span><div><p className="text-sm font-medium text-slate-200">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{description}</p></div></div>)}</div>}
      {panel === "history" && <div className="flex-1 space-y-3 overflow-y-auto p-4"><div className="rounded-2xl border border-violet-400/15 bg-violet-400/[0.06] p-4 text-xs leading-6 text-violet-100">新建对话不会删除旧记录。这里保存最近 20 段浏览器本地对话；它不是云端账号记录，清除浏览器数据后会消失。</div>{!conversations.length && <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-slate-500">还没有历史对话。</div>}{conversations.map((conversation) => <details key={conversation.sessionId} className="group rounded-2xl border border-white/[0.07] bg-white/[0.03]"><summary className="cursor-pointer list-none p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-slate-200">{conversation.title}</p><p className="mt-1 text-[11px] text-slate-500">{new Date(conversation.updatedAt).toLocaleString("zh-CN", { hour12: false })} · {conversation.messages.length} 条消息</p></div>{conversation.sessionId === sessionId && <span className="shrink-0 rounded-full bg-emerald-400/10 px-2 py-1 text-[10px] text-emerald-300">当前</span>}</div></summary><div className="space-y-2 border-t border-white/[0.07] p-3">{conversation.messages.map((message, index) => <div key={`${message.time}-${index}`} className="rounded-xl bg-black/20 p-3"><p className="text-[10px] text-slate-600">{message.role === "user" ? "用户" : "智能体"} · {message.time}</p><p className="mt-1 text-xs leading-5 text-slate-300">{message.content}</p></div>)}</div></details>)}</div>}
    </section></aside></section>
  </main>;
}
