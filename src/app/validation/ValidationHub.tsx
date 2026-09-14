"use client";

import { useState } from "react";
import ProductNav from "../components/ProductNav";
import EvaluationLab from "../evaluation/EvaluationLab";
import OpsCenter from "../ops/OpsCenter";
import TwinLab from "../twin-lab/TwinLab";

export type ValidationTab = "scenario" | "trace" | "evaluation";

const tabs: Array<{ id: ValidationTab; label: string; eyebrow: string; description: string }> = [
  { id: "scenario", label: "场景仿真", eyebrow: "SIGNALS", description: "注入车速、天气、电量等车辆事件，验证动态环境中的行为边界。" },
  { id: "trace", label: "执行追溯", eyebrow: "EVIDENCE", description: "按任务图、策略裁决、工具回执和状态版本复核每一次执行。" },
  { id: "evaluation", label: "可靠性评测", eyebrow: "EVALUATION", description: "运行确定性契约与多轮模型轨迹，衡量正确率、一致性和失败原因。" },
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
      <div className="grid gap-3 lg:grid-cols-3">{tabs.map((tab) => <button key={tab.id} onClick={() => selectTab(tab.id)} className={`rounded-2xl border p-4 text-left transition ${activeTab === tab.id ? "border-cyan-400/30 bg-cyan-400/[0.08] shadow-lg shadow-cyan-950/20" : "border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.05]"}`}><div className="flex items-center justify-between gap-3"><strong className={activeTab === tab.id ? "text-cyan-200" : "text-slate-200"}>{tab.label}</strong><span className="text-[10px] tracking-[0.16em] text-slate-600">{tab.eyebrow}</span></div><p className="mt-2 text-xs leading-5 text-slate-500">{tab.description}</p></button>)}</div>
    </section>
    {activeTab === "scenario" && <TwinLab />}
    {activeTab === "trace" && <OpsCenter />}
    {activeTab === "evaluation" && <EvaluationLab />}
  </main>;
}
