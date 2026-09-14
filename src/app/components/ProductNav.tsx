import type { ReactNode } from "react";
import Link from "next/link";

const links = [
  { href: "/", label: "智能座舱" },
  { href: "/validation", label: "验证中心" },
  { href: "/project", label: "项目说明" },
] as const;

export default function ProductNav({
  active,
  status,
  actions,
}: {
  active: "/" | "/validation" | "/project";
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="sticky top-0 z-[1001] border-b border-white/10 bg-[#07101f]/95 backdrop-blur-2xl">
      <div className="mx-auto flex max-w-[1720px] flex-wrap items-center justify-between gap-4 px-5 py-3.5 xl:px-8">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-cyan-300 via-blue-500 to-violet-500 font-black text-[#06101d] shadow-lg shadow-blue-500/20">CG</span>
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <strong className="text-base tracking-tight text-white">CabinGuard</strong>
              {status}
            </span>
            <span className="block truncate text-xs text-slate-500">可信座舱协同智能体 · 真实道路导航与安全执行</span>
          </span>
        </Link>
        <div className="flex max-w-full items-center gap-2 overflow-x-auto">
          <nav aria-label="CabinGuard 主导航" className="flex gap-1 rounded-2xl border border-white/[0.07] bg-white/[0.035] p-1 text-sm">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active === link.href ? "page" : undefined}
                className={`whitespace-nowrap rounded-xl px-3.5 py-2 transition ${active === link.href ? "bg-white/10 text-cyan-200" : "text-slate-400 hover:bg-white/[0.06] hover:text-white"}`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
          {actions}
        </div>
      </div>
    </header>
  );
}
