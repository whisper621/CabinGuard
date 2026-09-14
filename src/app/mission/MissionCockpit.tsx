"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import V6Nav from "../components/V6Nav";
import { cabinApiUrl, usesExternalCabinApi } from "../lib/apiBase";
import { domainLabels, readJson, type AgentResponseV6, type AgentTraceV6, type TaskPlan, type VehicleStateV6 } from "../lib/cabinV6";
import { zhCN, type OccupantRole } from "../lib/i18n/zh-CN";

const samples = [
  "把空调调到22度，并导航去北京南站",
  "找沿途快充站并导航过去",
  "下雨了，把天窗关上并打开前挡除雾",
  "记住我喜欢24度，再告诉我当前电量",
];

const roleNotes: Record<OccupantRole, string> = {
  driver: "可执行导航、舒适与安全车身动作",
  front_passenger: "可读信息并调节舒适设备",
  rear_child: "设备写操作需监护授权",
  guest: "只读访问，写操作会被服务端拒绝",
};

function TraceReceipt({ trace }: { trace: AgentTraceV6 }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.025] p-3">
      <div className="flex items-center justify-between gap-2">
        <code className="text-xs text-cyan-200">{trace.name}</code>
        <span className={`rounded-full px-2 py-1 text-[10px] ${trace.status === "success" ? "bg-emerald-400/10 text-emerald-300" : "bg-rose-400/10 text-rose-300"}`}>{trace.status === "success" ? "执行成功" : "策略阻止"}</span>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">{domainLabels[trace.domain || "system"]} · {trace.policyCode || "—"} · 状态 v{trace.stateVersionBefore ?? "—"} → v{trace.stateVersionAfter ?? "—"}</p>
    </div>
  );
}

export default function MissionCockpit() {
  const [role, setRole] = useState<OccupantRole>("driver");
  const [sessionId, setSessionId] = useState("");
  const [input, setInput] = useState(samples[0]);
  const [plan, setPlan] = useState<TaskPlan | null>(null);
  const [vehicle, setVehicle] = useState<VehicleStateV6 | null>(null);
  const [traces, setTraces] = useState<AgentTraceV6[]>([]);
  const [answer, setAnswer] = useState("等待你下达跨域任务。系统会先展示执行计划，再进入服务端安全执行。 ");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState({ model: "—", turns: 0, tokens: 0, stateVersion: 1 });

  const createSession = useCallback(async (nextRole: OccupantRole) => {
    const response = await fetch(cabinApiUrl("/api/cabin/session"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: "default", occupantRole: nextRole }),
    });
    const data = await readJson<{ sessionId: string; vehicle: VehicleStateV6; stateVersion: number }>(response);
    setSessionId(data.sessionId);
    setVehicle(data.vehicle);
    setMeta((current) => ({ ...current, stateVersion: data.stateVersion }));
    localStorage.setItem("cabinguard-session-id", data.sessionId);
    localStorage.setItem("cabinguard-occupant-role", nextRole);
    return data.sessionId;
  }, []);

  useEffect(() => { void createSession(role).catch((cause) => setError(cause instanceof Error ? cause.message : "Python 服务未连接")); }, [createSession, role]);

  const execute = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true); setError(""); setTraces([]);
    try {
      const previewResponse = await fetch(cabinApiUrl("/api/cabin/plan"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const preview = await readJson<TaskPlan>(previewResponse);
      setPlan(preview);
      const activeSession = sessionId || await createSession(role);
      const response = await fetch(cabinApiUrl("/api/deepseek/agent"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, sessionId: activeSession, history: [] }) });
      const data = await readJson<AgentResponseV6>(response);
      if (data.plan) setPlan(data.plan); setVehicle(data.vehicle); setTraces(data.traces); setAnswer(data.message);
      setMeta({ model: data.model, turns: data.turns, tokens: data.totalTokens, stateVersion: data.stateVersion });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "执行失败");
      setAnswer("任务图已经可以独立预演；若模型执行失败，请检查 Python 服务与 DEEPSEEK_API_KEY。安全策略和场景仿真功能不依赖模型。 ");
    } finally { setBusy(false); }
  };

  const nodeTraces = useMemo(() => new Map(plan?.nodes.map((node) => [node.id, traces.filter((trace) => trace.taskId === node.id)]) ?? []), [plan, traces]);

  return (
    <main className="min-h-screen bg-[#050b16] text-slate-100">
      <V6Nav active="/mission" />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(14,165,233,.13),transparent_30%),radial-gradient(circle_at_80%_20%,rgba(139,92,246,.11),transparent_28%)]" />
      <div className="relative mx-auto max-w-[1680px] space-y-5 px-5 py-6 lg:px-8">
        <section className="grid gap-5 xl:grid-cols-[1.3fr_.7fr]">
          <div className="overflow-hidden rounded-[30px] border border-white/10 bg-[#091323]/90 p-6 shadow-2xl shadow-black/30">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div><p className="text-xs tracking-[0.2em] text-cyan-300">MISSION CONTROL / 任务驾驶舱</p><h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-white md:text-5xl">把一句话，变成一张<br /><span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-violet-400 bg-clip-text text-transparent">可解释、可阻止、可复盘</span>的任务图</h1><p className="mt-4 max-w-3xl text-sm leading-7 text-slate-400">统一助手负责理解目标；导航领域 Agent 处理外部世界任务；舒适与车身服务确定性执行。每一步先过 TaskPlan 白名单、乘员 ABAC 和 VSS 安全约束。</p></div>
              <div className={`rounded-2xl border px-4 py-3 text-xs ${usesExternalCabinApi ? "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-300" : "border-amber-400/20 bg-amber-400/[0.07] text-amber-300"}`}><span className="mr-2 inline-block h-2 w-2 rounded-full bg-current" />{usesExternalCabinApi ? "Python Core 已连接" : "请用一键启动器连接 Python"}</div>
            </div>
            <div className="mt-7 rounded-3xl border border-white/10 bg-black/20 p-3">
              <textarea value={input} onChange={(event) => setInput(event.target.value)} className="min-h-24 w-full resize-none bg-transparent p-3 text-base leading-7 text-white outline-none placeholder:text-slate-600" placeholder="例如：有点冷，调到22度，再找附近的火锅店并导航过去" />
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-3">
                <div className="flex flex-wrap gap-2">{samples.map((sample, index) => <button key={sample} onClick={() => setInput(sample)} className="rounded-xl bg-white/[0.05] px-3 py-2 text-xs text-slate-400 transition hover:bg-white/10 hover:text-white">场景 {index + 1}</button>)}</div>
                <button onClick={() => void execute()} disabled={busy} className="rounded-2xl bg-gradient-to-r from-blue-500 to-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-blue-500/20 transition hover:brightness-110 disabled:opacity-50">{busy ? "正在编译并执行…" : "预演任务图并执行"}</button>
              </div>
            </div>
            {error && <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-3 text-sm text-amber-200">{error}</div>}
          </div>
          <aside className="rounded-[30px] border border-white/10 bg-gradient-to-br from-[#0c1729] to-[#09111e] p-5">
            <p className="text-xs tracking-[0.18em] text-violet-300">OCCUPANT AUTHORITY / 乘员权限</p><h2 className="mt-2 text-xl font-semibold">谁在发起这次任务？</h2>
            <div className="mt-4 grid grid-cols-2 gap-2">{(Object.keys(zhCN.roles) as OccupantRole[]).map((item) => <button key={item} onClick={() => setRole(item)} className={`rounded-2xl border p-3 text-left transition ${role === item ? "border-violet-400/35 bg-violet-400/10" : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"}`}><strong className="text-sm">{zhCN.roles[item]}</strong><span className="mt-1 block text-[11px] leading-5 text-slate-500">{roleNotes[item]}</span></button>)}</div>
            <div className="mt-4 rounded-2xl bg-black/20 p-4"><p className="text-xs text-slate-500">当前会话边界</p><p className="mt-2 break-all font-mono text-xs text-slate-300">{sessionId || "正在创建…"}</p><p className="mt-3 text-xs text-slate-500">会话 ID 不是账户身份凭据；本演示通过服务端角色字段验证多乘员权限模型。</p></div>
          </aside>
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]">
          <div className="rounded-[30px] border border-white/10 bg-[#091323]/90 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs tracking-[0.18em] text-cyan-300">TRUSTED TASK PLAN / 可信任务图</p><h2 className="mt-2 text-xl font-semibold">{plan?.objective || "尚未生成任务图"}</h2></div><div className="flex gap-2 text-[11px]"><span className="rounded-full bg-white/[0.06] px-3 py-1.5">{plan?.nodes.length ?? 0} 个任务</span><span className="rounded-full bg-white/[0.06] px-3 py-1.5">{plan?.executionWaves.length ?? 0} 个执行波次</span>{plan?.requiresConfirmation && <span className="rounded-full bg-amber-400/10 px-3 py-1.5 text-amber-300">含高风险动作</span>}</div></div>
            <div className="mt-5 grid gap-3 md:grid-cols-2">{plan?.nodes.map((node, index) => { const receipts = nodeTraces.get(node.id) || []; const blocked = receipts.some((trace) => trace.status === "blocked"); const success = receipts.some((trace) => trace.status === "success"); return <article key={node.id} className={`relative overflow-hidden rounded-2xl border p-4 ${blocked ? "border-rose-400/20 bg-rose-400/[0.04]" : success ? "border-emerald-400/20 bg-emerald-400/[0.04]" : "border-white/[0.07] bg-white/[0.025]"}`}><div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-cyan-400 to-violet-500" /><div className="flex items-start justify-between gap-3"><div className="flex gap-3"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-white/[0.06] text-xs font-semibold text-cyan-200">{index + 1}</span><div><p className="text-[11px] text-cyan-300">{domainLabels[node.domain] || node.domain}</p><h3 className="mt-1 font-medium text-white">{node.title}</h3></div></div><span className={`rounded-full px-2 py-1 text-[10px] ${node.risk === "high" ? "bg-rose-400/10 text-rose-300" : node.risk === "medium" ? "bg-amber-400/10 text-amber-300" : "bg-emerald-400/10 text-emerald-300"}`}>{zhCN.risks[node.risk]}</span></div><p className="mt-3 text-xs leading-6 text-slate-400">{node.description}</p><div className="mt-3 flex flex-wrap gap-1.5">{node.allowedTools.map((tool) => <code key={tool} className="rounded-lg bg-black/25 px-2 py-1 text-[10px] text-slate-400">{tool}</code>)}{node.allowedTools.length === 0 && <span className="text-[10px] text-slate-600">零工具 · 仅澄清</span>}</div><p className="mt-3 text-[10px] text-slate-600">依赖：{node.dependencies.length ? node.dependencies.join("、") : "无"} · 权限：{node.permission}</p></article>; }) || <div className="col-span-2 grid min-h-56 place-items-center rounded-2xl border border-dashed border-white/10 text-sm text-slate-600">输入任务后，这里会显示可执行 DAG</div>}</div>
          </div>
          <div className="space-y-5">
            <section className="rounded-[30px] border border-white/10 bg-[#091323]/90 p-5"><p className="text-xs tracking-[0.18em] text-emerald-300">AGENT RESPONSE / 执行结果</p><p className="mt-4 min-h-24 text-base leading-8 text-slate-200">{answer}</p><div className="mt-4 grid grid-cols-4 gap-2 text-center">{[["模型", meta.model],["轮次", meta.turns],["Token", meta.tokens],["状态版本", `v${meta.stateVersion}`]].map(([label, value]) => <div key={label} className="rounded-xl bg-white/[0.035] p-2"><p className="truncate text-xs font-medium text-white">{value}</p><p className="mt-1 text-[10px] text-slate-600">{label}</p></div>)}</div><div className="mt-3 grid grid-cols-4 gap-2 text-center">{[["车速", vehicle ? `${vehicle.speed} km/h` : "—"],["电量", vehicle ? `${vehicle.battery}%` : "—"],["目标温度", vehicle ? `${vehicle.targetTemperature}℃` : "—"],["目的地", vehicle?.destination || "—"]].map(([label, value]) => <div key={label} className="min-w-0 rounded-xl border border-white/[0.06] p-2"><p className="truncate text-xs text-slate-300" title={String(value)}>{value}</p><p className="mt-1 text-[10px] text-slate-600">{label}</p></div>)}</div></section>
            <section className="rounded-[30px] border border-white/10 bg-[#091323]/90 p-5"><div className="flex items-center justify-between"><div><p className="text-xs tracking-[0.18em] text-violet-300">EXECUTION RECEIPTS / 执行回执</p><h2 className="mt-2 font-semibold">策略核与工具轨迹</h2></div><span className="rounded-full bg-white/[0.06] px-3 py-1 text-xs text-slate-400">{traces.length}</span></div><div className="mt-4 max-h-72 space-y-2 overflow-y-auto">{traces.map((trace) => <TraceReceipt key={trace.id} trace={trace} />)}{traces.length === 0 && <p className="py-8 text-center text-xs text-slate-600">执行后显示机器可读回执</p>}</div></section>
          </div>
        </section>
      </div>
    </main>
  );
}
