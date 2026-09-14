"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { cabinApiUrl } from "../lib/apiBase";

type ToolCapability = {
  name: string;
  category: string;
  permission: "direct" | "confirm" | "blocked";
  description: string;
};

type SignalCapability = {
  path: string;
  alias: string;
  label: string;
  value_type: string;
  access: string;
  permission: "direct" | "confirm" | "blocked";
  unit?: string;
  minimum?: number;
  maximum?: number;
};

type ConstraintCapability = {
  id: string;
  targetPattern: string;
  action: "reject" | "clamp";
  code: string;
  message: string;
  suggestion: string;
};

type GraphNode = { id: string; label: string; layer: string };

type CapabilityManifest = {
  version: string;
  agentCount: number;
  toolCount: number;
  signalCount: number;
  constraintCount: number;
  tools: ToolCapability[];
  signals: SignalCapability[];
  constraints: ConstraintCapability[];
  executionGraph: { nodes: GraphNode[]; edges: [string, string][] };
  integrations: Array<{ name: string; type: string; mode: "live" | "simulated" }>;
};

const permissionMeta = {
  direct: { label: "彩标 · 可直执", className: "border-cyan-400/25 bg-cyan-400/10 text-cyan-200" },
  confirm: { label: "灰标 · 需授权", className: "border-amber-400/25 bg-amber-400/10 text-amber-200" },
  blocked: { label: "黑标 · 禁止", className: "border-slate-500/30 bg-slate-800 text-slate-400" },
};

function Badge({ permission }: { permission: keyof typeof permissionMeta }) {
  const meta = permissionMeta[permission];
  return <span className={`rounded-full border px-2 py-1 text-[11px] ${meta.className}`}>{meta.label}</span>;
}

function Metric({ value, label, note }: { value: string | number; label: string; note: string }) {
  return <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-4"><p className="text-3xl font-semibold tracking-tight text-white">{value}</p><p className="mt-2 text-sm font-medium text-slate-200">{label}</p><p className="mt-1 text-xs text-slate-500">{note}</p></div>;
}

export default function SystemLab() {
  const [manifest, setManifest] = useState<CapabilityManifest | null>(null);
  const [error, setError] = useState("");
  const [toolFilter, setToolFilter] = useState("全部");

  useEffect(() => {
    const controller = new AbortController();
    fetch(cabinApiUrl("/api/cabin/capabilities"), { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`能力接口返回 ${response.status}`);
        return response.json() as Promise<CapabilityManifest>;
      })
      .then(setManifest)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "无法读取 Python 能力注册表");
      });
    return () => controller.abort();
  }, []);

  const categories = useMemo(
    () => ["全部", ...Array.from(new Set(manifest?.tools.map((tool) => tool.category) ?? []))],
    [manifest],
  );
  const tools = manifest?.tools.filter((tool) => toolFilter === "全部" || tool.category === toolFilter) ?? [];
  const edgeSet = new Set(manifest?.executionGraph.edges.map(([from, to]) => `${from}:${to}`) ?? []);

  return <main className="min-h-screen bg-[#070b14] text-slate-100">
    <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080d18]/95 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1720px] flex-wrap items-center justify-between gap-4 px-5 py-4 xl:px-8">
        <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-400 font-black text-slate-950">CG</span><div><div className="flex items-center gap-2"><h1 className="text-lg font-semibold">System Lab</h1><span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-1 text-xs text-violet-200">Architecture Truth</span></div><p className="mt-0.5 text-xs text-slate-500">由 Python 运行时注册表生成，不是静态功能海报</p></div></div>
        <nav className="flex flex-wrap items-center gap-2 text-sm"><Link href="/mission" className="rounded-lg px-3 py-2 text-cyan-300 hover:bg-cyan-400/10 hover:text-white">任务驾驶舱</Link><Link href="/agent-lab" className="rounded-lg px-3 py-2 text-slate-400 hover:bg-white/5 hover:text-white">经典 Agent 实验室</Link><Link href="/twin-lab" className="rounded-lg px-3 py-2 text-slate-400 hover:bg-white/5 hover:text-white">数字孪生</Link><Link href="/ops" className="rounded-lg px-3 py-2 text-slate-400 hover:bg-white/5 hover:text-white">证据中心</Link><Link href="/evaluation" className="rounded-lg px-3 py-2 text-slate-400 hover:bg-white/5 hover:text-white">可靠性评测</Link><span className={`rounded-lg border px-3 py-2 text-xs ${manifest ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300" : "border-amber-400/25 bg-amber-400/10 text-amber-300"}`}>{manifest ? `Python 注册表 · ${manifest.version}` : "正在连接 Python"}</span></nav>
      </div>
    </header>

    <div className="mx-auto max-w-[1720px] space-y-5 px-5 py-5 xl:px-8">
      {error && <section className="rounded-2xl border border-rose-400/25 bg-rose-500/10 p-4 text-sm text-rose-200"><p className="font-medium">无法读取真实能力清单：{error}</p><p className="mt-1 text-rose-300/70">请用 start_demo.py 同时启动 FastAPI 与 Next.js。当前页面不会用静态数字伪装后端能力。</p></section>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Metric value={manifest?.agentCount ?? "—"} label="协同 Agent" note="主编排 + 导航领域" />
        <Metric value={manifest?.toolCount ?? "—"} label="Registered Tools" note="严格 Pydantic 参数" />
        <Metric value={manifest?.signalCount ?? "—"} label="VSS Signals" note="读取与控制信号" />
        <Metric value={manifest?.constraintCount ?? "—"} label="Hard Constraints" note="拒绝或降级执行" />
        <Metric value={manifest?.integrations.filter((item) => item.mode === "live").length ?? "—"} label="Live Integrations" note="模型、地图、定位" />
        <Metric value={manifest?.executionGraph.nodes.length ?? "—"} label="Execution Nodes" note="端到端执行阶段" />
      </section>

      <section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5">
        <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-[0.18em] text-violet-300">Execution Graph</p><h2 className="mt-1 text-xl font-semibold">从用户目标到可审计执行回执</h2><p className="mt-2 text-sm text-slate-500">模型负责策略，注册表、授权和声明式约束掌握执行权；工具结果可回流给模型继续规划。</p></div><span className="rounded-full border border-emerald-400/20 bg-emerald-400/[0.07] px-3 py-1.5 text-xs text-emerald-300">循环式 Tool Calling · 最多 6 轮</span></div>
        <div className="mt-6 grid gap-2 lg:grid-cols-[repeat(13,minmax(0,1fr))]">
          {(manifest?.executionGraph.nodes ?? []).map((node, index, nodes) => <div key={node.id} className="contents"><div className="col-span-1 lg:col-span-1 lg:[&:nth-child(odd)]:col-span-1"><div className="h-full min-h-28 rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.07] to-white/[0.025] p-3"><span className="text-[10px] uppercase tracking-[0.14em] text-cyan-400">{node.layer}</span><p className="mt-3 text-sm font-medium leading-5 text-white">{node.label}</p><p className="mt-2 text-[11px] text-slate-600">{node.id}</p></div></div>{index < nodes.length - 1 && <div className="hidden items-center justify-center text-xl text-slate-600 lg:flex">{edgeSet.has(`${node.id}:${nodes[index + 1].id}`) ? "→" : "↪"}</div>}</div>)}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(380px,0.75fr)]">
        <section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">工具注册表</h2><p className="mt-1 text-sm text-slate-500">工具是机制，Agent 决定何时组合；权限标签由服务端能力元数据提供。</p></div><div className="flex flex-wrap gap-1 rounded-xl bg-black/20 p-1">{categories.map((category) => <button key={category} onClick={() => setToolFilter(category)} className={`rounded-lg px-3 py-1.5 text-xs ${toolFilter === category ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-200"}`}>{category}</button>)}</div></div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">{tools.map((tool) => <article key={tool.name} className="rounded-2xl border border-white/[0.08] bg-white/[0.035] p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-sm text-cyan-200">{tool.name}</p><p className="mt-1 text-xs text-slate-600">{tool.category}</p></div><Badge permission={tool.permission} /></div><p className="mt-3 text-sm leading-6 text-slate-400">{tool.description}</p></article>)}</div>
        </section>

        <div className="space-y-5">
          <section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5"><h2 className="text-lg font-semibold">外部集成边界</h2><p className="mt-1 text-sm text-slate-500">明确区分真实数据链路与车辆沙箱。</p><div className="mt-4 space-y-2">{manifest?.integrations.map((integration) => <div key={integration.name} className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-3"><div><p className="text-sm font-medium">{integration.name}</p><p className="mt-1 text-xs text-slate-500">{integration.type}</p></div><span className={`rounded-full px-2 py-1 text-[11px] ${integration.mode === "live" ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300"}`}>{integration.mode === "live" ? "LIVE" : "SANDBOX"}</span></div>)}</div></section>
          <section className="rounded-3xl border border-amber-400/15 bg-amber-400/[0.055] p-5"><p className="text-xs tracking-[0.16em] text-amber-300">真实能力边界</p><h2 className="mt-2 font-semibold">当前不是量产车控系统</h2><p className="mt-3 text-sm leading-6 text-amber-100/70">地点检索、道路路线、浏览器定位和模型规划可真实联网；车窗、座椅、灯光、空调和后备箱写入的是车辆沙箱状态，没有连接 CAN 总线、车机账户或量产权限系统。</p></section>
        </div>
      </div>

      <section className="rounded-3xl border border-white/10 bg-[#0b1220] p-5"><div><h2 className="text-lg font-semibold">Declarative Safety Rules</h2><p className="mt-1 text-sm text-slate-500">同一规则既用于能力解释，也由 Python 工具执行路径真实调用。</p></div><div className="mt-4 grid gap-3 lg:grid-cols-5">{manifest?.constraints.map((constraint) => <article key={constraint.id} className={`rounded-2xl border p-4 ${constraint.action === "reject" ? "border-rose-400/20 bg-rose-500/[0.06]" : "border-amber-400/20 bg-amber-500/[0.06]"}`}><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs text-slate-400">{constraint.id}</span><span className={`rounded px-2 py-1 text-[10px] font-semibold uppercase ${constraint.action === "reject" ? "bg-rose-400/15 text-rose-300" : "bg-amber-400/15 text-amber-300"}`}>{constraint.action}</span></div><p className="mt-3 text-sm font-medium leading-6 text-white">{constraint.message}</p><p className="mt-2 break-all font-mono text-[10px] leading-4 text-slate-600">{constraint.targetPattern}</p><p className="mt-3 text-xs leading-5 text-slate-500">建议：{constraint.suggestion}</p></article>)}</div></section>

      <section className="overflow-hidden rounded-3xl border border-white/10 bg-[#0b1220]"><div className="border-b border-white/10 p-5"><h2 className="text-lg font-semibold">Vehicle Signal Catalog</h2><p className="mt-1 text-sm text-slate-500">采用 VSS 风格的层级路径作为跨域语义层；当前路径映射为项目对齐层，并非 OEM 量产 DBC。</p></div><div className="max-h-[520px] overflow-auto"><table className="w-full min-w-[980px] text-left text-sm"><thead className="sticky top-0 bg-[#111827] text-xs uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-3">Signal</th><th className="px-5 py-3">VSS-aligned path</th><th className="px-5 py-3">Alias</th><th className="px-5 py-3">Type / Range</th><th className="px-5 py-3">Access</th><th className="px-5 py-3">Permission</th></tr></thead><tbody className="divide-y divide-white/[0.06]">{manifest?.signals.map((signal) => <tr key={signal.path} className="hover:bg-white/[0.025]"><td className="px-5 py-3 font-medium text-slate-200">{signal.label}</td><td className="px-5 py-3 font-mono text-xs text-cyan-200/75">{signal.path}</td><td className="px-5 py-3 font-mono text-xs text-slate-500">{signal.alias}</td><td className="px-5 py-3 text-xs text-slate-400">{signal.value_type}{signal.minimum !== undefined ? ` · ${signal.minimum}–${signal.maximum}${signal.unit ?? ""}` : ""}</td><td className="px-5 py-3 text-xs text-slate-400">{signal.access}</td><td className="px-5 py-3"><Badge permission={signal.permission} /></td></tr>)}</tbody></table></div></section>
    </div>
  </main>;
}
