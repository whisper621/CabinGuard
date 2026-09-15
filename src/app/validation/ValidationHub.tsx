"use client";

import { useState } from "react";
import Link from "next/link";
import ProductNav from "../components/ProductNav";
import EvaluationLab from "../evaluation/EvaluationLab";
import OpsCenter from "../ops/OpsCenter";
import TwinLab from "../twin-lab/TwinLab";

export type ValidationTab = "scenario" | "trace" | "evaluation";

const tabs: Array<{ id: ValidationTab; label: string; eyebrow: string; description: string }> = [
  { id: "scenario", label: "① 车辆环境设置", eyebrow: "SIGNALS", description: "给当前演示会话注入车速、天气、电量等车辆信号，构造可复现测试条件。" },
  { id: "trace", label: "② 为什么执行/拦截", eyebrow: "EVIDENCE", description: "按任务图、策略裁决、工具回执和状态版本解释一次结果为什么发生。" },
  { id: "evaluation", label: "③ 批量测试报告", eyebrow: "EVALUATION", description: "运行确定性契约与模型轨迹，衡量正确率、一致性和具体失败原因。" },
];

export default function ValidationHub({ initialTab }: { initialTab: ValidationTab }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const selectTab = (tab: ValidationTab) => {
    setActiveTab(tab);
    window.history.replaceState(null, "", `/validation?tab=${tab}`);
  };

  return <main className="min-h-screen bg-[#050b16] text-slate-100">
    <ProductNav active="/validation" status={<span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-2.5 py-1 text-[11px] font-medium text-violet-200">验证工作台</span>} />
    <section className="mx-auto max-w-[1680px] px-5 pt-6 lg:px-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-amber-400/15 bg-amber-400/[0.05] p-4"><div><p className="text-sm font-medium text-amber-100">这是研发与面试验证工具，不是驾驶员日常操作页</p><p className="mt-1 text-xs leading-5 text-slate-500">推荐流程：设置车辆环境 → 返回智能座舱下达任务 → 回到这里解释结果或运行批量评测。当前会话会自动续接，不再因页面切换被重置。</p></div><Link href="/" className="rounded-xl bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-400/15">返回智能座舱执行任务 →</Link></div>
      <div className="grid gap-3 lg:grid-cols-3">{tabs.map((tab) => <button key={tab.id} onClick={() => selectTab(tab.id)} className={`rounded-2xl border p-4 text-left transition ${activeTab === tab.id ? "border-cyan-400/30 bg-cyan-400/[0.08] shadow-lg shadow-cyan-950/20" : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"}`}><div className="flex items-center justify-between gap-3"><strong className={activeTab === tab.id ? "text-cyan-200" : "text-slate-200"}>{tab.label}</strong><span className="text-[10px] tracking-[0.16em] text-slate-600">{tab.eyebrow}</span></div><p className="mt-2 text-xs leading-5 text-slate-500">{tab.description}</p></button>)}</div>
    </section>
    {activeTab === "scenario" && <TwinLab />}
    {activeTab === "trace" && <OpsCenter />}
    {activeTab === "evaluation" && <EvaluationLab />}
  </main>;
}
