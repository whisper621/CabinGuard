"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import V6Nav from "../components/V6Nav";
import { cabinApiUrl } from "../lib/apiBase";
import { eventLabels, readJson, type EvidenceEvent } from "../lib/cabinV6";

type EvidencePayload = { sessionId: string; occupantRole: string; stateVersion: number; eventCount: number; events: EvidenceEvent[] };

const tones: Record<string, string> = {
  "plan.created": "border-cyan-400/20 bg-cyan-400/[0.045] text-cyan-300",
  "policy.decision": "border-violet-400/20 bg-violet-400/[0.045] text-violet-300",
  "tool.receipt": "border-emerald-400/20 bg-emerald-400/[0.045] text-emerald-300",
  "signal.injected": "border-amber-400/20 bg-amber-400/[0.045] text-amber-300",
};

export default function OpsCenter() {
  const [sessionId, setSessionId] = useState("");
  const [data, setData] = useState<EvidencePayload | null>(null);
  const [filter, setFilter] = useState("全部");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadEvidence = useCallback(async (id: string) => {
    if (!id) return; setLoading(true); setError("");
    try { const response = await fetch(cabinApiUrl(`/api/cabin/evidence/${id}`), { cache: "no-store" }); setData(await readJson<EvidencePayload>(response)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "证据读取失败"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { const stored = localStorage.getItem("cabinguard-session-id") || ""; setSessionId(stored); if (stored) void loadEvidence(stored); }, [loadEvidence]);
  const eventTypes = useMemo(() => ["全部", ...Array.from(new Set(data?.events.map((event) => event.eventType) ?? []))], [data]);
  const visible = data?.events.filter((event) => filter === "全部" || event.eventType === filter) ?? [];
  const policyDenied = data?.events.filter((event) => event.eventType === "policy.decision" && event.payload.allowed === false).length ?? 0;
  const planCount = new Set(data?.events.map((event) => event.planId).filter(Boolean)).size;

  return <main className="min-h-screen bg-[#050b16] text-slate-100"><V6Nav active="/ops" /><div className="mx-auto max-w-[1680px] space-y-5 px-5 py-6 lg:px-8">
    <section className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]"><div className="rounded-[30px] border border-white/10 bg-[linear-gradient(120deg,#091728,#131329)] p-6"><p className="text-xs tracking-[0.2em] text-violet-300">EXECUTION TRACE / 执行追溯</p><h1 className="mt-3 text-3xl font-semibold md:text-5xl">每一次“已执行”，<br />都能回答<span className="text-violet-300">为什么、谁允许、状态如何变化</span></h1><p className="mt-4 max-w-4xl text-sm leading-7 text-slate-400">证据账本由服务端 SQLite 追加写入，界面不参与安全裁决。面试演示时可从用户原话一路追溯到任务节点、ABAC 策略、工具回执与状态版本。</p></div><aside className="rounded-[30px] border border-white/10 bg-[#091323] p-5"><p className="text-xs text-slate-500">当前演示会话</p><div className="mt-3 flex gap-2"><input value={sessionId} onChange={(event) => setSessionId(event.target.value)} className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs outline-none focus:border-violet-400/40" placeholder="请先在任务驾驶舱创建会话" /><button onClick={() => void loadEvidence(sessionId)} className="rounded-xl bg-violet-500 px-4 py-2 text-xs font-semibold text-white">{loading ? "刷新中" : "刷新证据"}</button></div>{!sessionId && <Link href="/mission" className="mt-4 block rounded-xl border border-cyan-400/20 bg-cyan-400/[0.05] px-4 py-3 text-center text-sm text-cyan-300">前往任务驾驶舱创建会话 →</Link>}<p className="mt-4 text-xs leading-6 text-slate-500">安全边界：演示会话 ID 不是生产身份认证；真实量产系统还需接入车机账户、设备证书与硬件安全模块。</p></aside></section>
    {error && <p className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3 text-sm text-rose-200">{error}</p>}
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[["证据事件", data?.eventCount ?? 0],["任务计划", planCount],["状态版本", `v${data?.stateVersion ?? "—"}`],["策略拒绝", policyDenied]].map(([label, value]) => <div key={label} className="rounded-2xl border border-white/[0.07] bg-[#091323] p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-3xl font-semibold text-white">{value}</p></div>)}</section>
    <section className="grid gap-5 xl:grid-cols-[.28fr_.72fr]"><aside className="rounded-[30px] border border-white/10 bg-[#091323] p-5"><p className="text-xs tracking-[0.18em] text-cyan-300">EVENT FILTER / 事件筛选</p><div className="mt-4 space-y-2">{eventTypes.map((type) => <button key={type} onClick={() => setFilter(type)} className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs ${filter === type ? "bg-white/10 text-white" : "text-slate-500 hover:bg-white/[0.05] hover:text-slate-300"}`}><span>{type === "全部" ? "全部事件" : eventLabels[type] || type}</span><span>{type === "全部" ? data?.eventCount ?? 0 : data?.events.filter((event) => event.eventType === type).length ?? 0}</span></button>)}</div><div className="mt-6 border-t border-white/[0.07] pt-5"><p className="text-xs text-slate-500">审计顺序</p><ol className="mt-3 space-y-3 text-xs text-slate-400"><li>1. 任务图限定最大能力范围</li><li>2. ABAC 判断乘员是否有权</li><li>3. 工具层执行 VSS 约束</li><li>4. 状态版本与回执写入账本</li></ol></div></aside>
      <div className="rounded-[30px] border border-white/10 bg-[#091323] p-5"><div className="flex items-center justify-between"><div><p className="text-xs tracking-[0.18em] text-violet-300">CAUSAL LEDGER / 执行证据链</p><h2 className="mt-2 text-xl font-semibold">最新事件在前</h2></div><span className="rounded-full bg-white/[0.06] px-3 py-1 text-xs text-slate-400">{visible.length} 条</span></div><div className="mt-5 max-h-[720px] space-y-3 overflow-y-auto pr-1">{visible.map((event) => <article key={event.id} className={`rounded-2xl border p-4 ${tones[event.eventType] || "border-white/[0.07] bg-white/[0.025] text-slate-300"}`}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold">{eventLabels[event.eventType] || event.eventType}</p><p className="mt-1 font-mono text-[10px] text-slate-600">{event.id}</p></div><div className="text-right text-[10px] text-slate-500"><p>状态 v{event.stateVersion}</p><p className="mt-1">{new Date(event.createdAt).toLocaleString("zh-CN", { hour12: false })}</p></div></div><div className="mt-3 flex flex-wrap gap-2 text-[10px] text-slate-500"><span className="rounded-lg bg-black/20 px-2 py-1">计划 {event.planId || "无"}</span><span className="rounded-lg bg-black/20 px-2 py-1">任务 {event.taskId || "系统事件"}</span></div><pre className="mt-3 max-h-44 overflow-auto rounded-xl bg-black/25 p-3 text-[10px] leading-5 text-slate-400">{JSON.stringify(event.payload, null, 2)}</pre></article>)}{visible.length === 0 && <div className="grid min-h-64 place-items-center rounded-2xl border border-dashed border-white/10 text-center text-sm text-slate-600"><p>尚无证据事件<br /><span className="mt-2 block text-xs">先在任务驾驶舱执行任务，或在场景仿真中注入信号</span></p></div>}</div></div>
    </section>
  </div></main>;
}
