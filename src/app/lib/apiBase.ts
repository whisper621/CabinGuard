const configuredApiBase = process.env.NEXT_PUBLIC_CABINGUARD_API_URL
  ?.trim()
  .replace(/\/$/, "") ?? "";

/** Route requests to FastAPI when configured, otherwise keep the built-in Next.js API. */
export const cabinApiUrl = (path: string) =>
  `${configuredApiBase}${path.startsWith("/") ? path : `/${path}`}`;
