import { NextResponse } from "next/server";
import { ProxyAgent, request } from "undici";
import { consumeRateLimit } from "../../lib/cabinSession";

export const runtime = "nodejs";

type ClientSecretResponse = {
  value?: string;
  expires_at?: number;
  session?: { model?: string };
  error?: { message?: string; type?: string; code?: string | null };
};

export async function GET(req: Request) {
  if (!process.env.OPENAI_API_KEY) {
    return NextResponse.json(
      { error: "OPENAI_API_KEY is not configured" },
      { status: 503 },
    );
  }

  const forwardedFor = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const rate = consumeRateLimit(`realtime:${forwardedFor || "local-anonymous"}`);
  if (!rate.allowed) {
    return NextResponse.json(
      { error: "Realtime 会话创建过于频繁，请稍后再试" },
      { status: 429, headers: { "Retry-After": String(rate.retryAfterSeconds) } },
    );
  }

  try {
    const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
    const dispatcher = proxyUrl ? new ProxyAgent(proxyUrl) : undefined;
    const response = await request(
      "https://api.openai.com/v1/realtime/client_secrets",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session: {
            type: "realtime",
            model: "gpt-realtime-2.1",
          },
        }),
        dispatcher,
        headersTimeout: 15_000,
        bodyTimeout: 30_000,
      },
    );
    const data = (await response.body.json()) as ClientSecretResponse;

    if (response.statusCode < 200 || response.statusCode >= 300 || !data.value) {
      return NextResponse.json(
        { error: data.error ?? { message: "Unable to create Realtime client secret" } },
        { status: response.statusCode },
      );
    }

    return NextResponse.json({
      client_secret: {
        value: data.value,
        expires_at: data.expires_at,
      },
      model: data.session?.model ?? "gpt-realtime-2.1",
    });
  } catch (error) {
    console.error("Error in /api/session:", error);
    return NextResponse.json(
      { error: "Unable to reach the Realtime API" },
      { status: 502 },
    );
  }
}
