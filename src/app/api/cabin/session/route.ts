import { NextRequest, NextResponse } from "next/server";
import {
  consumeRateLimit,
  createCabinSession,
  isCabinScenario,
  sessionTtlSeconds,
} from "../../../lib/cabinSession";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const forwardedFor = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const rate = consumeRateLimit(`session:${forwardedFor || "local-anonymous"}`);
  if (!rate.allowed) {
    return NextResponse.json(
      { error: { code: "rate_limited", message: "会话创建过于频繁，请稍后再试" } },
      { status: 429, headers: { "Retry-After": String(rate.retryAfterSeconds) } },
    );
  }

  const body = await req.json().catch(() => ({})) as { scenario?: unknown };
  const scenario = body.scenario === undefined ? "default" : body.scenario;

  if (!isCabinScenario(scenario)) {
    return NextResponse.json(
      { error: { code: "invalid_scenario", message: "scenario must be default, rain, or moving" } },
      { status: 400 },
    );
  }

  const session = createCabinSession(scenario);
  return NextResponse.json({
    sessionId: session.id,
    scenario: session.scenario,
    vehicle: session.vehicle,
    expiresInSeconds: sessionTtlSeconds,
  });
}
