"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { cabinApiUrl } from "../lib/apiBase";

type GeoPoint = { latitude: number; longitude: number };
type VehicleState = {
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
type CabinScenario = "default" | "rain" | "moving";
type BrowserLocation = { latitude: number; longitude: number; accuracyMeters?: number };

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((event: {
    results: { length: number; [index: number]: { [index: number]: { transcript: string } } };
  }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type Message = { role: "user" | "assistant"; content: string; time: string };
type Trace = {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  status: "success" | "blocked";
};

type AgentResponse = {
  message: string;
  sessionId: string;
  vehicle: VehicleState;
  traces: Trace[];
  model: string;
  turns: number;
  totalTokens: number;
  promptVersion: string;
  toolVersion: string;
  error?: { message?: string };
};

const initialVehicle: VehicleState = {
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
};

const prompts = [
  "把空调调到23度并切换外循环",
  "电量不多了，找个顺路快充并导航",
  "高速上有点闷，把天窗开一半",
  "行驶中帮我打开后备箱",
];
const scenarioOptions: Array<{ value: CabinScenario; label: string; hint: string }> = [
  { value: "default", label: "高速", hint: "82 km/h · 多云" },
  { value: "rain", label: "降雨", hint: "P 挡 · 70%" },
  { value: "moving", label: "行驶", hint: "35 km/h · D 挡" },
];

const now = () =>
  new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date());

function StateItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function RoutePreview({ vehicle }: { vehicle: VehicleState }) {
  const hasRoute = vehicle.routePolyline.length >= 2;
  const points = hasRoute ? vehicle.routePolyline : [{
    latitude: vehicle.latitude,
    longitude: vehicle.longitude,
  }];
  const latitudes = points.map((point) => point.latitude);
  const longitudes = points.map((point) => point.longitude);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const latitudeSpan = Math.max(maxLatitude - minLatitude, 0.01);
  const longitudeSpan = Math.max(maxLongitude - minLongitude, 0.01);
  const plotted = points.map((point) => ({
    x: 24 + ((point.longitude - minLongitude) / longitudeSpan) * 252,
    y: 154 - ((point.latitude - minLatitude) / latitudeSpan) * 122,
  }));
  const polyline = plotted.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-950 text-white">
      <div className="flex items-center justify-between px-3 pt-3">
        <div>
          <p className="text-xs font-medium text-slate-200">导航路线</p>
          <p className="mt-0.5 text-[11px] text-slate-400">坐标投影示意 · 非真实道路地图</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] ${hasRoute ? "bg-blue-500/20 text-blue-200" : "bg-white/10 text-slate-400"}`}>
          {hasRoute ? "导航中" : "等待路线"}
        </span>
      </div>
      <svg aria-label="导航路线示意图" className="mt-2 h-40 w-full" viewBox="0 0 300 180" role="img">
        <defs>
          <pattern id="route-grid" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#1e293b" strokeWidth="1" />
          </pattern>
          <linearGradient id="route-line" x1="0" x2="1">
            <stop offset="0" stopColor="#60a5fa" />
            <stop offset="1" stopColor="#34d399" />
          </linearGradient>
        </defs>
        <rect width="300" height="180" fill="url(#route-grid)" />
        {hasRoute ? (
          <>
            <polyline points={polyline} fill="none" stroke="#0f172a" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
            <polyline points={polyline} fill="none" stroke="url(#route-line)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
            {plotted.slice(1, -1).map((point, index) => (
              <circle key={`${point.x}-${point.y}-${index}`} cx={point.x} cy={point.y} fill="#93c5fd" r="3" />
            ))}
            <circle cx={plotted.at(-1)?.x} cy={plotted.at(-1)?.y} fill="#34d399" r="7" stroke="#d1fae5" strokeWidth="3" />
          </>
        ) : (
          <path d="M56 132 C112 82 182 110 250 46" fill="none" stroke="#334155" strokeDasharray="7 7" strokeWidth="3" />
        )}
        <circle cx={hasRoute ? plotted[0].x : 56} cy={hasRoute ? plotted[0].y : 132} fill="#3b82f6" r="7" stroke="#dbeafe" strokeWidth="3" />
      </svg>
      <div className="grid grid-cols-2 border-t border-slate-800 text-xs">
        <div className="border-r border-slate-800 p-3">
          <p className="text-slate-500">距离</p>
          <p className="mt-1 font-semibold">{vehicle.routeDistanceKm === null ? "—" : `${vehicle.routeDistanceKm} km`}</p>
        </div>
        <div className="p-3">
          <p className="text-slate-500">预计时间</p>
          <p className="mt-1 font-semibold">{vehicle.routeEtaMinutes === null ? "—" : `${vehicle.routeEtaMinutes} 分钟`}</p>
        </div>
      </div>
    </div>
  );
}

function getSpeechRecognitionConstructor() {
  if (typeof window === "undefined") return undefined;
  const speechWindow = window as typeof window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
}

export default function AgentLab() {
  const [vehicle, setVehicle] = useState(initialVehicle);
  const [sessionId, setSessionId] = useState("");
  const [scenario, setScenario] = useState<CabinScenario>("default");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "这是 DeepSeek Tool Calling 模式。我会自主选择工具、读取上下文，并由服务端安全策略校验动作。",
      time: "已就绪",
    },
  ]);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [browserLocation, setBrowserLocation] = useState<BrowserLocation | null>(null);
  const [locationBusy, setLocationBusy] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [speechOutputSupported, setSpeechOutputSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceReply, setVoiceReply] = useState(true);
  const [voiceNotice, setVoiceNotice] = useState("点击麦克风后，说出中文任务");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const [meta, setMeta] = useState({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" });

  const createSession = async (
    nextScenario: CabinScenario,
    location?: BrowserLocation,
  ) => {
    const response = await fetch(cabinApiUrl("/api/cabin/session"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: nextScenario, ...(location ? { location } : {}) }),
    });
    const data = await response.json() as { sessionId?: string; vehicle?: VehicleState; error?: { message?: string } };
    if (!response.ok || !data.sessionId || !data.vehicle) {
      throw new Error(data.error?.message || "无法创建演示会话");
    }
    setSessionId(data.sessionId);
    setVehicle(data.vehicle);
  };

  useEffect(() => {
    setVoiceSupported(Boolean(getSpeechRecognitionConstructor()));
    setSpeechOutputSupported("speechSynthesis" in window);
    void createSession("default").catch((error) => {
      const message = error instanceof Error ? error.message : "无法创建演示会话";
      setMessages((current) => [...current, { role: "assistant", content: `会话初始化失败：${message}`, time: now() }]);
    });
    return () => {
      recognitionRef.current?.stop();
      window.speechSynthesis?.cancel();
    };
  }, []);

  const speak = (text: string) => {
    if (!voiceReply || !speechOutputSupported) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  };

  const toggleVoiceInput = () => {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      setVoiceNotice("当前浏览器不支持语音识别，请改用 Chrome 或 Edge，或继续键盘输入");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "zh-CN";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1]?.[0]?.transcript?.trim();
      if (result) {
        setInput(result);
        setVoiceNotice("已识别到输入，请核对后点击发送");
      }
    };
    recognition.onerror = (event) => {
      const message = event.error === "not-allowed"
        ? "麦克风权限被拒绝，请在浏览器地址栏开启权限"
        : `语音识别失败：${event.error}`;
      setVoiceNotice(message);
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    setListening(true);
    setVoiceNotice("正在聆听…再次点击可停止");
    try {
      recognition.start();
    } catch {
      setListening(false);
      setVoiceNotice("麦克风启动失败，请检查浏览器权限");
    }
  };

  const useCurrentLocation = () => {
    if (!("geolocation" in navigator)) {
      setMessages((current) => [...current, {
        role: "assistant",
        content: "当前浏览器不支持定位，继续使用京承高速模拟起点。",
        time: now(),
      }]);
      return;
    }
    if (!window.isSecureContext) {
      setMessages((current) => [...current, {
        role: "assistant",
        content: "浏览器定位需要 HTTPS 或 localhost 安全上下文，当前继续使用模拟位置。",
        time: now(),
      }]);
      return;
    }
    setLocationBusy(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location: BrowserLocation = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracyMeters: position.coords.accuracy,
        };
        void createSession(scenario, location)
          .then(() => {
            setBrowserLocation(location);
            setMessages([{
              role: "assistant",
              content: "已用你授权的浏览器坐标新建会话。该位置只用于本次路线原型，不等同于可信车载 GPS。",
              time: now(),
            }]);
            setTraces([]);
            setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" });
          })
          .catch((error) => {
            const message = error instanceof Error ? error.message : "定位写入会话失败";
            setMessages((current) => [...current, { role: "assistant", content: message, time: now() }]);
          })
          .finally(() => setLocationBusy(false));
      },
      (error) => {
        const reason = error.code === error.PERMISSION_DENIED
          ? "你拒绝了定位权限"
          : error.code === error.TIMEOUT
            ? "定位请求超时"
            : "浏览器无法获取当前位置";
        setMessages((current) => [...current, {
          role: "assistant",
          content: `${reason}，继续使用模拟位置。`,
          time: now(),
        }]);
        setLocationBusy(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    );
  };

  const submit = async (rawText: string) => {
    const text = rawText.trim();
    if (!text || busy || !sessionId) return;
    const history = messages.slice(-8).map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, { role: "user", content: text, time: now() }]);
    setInput("");
    setBusy(true);
    const started = performance.now();

    try {
      let response: Response | null = null;
      for (let attempt = 1; attempt <= 2; attempt += 1) {
        response = await fetch(cabinApiUrl("/api/deepseek/agent"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, sessionId, history }),
        });
        if (response.ok || response.status !== 502 || attempt === 2) break;
      }
      if (!response) throw new Error("Agent 请求未发出");
      const data = (await response.json()) as AgentResponse;
      if (!response.ok) throw new Error(data.error?.message || "Agent 请求失败");
      setVehicle(data.vehicle);
      setSessionId(data.sessionId);
      setTraces((current) => [...[...data.traces].reverse(), ...current]);
      setMessages((current) => [...current, { role: "assistant", content: data.message, time: now() }]);
      speak(data.message);
      setMeta({
        model: data.model,
        turns: data.turns,
        tokens: data.totalTokens,
        latency: Math.round(performance.now() - started),
        promptVersion: data.promptVersion,
        toolVersion: data.toolVersion,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知错误";
      setMessages((current) => [...current, { role: "assistant", content: `本次执行失败：${message}`, time: now() }]);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit(input);
  };

  const reset = async () => {
    try {
      await createSession(scenario, browserLocation ?? undefined);
    } catch (error) {
      const message = error instanceof Error ? error.message : "无法创建演示会话";
      setMessages((current) => [...current, { role: "assistant", content: `重置失败：${message}`, time: now() }]);
      return;
    }
    setMessages([
      {
        role: "assistant",
        content: "执行环境已重置。你可以重新测试多步调用、澄清和安全拦截。",
        time: now(),
      },
    ]);
    setTraces([]);
    setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" });
  };

  const changeScenario = async (nextScenario: CabinScenario) => {
    if (busy || nextScenario === scenario) return;
    setBusy(true);
    try {
      await createSession(nextScenario, browserLocation ?? undefined);
      setScenario(nextScenario);
      setMessages([{
        role: "assistant",
        content: `已切换到${scenarioOptions.find((item) => item.value === nextScenario)?.label}场景。新的服务端会话不会继承上一场景的状态或确认。`,
        time: now(),
      }]);
      setTraces([]);
      setMeta({ model: "等待调用", turns: 0, tokens: 0, latency: 0, promptVersion: "—", toolVersion: "—" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "无法切换演示场景";
      setMessages((current) => [...current, { role: "assistant", content: `场景切换失败：${message}`, time: now() }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-lg bg-blue-600 px-2 py-1 text-xs font-bold text-white">CP</span>
              <h1 className="text-lg font-semibold">CabinGuard Agent Lab</h1>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">1 Agent · 8 Tools</span>
            </div>
            <p className="mt-1 text-sm text-slate-500">模型规划 → 工具执行 → 策略校验 → 结果回传 → 继续决策</p>
          </div>
          <nav className="flex items-center gap-2 text-sm">
            <Link className="rounded-lg border border-slate-200 bg-white px-3 py-2 hover:bg-slate-50" href="/">稳定演示</Link>
            <Link className="rounded-lg border border-slate-200 bg-white px-3 py-2 hover:bg-slate-50" href="/case-study">产品案例</Link>
            <Link className="rounded-lg border border-slate-200 bg-white px-3 py-2 hover:bg-slate-50" href="/evaluation">一键评测</Link>
            <button className="rounded-lg bg-slate-900 px-3 py-2 text-white hover:bg-slate-700" onClick={() => void reset()}>重置状态</button>
          </nav>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-5 px-5 py-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <aside className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">模拟车辆状态</h2>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-500">场景驱动</span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-1.5">
              {scenarioOptions.map((option) => (
                <button
                  key={option.value}
                  disabled={busy}
                  onClick={() => void changeScenario(option.value)}
                  title={option.hint}
                  className={`rounded-lg border px-2 py-2 text-xs font-medium transition disabled:opacity-50 ${scenario === option.value ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500 hover:border-blue-300"}`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <StateItem label="车速" value={`${vehicle.speed} km/h`} />
              <StateItem label="剩余电量" value={`${vehicle.battery}%`} />
              <StateItem label="预计续航" value={`${vehicle.range} km`} />
              <StateItem label="车内温度" value={`${vehicle.cabinTemperature}℃`} />
              <StateItem label="空调设定" value={`${vehicle.targetTemperature}℃ · ${vehicle.fanLevel}档`} />
              <StateItem label="循环模式" value={vehicle.circulation} />
              <StateItem label="天窗" value={`${vehicle.sunroof}%`} />
              <StateItem label="降雨概率" value={`${vehicle.rainProbability}%`} />
            </div>
            <div className="mt-2 rounded-xl border border-blue-100 bg-blue-50 p-3">
              <p className="text-xs text-blue-600">导航目的地</p>
              <p className="mt-1 text-sm font-semibold text-blue-900">{vehicle.destination}</p>
            </div>
            <div className="mt-2 rounded-xl border border-violet-100 bg-violet-50 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs text-violet-600">当前位置</p>
                  <p className="mt-1 break-words text-sm font-semibold text-violet-950">{vehicle.currentLocation}</p>
                  <p className="mt-1 text-[11px] text-violet-600">
                    {vehicle.latitude.toFixed(5)}, {vehicle.longitude.toFixed(5)}
                    {vehicle.locationAccuracyMeters !== null ? ` · ±${Math.round(vehicle.locationAccuracyMeters)} m` : ""}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-white px-2 py-1 text-[10px] text-violet-700">
                  {vehicle.locationSource === "browser_geolocation" ? "浏览器授权" : "模拟"}
                </span>
              </div>
              <button
                type="button"
                disabled={busy || locationBusy}
                onClick={useCurrentLocation}
                className="mt-3 w-full rounded-lg border border-violet-200 bg-white px-3 py-2 text-xs font-medium text-violet-700 hover:border-violet-400 disabled:opacity-50"
              >
                {locationBusy ? "正在请求定位…" : "使用我的当前位置"}
              </button>
            </div>
            <div className="mt-3">
              <RoutePreview vehicle={vehicle} />
            </div>
            <p className="mt-2 text-[11px] leading-4 text-slate-400">定位需你主动授权；精确坐标留在本地会话，不进入模型工具上下文。充电站与道路路线仍为演示沙箱数据。</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="font-semibold">本次推理</h2>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-slate-500">模型</dt><dd className="text-right font-medium">{meta.model}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">模型轮次</dt><dd className="font-medium">{meta.turns}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Token</dt><dd className="font-medium">{meta.tokens}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Prompt / Tool</dt><dd className="font-medium">v{meta.promptVersion} / v{meta.toolVersion}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">端到端延迟</dt><dd className="font-medium">{meta.latency ? `${meta.latency} ms` : "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">服务端会话</dt><dd className="font-medium">{sessionId ? "已建立" : "初始化中"}</dd></div>
            </dl>
          </div>
        </aside>

        <section className="flex min-h-[680px] flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="font-semibold">任务对话</h2>
              <p className="mt-1 text-xs text-slate-500">每次执行都由 DeepSeek 决定下一步工具，服务端保留最终安全控制权。</p>
            </div>
            <button
              type="button"
              disabled={!speechOutputSupported}
              aria-pressed={voiceReply}
              onClick={() => {
                window.speechSynthesis?.cancel();
                setVoiceReply((current) => !current);
              }}
              className={`shrink-0 rounded-lg border px-3 py-2 text-xs font-medium disabled:opacity-40 ${voiceReply ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500"}`}
            >
              {voiceReply ? "播报已开" : "播报已关"}
            </button>
          </div>
          <div className="flex-1 space-y-4 overflow-auto p-5">
            {messages.map((message, index) => (
              <div key={`${message.time}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"}`}>
                  <p>{message.content}</p>
                  <p className={`mt-1 text-[11px] ${message.role === "user" ? "text-blue-100" : "text-slate-400"}`}>{message.time}</p>
                </div>
              </div>
            ))}
            {busy && <div className="w-fit rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-700">Agent 正在规划并执行工具链…</div>}
          </div>
          <div className="border-t border-slate-200 p-4">
            <div className="mb-3 flex flex-wrap gap-2">
              {prompts.map((prompt) => (
                <button key={prompt} disabled={busy || !sessionId} onClick={() => void submit(prompt)} className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:border-blue-300 hover:text-blue-700 disabled:opacity-50">
                  {prompt}
                </button>
              ))}
            </div>
            <p className={`mb-2 text-xs ${listening ? "text-red-600" : "text-slate-400"}`}>
              {voiceSupported ? voiceNotice : "当前浏览器不支持语音识别，键盘输入仍可用"}
            </p>
            <form className="flex gap-2" onSubmit={onSubmit}>
              <button
                type="button"
                disabled={busy || !voiceSupported}
                aria-label={listening ? "停止语音输入" : "开始中文语音输入"}
                aria-pressed={listening}
                onClick={toggleVoiceInput}
                className={`rounded-xl border px-4 py-3 text-sm font-medium disabled:opacity-40 ${listening ? "border-red-300 bg-red-50 text-red-700" : "border-slate-300 bg-white text-slate-700 hover:border-blue-400"}`}
              >
                {listening ? "停止" : "麦克风"}
              </button>
              <input value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} placeholder="输入一个需要多步执行的座舱任务" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500" />
              <button disabled={busy || !sessionId || !input.trim()} className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40">发送</button>
            </form>
          </div>
        </section>

        <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-semibold">模型工具调用轨迹</h2>
              <p className="mt-1 text-xs text-slate-500">输入、输出、顺序与拦截结果均可复核</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{traces.length} 条</span>
          </div>
          <div className="mt-4 space-y-3">
            {!traces.length && <p className="rounded-xl border border-dashed border-slate-300 p-5 text-center text-sm text-slate-400">执行任务后显示轨迹</p>}
            {traces.map((trace, index) => (
              <details key={`${trace.id}-${index}`} className={`rounded-xl border p-3 ${trace.status === "blocked" ? "border-red-200 bg-red-50" : "border-emerald-200 bg-emerald-50"}`}>
                <summary className="cursor-pointer list-none text-sm font-medium">
                  <span className={`mr-2 inline-block h-2 w-2 rounded-full ${trace.status === "blocked" ? "bg-red-500" : "bg-emerald-500"}`} />
                  {trace.name}
                </summary>
                <div className="mt-3 space-y-2 text-xs">
                  <div><p className="font-medium text-slate-600">输入</p><pre className="mt-1 overflow-auto whitespace-pre-wrap rounded-lg bg-white/70 p-2 text-slate-600">{JSON.stringify(trace.input, null, 2)}</pre></div>
                  <div><p className="font-medium text-slate-600">输出</p><pre className="mt-1 overflow-auto whitespace-pre-wrap rounded-lg bg-white/70 p-2 text-slate-600">{JSON.stringify(trace.output, null, 2)}</pre></div>
                </div>
              </details>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}
