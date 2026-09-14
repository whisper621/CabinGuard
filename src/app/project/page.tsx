import ProductNav from "../components/ProductNav";
import SystemLab from "../system-lab/SystemLab";

const productFlow = [
  ["01", "自然交互", "用户以中文文字或语音表达跨域目标，只面对一个统一座舱助手。"],
  ["02", "任务编排", "主智能体生成带依赖、风险、权限和工具白名单的 TaskPlan。"],
  ["03", "安全裁决", "ABAC 与车辆硬约束在 Python 服务端判定，模型不能绕过。"],
  ["04", "确定性执行", "导航、空调、车窗、座椅、灯光和记忆通过受控 Tool/API 执行。"],
  ["05", "证据闭环", "计划、裁决、回执、状态版本进入 SQLite 账本并可追溯评测。"],
] as const;

const boundaries = [
  ["真实联网", "浏览器定位、OpenStreetMap 地点检索、OSRM 道路算路、可选大模型规划。"],
  ["车辆沙箱", "座舱控制写入可观测的数字车辆状态，未连接真实 CAN 总线与量产 ECU。"],
  ["演示身份", "驾驶员、乘客、儿童、访客用于展示 ABAC；生产版仍需车机账户、设备证书与 HSM。"],
] as const;

export default function ProjectPage() {
  return <main className="min-h-screen bg-[#070b14] text-slate-100">
    <ProductNav active="/project" status={<span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2.5 py-1 text-[11px] font-medium text-cyan-200">v0.6 产品档案</span>} />
    <div className="mx-auto max-w-[1720px] space-y-6 px-5 py-7 xl:px-8">
      <section className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
        <div className="rounded-[34px] border border-white/10 bg-[radial-gradient(circle_at_82%_18%,rgba(34,211,238,.15),transparent_32%),linear-gradient(120deg,#09192b,#101126)] p-7 md:p-10"><p className="text-xs tracking-[0.22em] text-cyan-300">PRODUCT STORY / 项目说明</p><h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight md:text-6xl">一个入口完成跨域任务，<br /><span className="text-cyan-300">每次执行都有安全依据</span></h1><p className="mt-6 max-w-4xl text-base leading-8 text-slate-400">CabinGuard 面向复杂驾驶场景，将真实导航、座舱控制、角色权限、车辆状态和可靠性评测连接成一个可运行闭环。用户体验是一个主智能体，系统内部采用主编排器、导航领域智能体与确定性工具层协作。</p></div>
        <aside className="grid grid-cols-2 gap-3">{[["2", "智能体边界", "主编排 + 导航领域"], ["5", "业务领域", "导航 / 舒适 / 安全 / 记忆 / 感知"], ["14", "注册工具", "严格参数与工具白名单"], ["25", "车辆信号", "VSS 风格语义层"], ["24", "组合场景", "确定性安全契约"], ["130", "自动化测试", "39 前端 + 91 Python"]].map(([value, label, note]) => <div key={label} className="rounded-2xl border border-white/[0.08] bg-[#0b1423] p-4"><p className="text-3xl font-semibold text-white">{value}</p><p className="mt-2 text-sm font-medium text-cyan-200">{label}</p><p className="mt-1 text-xs leading-5 text-slate-500">{note}</p></div>)}</aside>
      </section>

      <section className="rounded-[30px] border border-white/10 bg-[#0b1220] p-6"><div><p className="text-xs tracking-[0.18em] text-violet-300">END-TO-END LOOP / 产品闭环</p><h2 className="mt-2 text-2xl font-semibold">从用户目标到可审计结果</h2></div><div className="mt-6 grid gap-3 lg:grid-cols-5">{productFlow.map(([step, title, description]) => <article key={step} className="rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4"><span className="text-xs font-semibold text-cyan-300">{step}</span><h3 className="mt-3 font-semibold text-white">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-500">{description}</p></article>)}</div></section>

      <section className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]"><div className="rounded-[30px] border border-emerald-400/15 bg-emerald-400/[0.035] p-6"><p className="text-xs tracking-[0.18em] text-emerald-300">CORE VALUE / 核心价值</p><h2 className="mt-3 text-2xl font-semibold">不是“能回答”，而是“能可靠完成”</h2><p className="mt-4 text-sm leading-7 text-slate-400">项目的差异点不是堆叠 Agent 数量，而是把跨域规划、实时车辆上下文、安全执行权、状态并发控制和可量化评测放进同一系统。面试可现场证明正常任务、缺失能力、必要澄清与越权拦截。</p></div><div className="rounded-[30px] border border-amber-400/15 bg-amber-400/[0.035] p-6"><p className="text-xs tracking-[0.18em] text-amber-300">TRUTH BOUNDARY / 真实边界</p><div className="mt-4 grid gap-3 md:grid-cols-3">{boundaries.map(([title, description]) => <article key={title} className="rounded-2xl border border-white/[0.07] bg-black/10 p-4"><h3 className="font-medium text-amber-100">{title}</h3><p className="mt-2 text-xs leading-6 text-slate-500">{description}</p></article>)}</div></div></section>
    </div>

    <section id="architecture" className="border-t border-white/10"><div className="mx-auto max-w-[1720px] px-5 pt-10 xl:px-8"><p className="text-xs tracking-[0.18em] text-violet-300">RUNTIME ARCHITECTURE / 运行时架构</p><h2 className="mt-2 text-3xl font-semibold">以 Python 能力注册表为准的技术全景</h2><p className="mt-3 max-w-3xl text-sm leading-7 text-slate-500">下方数据直接读取运行时接口，不用静态海报夸大能力；服务未启动时会明确显示不可用。</p></div><SystemLab /></section>
  </main>;
}
