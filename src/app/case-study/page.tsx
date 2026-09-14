import Link from "next/link";

const metrics = [
  { value: "7", label: "能力域", note: "导航 / 补能 / HVAC / 车身 / 座椅 / 灯光 / 记忆" },
  { value: "14", label: "注册工具", note: "运行时清单，不是静态展示" },
  { value: "75", label: "Python 测试", note: "安全规则与执行器进入 CI" },
  { value: "15", label: "模型行为用例", note: "工具链、状态、澄清与越权" },
];

const decisions = [
  {
    title: "模型规划，应用授权",
    problem: "Prompt 不能保证模型永远遵守安全要求。",
    choice: "模型只建议工具调用；服务端校验参数、读取前置、环境风险和用户授权。",
    evidence: "非法参数、降雨、高速未确认、行驶中开后备箱和越权导航均有确定性测试。",
  },
  {
    title: "稳定演示 + 开放 Agent",
    problem: "完全依赖模型会让演示受网络和随机性影响，固定流程又无法展示自主规划。",
    choice: "首页提供本地规则回退，Agent Lab 真实运行 DeepSeek 多轮 Tool Calling。",
    evidence: "同一业务目标可在稳定链路复现，也可查看模型轮次、Token 和完整 Trace。",
  },
  {
    title: "搜索不等于导航授权",
    problem: "推荐候选站和启动导航是两个不同副作用。",
    choice: "导航必须由用户明确提出，且目的地来自本轮成功搜索结果。",
    evidence: "搜索-only 与搜索并导航被拆成独立评测用例。",
  },
];

const roadmap = [
  ["当前 v0.5", "真实地点与道路服务、25 个 VSS 对齐信号、声明式约束、会话偏好与行程记忆"],
  ["下一阶段", "WebSocket 信号流、异步动作回执、幂等、离线语音与持久化审计"],
  ["真实接入前", "用户/车辆身份、权限分级、车端签名、弱网降级与合规验证"],
];

export default function CaseStudyPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-500 font-bold">CG</span>
            <div><p className="font-semibold">CabinGuard Case Study</p><p className="text-xs text-slate-400">问题、取舍、证据与边界</p></div>
          </div>
          <nav className="flex flex-wrap gap-2 text-sm">
            <Link className="rounded-lg border border-white/15 px-3 py-2 hover:bg-white/10" href="/">产品演示</Link>
            <Link className="rounded-lg border border-white/15 px-3 py-2 hover:bg-white/10" href="/agent-lab">Agent Lab</Link>
            <Link className="rounded-lg border border-violet-300/30 px-3 py-2 text-violet-200 hover:bg-violet-300/10" href="/system-lab">系统架构</Link>
            <Link className="rounded-lg bg-blue-500 px-3 py-2 font-medium text-white hover:bg-blue-400" href="/evaluation">评测证据</Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-5 py-16">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-blue-400">Trusted cockpit task agent</p>
        <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight sm:text-6xl">从“听懂一句话”升级为<br />“安全完成一个任务”</h1>
        <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-300">CabinGuard 验证一个核心假设：当座舱 Agent 主动读取环境、澄清模糊意图、在高风险动作前获得授权，并用工具结果证明完成，用户才有理由把跨系统任务交给它。</p>

        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/5 p-5">
              <p className="text-4xl font-semibold text-white">{metric.value}</p>
              <p className="mt-2 font-medium">{metric.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">{metric.note}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-white/10 bg-white/[0.03]">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 lg:grid-cols-[0.8fr_1.2fr]">
          <div><p className="text-sm font-semibold text-amber-300">产品问题</p><h2 className="mt-3 text-3xl font-semibold">错误不只发生在“理解”</h2></div>
          <div className="grid gap-3 sm:grid-cols-3">
            {["模糊意图被直接猜测", "忽略车速、天气等上下文", "工具失败却反馈已经完成"].map((item, index) => (
              <div key={item} className="rounded-2xl border border-amber-300/20 bg-amber-300/5 p-5">
                <p className="text-xs text-amber-300">风险 0{index + 1}</p><p className="mt-3 leading-6">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-14">
        <p className="text-sm font-semibold text-blue-400">关键决策</p>
        <h2 className="mt-3 text-3xl font-semibold">每个设计都对应一个可验证风险</h2>
        <div className="mt-8 space-y-4">
          {decisions.map((decision, index) => (
            <article key={decision.title} className="grid gap-5 rounded-2xl border border-white/10 bg-white/5 p-6 md:grid-cols-[72px_1fr_1fr]">
              <p className="text-3xl font-semibold text-blue-400">0{index + 1}</p>
              <div><h3 className="text-xl font-semibold">{decision.title}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{decision.problem}</p></div>
              <div><p className="text-sm leading-6 text-slate-200">{decision.choice}</p><p className="mt-3 text-xs leading-5 text-emerald-300">证据：{decision.evidence}</p></div>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-white/10 bg-gradient-to-r from-blue-950/60 to-cyan-950/30">
        <div className="mx-auto max-w-6xl px-5 py-14">
          <p className="text-sm font-semibold text-cyan-300">信任架构</p>
          <div className="mt-6 grid items-center gap-2 text-center md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr]">
            {[
              ["用户目标", "自然语言与明确授权"],
              ["LLM 规划", "理解意图、选择工具"],
              ["可信执行器", "参数、状态、安全规则"],
              ["可核验反馈", "状态、Trace、失败原因"],
            ].map(([title, note], index) => (
              <div key={title} className="contents">
                <div className="rounded-2xl border border-cyan-300/20 bg-slate-950/50 p-5"><p className="font-semibold">{title}</p><p className="mt-2 text-xs text-slate-400">{note}</p></div>
                {index < 3 && <span className="hidden text-cyan-400 md:block">→</span>}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-5 py-14 lg:grid-cols-2">
        <div>
          <p className="text-sm font-semibold text-emerald-300">验证方式</p>
          <h2 className="mt-3 text-3xl font-semibold">规则确定性与模型非确定性分层测试</h2>
          <ul className="mt-6 space-y-3 text-sm leading-6 text-slate-300">
            <li className="rounded-xl border border-white/10 p-4"><strong className="text-white">CI：</strong>75 条 Python 测试，覆盖确认、参数、VSS 约束、会话记忆、TTL、限流和导航授权。</li>
            <li className="rounded-xl border border-white/10 p-4"><strong className="text-white">Guarded live eval：</strong>15 类真实模型用例，记录有序工具链、状态、Token、轮次、延迟和失败原因。</li>
            <li className="rounded-xl border border-white/10 p-4"><strong className="text-white">可观测：</strong>所有工具输入、输出和 blocked/success 状态在 Agent Lab 中可展开检查。</li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold text-violet-300">产品路线</p>
          <div className="mt-6 space-y-3">
            {roadmap.map(([phase, content]) => (
              <div key={phase} className="rounded-xl border border-white/10 bg-white/5 p-5"><p className="text-sm font-semibold text-violet-300">{phase}</p><p className="mt-2 text-sm leading-6 text-slate-300">{content}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-16">
        <div className="rounded-3xl border border-red-300/20 bg-red-300/5 p-7">
          <p className="text-sm font-semibold text-red-300">明确边界</p>
          <p className="mt-3 leading-7 text-slate-300">当前真实联网能力包括 DeepSeek 规划、浏览器定位、OpenStreetMap 地点检索与 OSRM 道路算路；天气、充电站目录和车辆执行仍是沙箱数据。系统没有连接 CAN 总线、OEM 账户、量产权限或车端签名，因此证明的是 Agent 产品策略、跨域编排、安全边界和评测方法，不代表生产级车辆控制。</p>
        </div>
      </section>
    </main>
  );
}
