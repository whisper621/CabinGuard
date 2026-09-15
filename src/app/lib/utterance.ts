export function appendSpeechSegment(existing: string, segment: string): string {
  const prefix = existing.trim();
  const next = segment.trim();
  if (!next) return prefix;
  if (!prefix) return next;
  if (prefix.endsWith(next)) return prefix;
  if (next.startsWith(prefix)) return next;
  const separator = /[，。；！？,.!?;]$/.test(prefix) ? "" : "，";
  return `${prefix}${separator}${next}`;
}
