import Link from "next/link";
import { zhCN } from "../lib/i18n/zh-CN";

const links = [
  ["/mission", zhCN.mission],
  ["/twin-lab", zhCN.twin],
  ["/ops", zhCN.ops],
  ["/evaluation", zhCN.evaluation],
  ["/system-lab", zhCN.architecture],
] as const;

export default function V6Nav({ active }: { active?: string }) {
  return (
    <header className="sticky top-0 z-[1000] border-b border-white/10 bg-[#07101f]/90 backdrop-blur-2xl">
      <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-4 px-5 py-3.5 lg:px-8">
        <Link href="/mission" className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-cyan-300 via-blue-500 to-violet-500 font-black text-[#06101d] shadow-lg shadow-blue-500/20">CG</span>
          <span>
            <strong className="block text-sm tracking-wide text-white">{zhCN.productShort}</strong>
            <span className="text-[11px] tracking-[0.12em] text-slate-500">可信座舱协同智能体 · v0.6</span>
          </span>
        </Link>
        <nav aria-label="CabinGuard 项目导航" className="flex max-w-full gap-1 overflow-x-auto rounded-2xl border border-white/[0.07] bg-white/[0.035] p-1 text-xs">
          {links.map(([href, label]) => (
            <Link key={href} href={href} aria-current={active === href ? "page" : undefined} className={`whitespace-nowrap rounded-xl px-3 py-2 transition ${active === href ? "bg-white/10 text-cyan-200" : "text-slate-400 hover:bg-white/[0.06] hover:text-white"}`}>{label}</Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
