import { Suspense } from "react";
import Link from "next/link";
import App from "../App";
import { EventProvider } from "../contexts/EventContext";
import { TranscriptProvider } from "../contexts/TranscriptContext";

export const dynamic = "force-dynamic";

export default function RealtimePage() {
  if (!process.env.OPENAI_API_KEY) {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 p-6 text-slate-900">
        <section className="max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/60">
          <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">需要配置</span>
          <h1 className="mt-4 text-2xl font-semibold">Realtime 语音 Agent 尚未启用</h1>
          <p className="mt-3 leading-7 text-slate-600">本地产品演示可以直接使用。若要体验真实模型驱动的语音和工具调用，请在项目根目录创建 <code className="rounded bg-slate-100 px-1.5 py-1 text-sm">.env.local</code>，配置 <code className="rounded bg-slate-100 px-1.5 py-1 text-sm">OPENAI_API_KEY</code> 后重启服务。</p>
          <Link href="/" className="mt-6 inline-flex rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">返回本地演示</Link>
        </section>
      </main>
    );
  }

  return (
    <Suspense fallback={<div className="p-8 text-slate-600">正在加载 Realtime Agent…</div>}>
      <TranscriptProvider>
        <EventProvider>
          <App />
        </EventProvider>
      </TranscriptProvider>
    </Suspense>
  );
}
