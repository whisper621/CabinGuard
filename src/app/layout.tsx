import type { Metadata } from "next";
import "./globals.css";
import "./lib/envSetup";

export const metadata: Metadata = {
  title: "CabinGuard 可信座舱任务 Agent",
  description: "以智能座舱为首个验证场景、具备服务端安全约束的可信任务 Agent。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`antialiased`}>{children}</body>
    </html>
  );
}
