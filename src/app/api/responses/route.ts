import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { consumeRateLimit } from '../../lib/cabinSession';

// Optional proxy used only by the Realtime experiment's output moderation.
export async function POST(req: NextRequest) {
  if (process.env.ENABLE_REALTIME_OUTPUT_GUARDRAIL !== 'true') {
    return NextResponse.json(
      { error: 'Realtime output guardrail is disabled' },
      { status: 404 },
    );
  }
  if (!process.env.OPENAI_API_KEY) {
    return NextResponse.json({ error: 'OPENAI_API_KEY is not configured' }, { status: 503 });
  }
  const contentLength = Number(req.headers.get('content-length') || 0);
  if (contentLength > 64 * 1024) {
    return NextResponse.json({ error: 'Request body is too large' }, { status: 413 });
  }
  const forwardedFor = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim();
  const rate = consumeRateLimit(`realtime-guardrail:${forwardedFor || 'local-anonymous'}`);
  if (!rate.allowed) {
    return NextResponse.json(
      { error: 'Request rate limit exceeded' },
      { status: 429, headers: { 'Retry-After': String(rate.retryAfterSeconds) } },
    );
  }
  const body = await req.json();

  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

  if (body.text?.format?.type === 'json_schema') {
    return await structuredResponse(openai, body);
  } else {
    return await textResponse(openai, body);
  }
}

async function structuredResponse(openai: OpenAI, body: any) {
  try {
    const response = await openai.responses.parse({
      ...(body as any),
      stream: false,
    });

    return NextResponse.json(response);
  } catch (err: any) {
    console.error('responses proxy error', err);
    return NextResponse.json({ error: 'failed' }, { status: 500 }); 
  }
}

async function textResponse(openai: OpenAI, body: any) {
  try {
    const response = await openai.responses.create({
      ...(body as any),
      stream: false,
    });

    return NextResponse.json(response);
  } catch (err: any) {
    console.error('responses proxy error', err);
    return NextResponse.json({ error: 'failed' }, { status: 500 });
  }
}
