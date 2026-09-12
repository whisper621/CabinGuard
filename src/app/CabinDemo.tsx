"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import { cabinApiUrl } from "./lib/apiBase";
import { classifyConfirmation, isNavigationRequested } from "./lib/cabinPolicy";

type Role = "assistant" | "user" | "system";
type ToolStatus = "running" | "success" | "blocked";

type Message = {
  id: number;
  role: Role;
  content: string;
  time: string;
};

type ToolRun = {
  id: number;
  name: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: ToolStatus;
  startedAt: string;
};

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
  destination: string;
};

type PendingAction =
  | { kind: "sunroof"; value: number }
  | { kind: "comfort" }
  | null;

type Metrics = {
  attempts: number;
  completed: number;
  clarifications: number;
  protections: number;
  toolCalls: number;
};

type AgentInterpretation = {
  intent: "sunroof" | "charging" | "climate" | "trunk" | "status" | "unknown";
  percent?: number | null;
  temperature?: number | null;
  circulation?: "inside" | "outside" | null;
  confidence?: number;
};

type AiStatus = "idle" | "checking" | "connected" | "fallback";

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
  destination: "未设置",
};

const quickPrompts = [
  "车里有点闷，帮我把天窗开一半",
  "电量不多了，找个顺路快充并导航",
  "帮我调舒服一点",
  "行驶中打开后备箱",
];

const currentTime = () =>
  new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date());

const wait = (milliseconds: number) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

function parsePercent(text: string) {
  if (/一半|半开/.test(text)) return 50;
  const percent = text.match(/(\d{1,3})\s*%/);
  return percent ? Math.min(100, Math.max(0, Number(percent[1]))) : 50;
}

function parseTemperature(text: string) {
  const match = text.match(/(1[6-9]|2[0-9]|30)\s*(?:度|℃)?/);
  return match ? Number(match[1]) : null;
}

function Badge({ children, tone = "blue" }: { children: React.ReactNode; tone?: "blue" | "green" | "amber" | "red" }) {
  const styles = {
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    red: "border-red-200 bg-red-50 text-red-700",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${styles[tone]}`}>
      {children}
    </span>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-400">{hint}</p>
    </div>
  );
}

export default function CabinDemo() {
  const [vehicle, setVehicle] = useState(initialVehicle);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      content:
        "你好，我是 CabinGuard。你可以用自然语言让我调节座舱、规划补能或查询车辆状态；涉及行驶安全的动作，我会先检查状态并在必要时确认。",
      time: "已就绪",
    },
  ]);
  const [toolRuns, setToolRuns] = useState<ToolRun[]>([]);
  const [metrics, setMetrics] = useState<Metrics>({
    attempts: 0,
    completed: 0,
    clarifications: 0,
    protections: 0,
    toolCalls: 0,
  });
  const [pending, setPending] = useState<PendingAction>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [aiStatus, setAiStatus] = useState<AiStatus>("idle");
  const [listening, setListening] = useState(false);
  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(true);
  const messageId = useRef(2);
  const toolId = useRef(1);

  const completionRate = useMemo(
    () => (metrics.attempts ? Math.round((metrics.completed / metrics.attempts) * 100) : 0),
    [metrics.attempts, metrics.completed],
  );

  const aiStatusView = {
    idle: { label: "DeepSeek 优先", tone: "blue" as const },
    checking: { label: "DeepSeek 分析中", tone: "amber" as const },
    connected: { label: "DeepSeek 已连接", tone: "green" as const },
    fallback: { label: "本地规则回退", tone: "amber" as const },
  }[aiStatus];

  const addMessage = (role: Role, content: string) => {
    const message: Message = {
      id: messageId.current++,
      role,
      content,
      time: currentTime(),
    };
    setMessages((current) => [...current, message]);
  };

  const speak = (content: string) => {
    if (!voiceOutputEnabled || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(content);
    utterance.lang = "zh-CN";
    utterance.rate = 1.05;
    window.speechSynthesis.speak(utterance);
  };

  const interpretWithDeepSeek = async (text: string): Promise<AgentInterpretation | null> => {
    if (aiStatus === "fallback") return null;
    setAiStatus("checking");
    try {
      const response = await fetch(cabinApiUrl("/api/deepseek/interpret"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) {
        setAiStatus("fallback");
        return null;
      }
      const data = (await response.json()) as { interpretation?: AgentInterpretation };
      if (!data.interpretation?.intent) {
        setAiStatus("fallback");
        return null;
      }
      setAiStatus("connected");
      return data.interpretation;
    } catch {
      setAiStatus("fallback");
      return null;
    }
  };

  const runTool = async <T extends Record<string, unknown>>(
    name: string,
    toolInput: Record<string, unknown>,
    execute: () => T,
  ): Promise<T> => {
    const id = toolId.current++;
    setToolRuns((current) => [
      { id, name, input: toolInput, status: "running", startedAt: currentTime() },
      ...current,
    ]);
    setMetrics((current) => ({ ...current, toolCalls: current.toolCalls + 1 }));
    await wait(360);
    const output = execute();
    setToolRuns((current) =>
      current.map((run) => (run.id === id ? { ...run, output, status: "success" } : run)),
    );
    return output;
  };

  const addBlockedTool = (name: string, toolInput: Record<string, unknown>, reason: string) => {
    setToolRuns((current) => [
      {
        id: toolId.current++,
        name,
        input: toolInput,
        output: { executed: false, reason },
        status: "blocked",
        startedAt: currentTime(),
      },
      ...current,
    ]);
    setMetrics((current) => ({
      ...current,
      protections: current.protections + 1,
      toolCalls: current.toolCalls + 1,
    }));
  };

  const completeTask = (message: string) => {
    addMessage("assistant", message);
    speak(message);
    setMetrics((current) => ({ ...current, completed: current.completed + 1 }));
  };

  const handleSunroof = async (text: string, confirmed = false) => {
    const target = parsePercent(text);
    const state = await runTool("get_vehicle_state", {}, () => ({
      speed_kmh: vehicle.speed,
      gear: "D",
      battery_percent: vehicle.battery,
    }));
    const weather = await runTool("get_weather", { location: "当前位置" }, () => ({
      condition: vehicle.weather,
      rain_probability: vehicle.rainProbability,
    }));

    if (weather.rain_probability >= 50) {
      addBlockedTool("control_sunroof", { target_percent: target }, "降雨概率较高");
      addMessage("assistant", `当前位置降雨概率为 ${weather.rain_probability}%，为避免雨水进入车内，我没有打开天窗。可以改为外循环通风。`);
      return;
    }

    if (state.speed_kmh >= 80 && !confirmed) {
      setPending({ kind: "sunroof", value: target });
      setMetrics((current) => ({ ...current, clarifications: current.clarifications + 1 }));
      addMessage(
        "assistant",
        `当前车速 ${state.speed_kmh} km/h，高速打开天窗可能带来明显风噪。我可以先打开遮阳帘，再将天窗打开到 ${target}%。确认继续吗？`,
      );
      return;
    }

    await runTool("control_sunroof", { target_percent: target, confirmed }, () => {
      setVehicle((current) => ({ ...current, sunshade: 100, sunroof: target }));
      return { executed: true, sunshade_percent: 100, sunroof_percent: target };
    });
    setPending(null);
    completeTask(`已先打开遮阳帘，并将天窗打开到 ${target}%。当前降雨概率 ${vehicle.rainProbability}%，如天气变化我会提醒你。`);
  };

  const handleCharging = async (shouldNavigate: boolean) => {
    const state = await runTool("get_vehicle_state", {}, () => ({
      battery_percent: vehicle.battery,
      estimated_range_km: vehicle.range,
      route: "京承高速北向",
    }));
    const station = await runTool(
      "search_charging_stations",
      { along_route: true, charger_type: "快充", max_detour_km: 5 },
      () => ({
        name: "顺义服务区超充站",
        distance_km: 18.6,
        detour_km: 1.8,
        available_fast_chargers: 6,
        estimated_arrival_battery_percent: 31,
      }),
    );
    if (shouldNavigate) {
      await runTool("start_navigation", { destination: station.name }, () => {
        setVehicle((current) => ({ ...current, destination: station.name }));
        return { navigation_started: true, eta_minutes: 16 };
      });
      completeTask(
        `已结合当前 ${state.battery_percent}% 电量和路线，选择顺路的「${station.name}」：距你 ${station.distance_km} km，绕行 ${station.detour_km} km，目前有 ${station.available_fast_chargers} 个快充空闲。导航已开始，预计 16 分钟到达。`,
      );
      return;
    }
    completeTask(
      `已找到顺路的「${station.name}」：距你 ${station.distance_km} km，绕行 ${station.detour_km} km，目前有 ${station.available_fast_chargers} 个快充空闲。我还没有启动导航，需要时请明确告诉我。`,
    );
  };

  const setComfort = async (targetTemperature: number, circulation: "内循环" | "外循环") => {
    await runTool("get_climate_state", {}, () => ({
      cabin_temperature_c: vehicle.cabinTemperature,
      target_temperature_c: vehicle.targetTemperature,
      fan_level: vehicle.fanLevel,
      circulation: vehicle.circulation,
    }));
    await runTool(
      "set_climate",
      { target_temperature_c: targetTemperature, fan_level: 2, circulation },
      () => {
        setVehicle((current) => ({
          ...current,
          targetTemperature,
          fanLevel: 2,
          circulation,
        }));
        return { executed: true, target_temperature_c: targetTemperature, fan_level: 2, circulation };
      },
    );
    setPending(null);
    completeTask(`已将空调设为 ${targetTemperature}℃、风量 2 档并切换为${circulation}。你觉得仍然偏热或偏闷时，我可以继续微调。`);
  };

  const handleClimate = async (text: string) => {
    const temperature = parseTemperature(text);
    if (/舒服|舒适|调一下/.test(text) && temperature === null && !/热|冷|闷|通风/.test(text)) {
      setPending({ kind: "comfort" });
      setMetrics((current) => ({ ...current, clarifications: current.clarifications + 1 }));
      addMessage("assistant", "可以。你现在主要是觉得偏热，还是空气有点闷？我会据此调整温度和循环模式。");
      return;
    }
    const target = temperature ?? (/冷/.test(text) ? 25 : 23);
    const circulation: "内循环" | "外循环" = /闷|通风|外循环/.test(text) ? "外循环" : vehicle.circulation;
    await setComfort(target, circulation);
  };

  const handleTrunk = () => {
    const reason = `车辆正在以 ${vehicle.speed} km/h 行驶，后备箱只能在驻车状态下开启`;
    addBlockedTool("control_trunk", { action: "open" }, reason);
    const message = `我没有执行。${reason}。停车并切换到 P 挡后，我可以再为你开启。`;
    addMessage("assistant", message);
    speak(message);
  };

  const handleStatus = async () => {
    const state = await runTool("get_vehicle_state", {}, () => ({
      speed_kmh: vehicle.speed,
      battery_percent: vehicle.battery,
      estimated_range_km: vehicle.range,
      cabin_temperature_c: vehicle.cabinTemperature,
      destination: vehicle.destination,
    }));
    completeTask(
      `当前车速 ${state.speed_kmh} km/h，剩余电量 ${state.battery_percent}%，预计续航 ${state.estimated_range_km} km；车内 ${state.cabin_temperature_c}℃，导航目的地为${state.destination}。`,
    );
  };

  const processInput = async (rawText: string, countAttempt = true) => {
    const text = rawText.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    addMessage("user", text);
    if (countAttempt) setMetrics((current) => ({ ...current, attempts: current.attempts + 1 }));

    try {
      const interpretation = pending ? null : await interpretWithDeepSeek(text);
      const intent = interpretation?.confidence === undefined || interpretation.confidence >= 0.45
        ? interpretation?.intent
        : undefined;
      const confirmationDecision = pending?.kind === "sunroof" ? classifyConfirmation(text) : "none";
      if (pending?.kind === "sunroof" && confirmationDecision === "cancel") {
        setPending(null);
        addMessage("assistant", "好的，已取消这次操作。");
      } else if (pending?.kind === "sunroof" && confirmationDecision === "confirm") {
        await handleSunroof(`${pending.value}%`, true);
      } else if (pending?.kind === "sunroof") {
        addMessage("assistant", "我没有执行天窗操作。请明确回复“确认继续”或“取消”，其他表达不会被视为高风险授权。");
      } else if (pending?.kind === "comfort" && /取消|不要|否|算了/.test(text)) {
        setPending(null);
        addMessage("assistant", "好的，已取消这次操作。");
      } else if (pending?.kind === "comfort" && /闷|通风|空气/.test(text)) {
        await setComfort(24, "外循环");
      } else if (pending?.kind === "comfort" && /热|温度/.test(text)) {
        await setComfort(23, "内循环");
      } else if (intent === "sunroof" || /天窗/.test(text)) {
        const sunroofRequest = interpretation?.percent != null ? `${interpretation.percent}%` : text;
        await handleSunroof(sunroofRequest);
      } else if (intent === "charging" || /充电|快充|补能|电量不多/.test(text)) {
        await handleCharging(isNavigationRequested(text));
      } else if (intent === "trunk" || /后备箱|尾门/.test(text)) {
        handleTrunk();
      } else if (intent === "climate" || /空调|温度|舒服|舒适|冷|热|闷|通风|循环/.test(text)) {
        const climateRequest = [
          text,
          interpretation?.temperature != null ? `${interpretation.temperature}度` : "",
          interpretation?.circulation === "outside" ? "外循环" : "",
          interpretation?.circulation === "inside" ? "内循环" : "",
        ].filter(Boolean).join(" ");
        await handleClimate(climateRequest);
      } else if (intent === "status" || /状态|电量|续航|车速/.test(text)) {
        await handleStatus();
      } else {
        addBlockedTool("capability_check", { request: text }, "当前演示未接入对应车辆能力");
        addMessage(
          "assistant",
          "我理解了你的目标，但当前演示环境还没有接入这项车辆能力，因此无法确认执行成功。你可以试试座舱调节、补能导航、天窗或车辆状态查询。",
        );
      }
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void processInput(input);
  };

  const startVoiceInput = () => {
    if (typeof window === "undefined") return;
    const browserWindow = window as typeof window & {
      SpeechRecognition?: new () => any;
      webkitSpeechRecognition?: new () => any;
    };
    const Recognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition;
    if (!Recognition) {
      addMessage("assistant", "当前浏览器不支持语音识别，请使用最新版 Chrome 或 Edge，或继续使用文字输入。");
      return;
    }

    const recognition = new Recognition();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => setListening(true);
    recognition.onend = () => setListening(false);
    recognition.onerror = () => {
      setListening(false);
      addMessage("assistant", "没有获取到清晰的语音，请检查麦克风权限后重试。");
    };
    recognition.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim();
      if (transcript) void processInput(transcript);
    };
    recognition.start();
  };

  const resetDemo = () => {
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setVehicle(initialVehicle);
    setToolRuns([]);
    setMetrics({ attempts: 0, completed: 0, clarifications: 0, protections: 0, toolCalls: 0 });
    setPending(null);
    setAiStatus("idle");
    setListening(false);
    setMessages([
      {
        id: messageId.current++,
        role: "assistant",
        content: "演示已重置。请选择一个典型场景，或直接告诉我你想完成的任务。",
        time: currentTime(),
      },
    ]);
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_#dbeafe_0,_#f8fafc_34%,_#f8fafc_100%)] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 text-lg font-bold text-white shadow-lg shadow-blue-200">
              CP
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold tracking-tight">CabinGuard</h1>
                <Badge tone="blue">可信座舱 Agent</Badge>
              </div>
              <p className="mt-0.5 text-sm text-slate-500">以智能座舱为首个验证场景的情境感知任务系统</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="green">● 本地演示已就绪</Badge>
            <Badge tone={aiStatusView.tone}>{aiStatusView.label}</Badge>
            <a href="/case-study" className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">产品案例</a>
            <button onClick={() => setVoiceOutputEnabled((value) => !value)} className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
              语音播报：{voiceOutputEnabled ? "开" : "关"}
            </button>
            <a
              href="/agent-lab"
              className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-sm font-medium text-emerald-700 transition hover:bg-emerald-100"
            >
              DeepSeek Agent Lab
            </a>
            <a
              href="/evaluation"
              className="rounded-xl border border-violet-200 bg-violet-50 px-3.5 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100"
            >
              一键评测
            </a>
            <a
              href="/realtime?agentConfig=cabinPilot"
              className="rounded-xl border border-blue-200 bg-blue-50 px-3.5 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
            >
              OpenAI Realtime（可选） ↗
            </a>
            <button onClick={resetDemo} className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
              重置演示
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-[1500px] gap-5 px-5 py-6 lg:px-8 xl:grid-cols-[270px_minmax(520px,1fr)_360px]">
        <aside className="space-y-5">
          <div className="rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">实时车辆状态</h2>
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 ring-4 ring-emerald-100" />
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-slate-50 p-3">
                <p className="text-xs text-slate-500">车速</p>
                <p className="mt-1 text-xl font-semibold">{vehicle.speed}<span className="ml-1 text-xs font-normal text-slate-400">km/h</span></p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-3">
                <p className="text-xs text-slate-500">剩余电量</p>
                <p className="mt-1 text-xl font-semibold">{vehicle.battery}<span className="ml-1 text-xs font-normal text-slate-400">%</span></p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-3">
                <p className="text-xs text-slate-500">预计续航</p>
                <p className="mt-1 text-xl font-semibold">{vehicle.range}<span className="ml-1 text-xs font-normal text-slate-400">km</span></p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-3">
                <p className="text-xs text-slate-500">车内温度</p>
                <p className="mt-1 text-xl font-semibold">{vehicle.cabinTemperature}<span className="ml-1 text-xs font-normal text-slate-400">℃</span></p>
              </div>
            </div>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-slate-500">空调设定</dt><dd className="font-medium">{vehicle.targetTemperature}℃ · {vehicle.fanLevel}档</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500">循环模式</dt><dd className="font-medium">{vehicle.circulation}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500">天窗 / 遮阳帘</dt><dd className="font-medium">{vehicle.sunroof}% / {vehicle.sunshade}%</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500">天气</dt><dd className="font-medium">{vehicle.weather} · 降雨{vehicle.rainProbability}%</dd></div>
              <div className="border-t border-slate-100 pt-3"><dt className="text-slate-500">导航目的地</dt><dd className="mt-1 break-words font-medium text-blue-700">{vehicle.destination}</dd></div>
            </dl>
          </div>

          <div className="rounded-3xl border border-blue-100 bg-blue-50/80 p-5">
            <h2 className="font-semibold text-blue-950">动作前置校验</h2>
            <ul className="mt-3 space-y-3 text-sm leading-6 text-blue-900/80">
              <li>• 高速开启天窗时二次确认</li>
              <li>• 降雨风险较高时阻止开启</li>
              <li>• 行驶中禁止开启后备箱</li>
              <li>• 工具未返回成功时不声称完成</li>
            </ul>
          </div>
        </aside>

        <section className="flex min-h-[760px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold">任务对话</h2>
              <p className="text-xs text-slate-500">自然语言意图 → 状态查询 → 安全校验 → 工具执行 → 结果反馈</p>
            </div>
            {busy ? <Badge tone="amber">执行中</Badge> : <Badge tone="green">可用</Badge>}
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50/50 p-5">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[84%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${message.role === "user" ? "rounded-br-md bg-blue-600 text-white" : message.role === "system" ? "border border-amber-200 bg-amber-50 text-amber-900" : "rounded-bl-md border border-slate-200 bg-white text-slate-700"}`}>
                  <p>{message.content}</p>
                  <p className={`mt-1 text-[10px] ${message.role === "user" ? "text-blue-100" : "text-slate-400"}`}>{message.time}</p>
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  {[0, 1, 2].map((item) => <span key={item} className="h-2 w-2 animate-bounce rounded-full bg-blue-400" style={{ animationDelay: `${item * 120}ms` }} />)}
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-slate-100 bg-white p-4">
            {pending?.kind === "sunroof" && (
              <div className="mb-3 flex flex-wrap gap-2">
                <button disabled={busy} onClick={() => void processInput("确认继续", false)} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">确认继续</button>
                <button disabled={busy} onClick={() => void processInput("取消", false)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50">取消</button>
              </div>
            )}
            {pending?.kind === "comfort" && (
              <div className="mb-3 flex flex-wrap gap-2">
                <button disabled={busy} onClick={() => void processInput("有点热，温度调低", false)} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">偏热，调低温度</button>
                <button disabled={busy} onClick={() => void processInput("空气有点闷，需要通风", false)} className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50">空气闷，切外循环</button>
              </div>
            )}
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
              {quickPrompts.map((prompt) => (
                <button key={prompt} disabled={busy} onClick={() => void processInput(prompt)} className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50">
                  {prompt}
                </button>
              ))}
            </div>
            <form onSubmit={submit} className="flex gap-2">
              <input value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} placeholder="输入任务，例如：帮我找个顺路的快充站" className="min-w-0 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100 disabled:opacity-60" />
              <button type="button" aria-label="语音输入" onClick={startVoiceInput} disabled={busy || listening} className={`rounded-2xl border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${listening ? "border-red-200 bg-red-50 text-red-700" : "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"}`}>
                {listening ? "聆听中…" : "🎙 语音"}
              </button>
              <button type="submit" disabled={busy || !input.trim()} className="rounded-2xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40">发送</button>
            </form>
          </div>
        </section>

        <aside className="space-y-5">
          <div>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="font-semibold">可靠性看板</h2>
                <p className="text-xs text-slate-500">当前演示会话</p>
              </div>
              <Badge tone="blue">可量化</Badge>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="任务完成率" value={`${completionRate}%`} hint={`${metrics.completed}/${metrics.attempts} 个任务`} />
              <MetricCard label="工具调用" value={`${metrics.toolCalls}`} hint="含查询与执行" />
              <MetricCard label="主动澄清" value={`${metrics.clarifications}`} hint="避免误执行" />
              <MetricCard label="安全保护" value={`${metrics.protections}`} hint="已阻止风险动作" />
            </div>
          </div>

          <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <h2 className="font-semibold">工具执行轨迹</h2>
                <p className="text-xs text-slate-500">过程可追踪、结果可核验</p>
              </div>
              <span className="text-xs text-slate-400">{toolRuns.length} 条</span>
            </div>
            <div className="max-h-[430px] space-y-3 overflow-y-auto p-4">
              {toolRuns.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">执行任务后，此处展示工具调用与返回结果</div>
              ) : (
                toolRuns.map((run) => (
                  <div key={run.id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="break-all font-mono text-xs font-semibold text-slate-700">{run.name}</p>
                        <p className="mt-0.5 text-[10px] text-slate-400">{run.startedAt}</p>
                      </div>
                      <Badge tone={run.status === "success" ? "green" : run.status === "blocked" ? "red" : "amber"}>
                        {run.status === "success" ? "成功" : run.status === "blocked" ? "已阻止" : "执行中"}
                      </Badge>
                    </div>
                    <details className="mt-2 text-xs text-slate-500">
                      <summary className="cursor-pointer select-none hover:text-blue-600">查看输入与输出</summary>
                      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-xl bg-slate-900 p-3 text-[10px] leading-5 text-slate-200">{JSON.stringify({ input: run.input, output: run.output }, null, 2)}</pre>
                    </details>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="font-semibold">项目验证设计</h2>
            <div className="mt-3 grid gap-2 text-sm text-slate-600">
              <div className="flex justify-between rounded-xl bg-slate-50 px-3 py-2"><span>标准任务用例</span><strong className="text-slate-800">12 类</strong></div>
              <div className="flex justify-between rounded-xl bg-slate-50 px-3 py-2"><span>异常与安全用例</span><strong className="text-slate-800">8 类</strong></div>
              <div className="flex justify-between rounded-xl bg-slate-50 px-3 py-2"><span>核心评价维度</span><strong className="text-slate-800">5 项</strong></div>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">覆盖任务完成、意图澄清、工具正确性、安全合规和无依据输出。数据为本地模拟，便于稳定复现产品逻辑。</p>
          </div>
        </aside>
      </section>
    </main>
  );
}
