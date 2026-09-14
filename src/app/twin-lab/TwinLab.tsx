"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cabinApiUrl } from "../lib/apiBase";
import { readJson, v6WebSocketUrl, type VehicleStateV6 } from "../lib/cabinV6";

type SignalEvent = { id: string; label: string };
type TimelineItem = { version: number; at: string; speed: number; battery: number; rain: number; label: string };

const fallbackEvents: SignalEvent[] = [
  { id: "urban_drive", label: "进入城市道路" }, { id: "highway_drive", label: "进入高速道路" },
  { id: "park", label: "车辆安全驻车" }, { id: "rain", label: "降雨事件" },
  { id: "clear_weather", label: "天气转晴" }, { id: "low_battery", label: "低电量事件" },
  { id: "reset", label: "恢复默认状态" },
];

const signalCards = (vehicle: VehicleStateV6 | null) => [
  ["Vehicle.Speed", "车辆速度", vehicle ? `${vehicle.speed} km/h` : "—", vehicle?.speed && vehicle.speed >= 80 ? "warn" : "normal"],
  ["Transmission.CurrentGear", "当前挡位", vehicle?.gear ?? "—", "normal"],
  ["TractionBattery.StateOfCharge", "动力电池", vehicle ? `${vehicle.battery}%` : "—", vehicle && vehicle.battery <= 15 ? "danger" : "normal"],
  ["Environment.RainProbability", "降雨概率", vehicle ? `${vehicle.rainProbability}%` : "—", vehicle && vehicle.rainProbability >= 50 ? "warn" : "normal"],
  ["Cabin.HVAC.TargetTemperature", "目标温度", vehicle ? `${vehicle.targetTemperature}℃` : "—", "normal"],
  ["Cabin.Sunroof.Position", "天窗开度", vehicle ? `${vehicle.sunroof}%` : "—", "normal"],
] as const;

export default function TwinLab() {
  const [sessionId, setSessionId] = useState("");
  const [vehicle, setVehicle] = useState<VehicleStateV6 | null>(null);
  const [version, setVersion] = useState(0);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<SignalEvent[]>(fallbackEvents);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [busyEvent, setBusyEvent] = useState("");
  const [error, setError] = useState("");
  const lastEventLabel = useRef("初始状态");

  const ensureSession = useCallback(async () => {
    const stored = localStorage.getItem("cabinguard-session-id");
    if (stored) { setSessionId(stored); return stored; }
    const response = await fetch(cabinApiUrl("/api/cabin/session"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: "default", occupantRole: "driver" }) });
    const data = await readJson<{ sessionId: string; vehicle: VehicleStateV6; stateVersion: number }>(response);
    localStorage.setItem("cabinguard-session-id", data.sessionId); setSessionId(data.sessionId); setVehicle(data.vehicle); setVersion(data.stateVersion);
    return data.sessionId;
  }, []);

  useEffect(() => { fetch(cabinApiUrl("/api/cabin/signal-events")).then((response) => readJson<{ events: SignalEvent[] }>(response)).then((data) => setEvents(data.events)).catch(() => setEvents(fallbackEvents)); }, []);
  useEffect(() => { void ensureSession().catch((cause) => setError(cause instanceof Error ? cause.message : "无法创建会话")); }, [ensureSession]);
  useEffect(() => {
    if (!sessionId) return;
    const socket = new WebSocket(v6WebSocketUrl(sessionId));
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setError("时序信号通道未连接，请确认 Python API 已启动");
    socket.onmessage = (message) => {
      const data = JSON.parse(String(message.data)) as { type: string; stateVersion: number; vehicle: VehicleStateV6 };
      if (data.type !== "vehicle.state") return;
      setVehicle(data.vehicle); setVersion(data.stateVersion);
      setTimeline((current) => [...current, { version: data.stateVersion, at: new Date().toLocaleTimeString("zh-CN", { hour12: false }), speed: data.vehicle.speed, battery: data.vehicle.battery, rain: data.vehicle.rainProbability, label: lastEventLabel.current }].slice(-12));
    };
    return () => socket.close();
  }, [sessionId]);

  const inject = async (event: SignalEvent) => {
    if (!sessionId || busyEvent) return;
    setBusyEvent(event.id); setError(""); lastEventLabel.current = event.label;
    try {
      const response = await fetch(cabinApiUrl("/api/cabin/signal-event"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sessionId, event: event.id }) });
      await readJson(response);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "事件注入失败"); }
    finally { setBusyEvent(""); }
  };

  const maxSpeed = useMemo(() => Math.max(100, ...timeline.map((item) => item.speed)), [timeline]);

  return (
    <div className="bg-[#050b16] text-slate-100">
      <div className="mx-auto max-w-[1680px] space-y-5 px-5 py-6 lg:px-8">
        <section className="flex flex-wrap items-end justify-between gap-5 rounded-[30px] border border-white/10 bg-[linear-gradient(115deg,#0a1728,#10152a)] p-6"><div><p className="text-xs tracking-[0.2em] text-cyan-300">VSS TEMPORAL DIGITAL TWIN / 时序数字孪生</p><h1 className="mt-3 text-3xl font-semibold md:text-5xl">让安全策略在<span className="text-cyan-300">变化中的车辆</span>里接受检验</h1><p className="mt-4 max-w-4xl text-sm leading-7 text-slate-400">这里不是静态表单。事件改变服务端可信状态，状态版本通过 WebSocket 推送，随后可在“执行追溯”中复核哪一个信号、在什么时间触发了哪一次策略决策。</p></div><div className={`rounded-2xl border px-4 py-3 text-xs ${connected ? "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-300" : "border-amber-400/20 bg-amber-400/[0.07] text-amber-300"}`}><span className={`mr-2 inline-block h-2 w-2 rounded-full ${connected ? "animate-pulse bg-emerald-300" : "bg-amber-300"}`} />{connected ? `实时通道已连接 · 状态 v${version}` : "正在连接时序通道"}</div></section>
        {error && <p className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3 text-sm text-rose-200">{error}</p>}
        <section className="grid gap-5 xl:grid-cols-[.72fr_1.28fr]">
          <div className="space-y-5"><div className="rounded-[30px] border border-white/10 bg-[#091323] p-5"><p className="text-xs tracking-[0.18em] text-violet-300">SCENARIO INJECTION / 场景注入</p><h2 className="mt-2 text-xl font-semibold">选择车辆事件</h2><div className="mt-4 grid grid-cols-2 gap-2">{events.map((event) => <button key={event.id} disabled={Boolean(busyEvent)} onClick={() => void inject(event)} className="rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4 text-left text-sm transition hover:border-cyan-400/20 hover:bg-cyan-400/[0.06] disabled:opacity-50"><span className="block text-white">{event.label}</span><code className="mt-2 block text-[10px] text-slate-600">{event.id}</code></button>)}</div></div><div className="rounded-[30px] border border-amber-400/15 bg-amber-400/[0.04] p-5"><p className="text-xs tracking-[0.18em] text-amber-300">SAFETY HYPOTHESIS / 安全假设</p><p className="mt-3 text-sm leading-7 text-amber-100/70">先注入“高速道路”与“降雨”，再回到智能座舱请求开天窗。即使模型发起调用，VSS 约束仍会在服务端拒绝；这正是 Agent 决策与确定性执行分层的价值。</p></div></div>
          <div className="space-y-5"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{signalCards(vehicle).map(([path, label, value, tone]) => <article key={path} className={`rounded-2xl border p-4 ${tone === "danger" ? "border-rose-400/25 bg-rose-400/[0.06]" : tone === "warn" ? "border-amber-400/20 bg-amber-400/[0.05]" : "border-white/[0.07] bg-[#091323]"}`}><p className="truncate font-mono text-[10px] text-slate-600" title={path}>{path}</p><p className="mt-3 text-xs text-slate-400">{label}</p><p className="mt-1 text-2xl font-semibold text-white">{value}</p></article>)}</div>
            <div className="rounded-[30px] border border-white/10 bg-[#091323] p-5"><div className="flex items-center justify-between"><div><p className="text-xs tracking-[0.18em] text-cyan-300">STATE TIMELINE / 状态时间线</p><h2 className="mt-2 text-xl font-semibold">最近 12 个版本</h2></div><p className="text-xs text-slate-500">纵轴：速度 · 标签：电量 / 降雨</p></div><div className="mt-6 flex h-52 items-end gap-2 border-b border-l border-white/10 px-3">{timeline.map((item) => <div key={`${item.version}-${item.at}`} className="group relative flex h-full min-w-0 flex-1 items-end"><div style={{ height: `${Math.max(4, (item.speed / maxSpeed) * 100)}%` }} className="w-full rounded-t-lg bg-gradient-to-t from-blue-600/60 to-cyan-300 transition-all"><div className="absolute bottom-full left-1/2 z-10 mb-2 hidden w-36 -translate-x-1/2 rounded-xl border border-white/10 bg-slate-950 p-2 text-[10px] shadow-xl group-hover:block">v{item.version} · {item.label}<br />{item.speed}km/h · 电量{item.battery}% · 降雨{item.rain}%</div></div></div>)}{timeline.length === 0 && <div className="grid h-full w-full place-items-center text-xs text-slate-600">等待 WebSocket 状态帧</div>}</div><div className="mt-3 flex justify-between text-[10px] text-slate-600"><span>会话开始</span><span>当前 v{version}</span></div></div>
          </div>
        </section>
      </div>
    </div>
  );
}
