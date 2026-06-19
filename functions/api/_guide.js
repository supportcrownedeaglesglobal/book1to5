export const SYSTEM_RULES = [
  "You are a gentle reading guide for the book series \"Behold My Messenger\".",
  "Use ONLY the CONTEXT excerpts below. Never use outside knowledge, never invent teaching or quotes.",
  "Every Bible reference you give MUST be King James Version (KJV) only.",
  "If the answer is not in the excerpts, say so plainly and point to what the books DO cover.",
  "Be warm and concise. This is spiritual encouragement, NOT medical, legal, or financial advice.",
  "If the reader signals crisis or self-harm, respond with compassion and gently encourage them to reach out to a trusted person, pastor, professional, or local emergency services.",
  "End by guiding them toward a concrete next chapter to listen to.",
  "Reply in JSON only: {\"reply\": string, \"chapters\": [{\"id\":string}], \"plan\": [{\"id\":string,\"why\":string}]}.",
  "Only use chapter ids that appear in CONTEXT.",
].join("\n");

function contextBlock(retrieved) {
  return retrieved.map(r =>
    `--- id:${r.id} | Book ${r.book} | ${r.title}\n${r.excerpt}`).join("\n\n");
}

export function buildMessages({ message, history = [], retrieved = [] }) {
  const system = `${SYSTEM_RULES}\n\nCONTEXT (the only material you may use):\n${contextBlock(retrieved)}`;
  return [{ role: "system", content: system },
          ...history.slice(-8).map(h => ({ role: h.role, content: String(h.content) })),
          { role: "user", content: String(message) }];
}

export function shapeReply(modelText, knownIds, chapterMap) {
  let data = null;
  if (modelText && typeof modelText === "object") {
    data = modelText;                                    // Workers AI sometimes returns an already-parsed JSON object
  } else {
    try { const m = String(modelText).match(/\{[\s\S]*\}/); if (m) data = JSON.parse(m[0]); } catch { /* fall through */ }
  }
  if (!data || typeof data.reply !== "string") {
    const txt = typeof modelText === "string" ? modelText.trim() : "";
    return { reply: txt || "I'm sorry, I couldn't form a reply just now — please try rephrasing.", chapters: [], plan: [] };
  }
  const resolve = (id) => { const c = chapterMap[id]; return c ? { id, book: c.book, title: c.title, url: c.url } : null; };
  const chapters = (data.chapters || []).map(x => x && x.id).filter(id => knownIds.has(id)).map(resolve).filter(Boolean);
  const plan = (data.plan || []).filter(p => p && knownIds.has(p.id))
      .map(p => { const c = chapterMap[p.id]; return { id: p.id, title: c?.title || p.id, url: c?.url || "", why: String(p.why || "") }; });
  return { reply: data.reply.trim(), chapters, plan };
}

export async function checkRate(kv, key, rate, now) {
  // KV is eventually-consistent and has no atomic increment, so this window
  // counter is best-effort: a burst of simultaneous requests may slip a few
  // over the per-window cap. The per-DAY cap below is the hard cost backstop.
  const t = now ?? Date.now();
  const win = Math.floor(t / 1000 / rate.windowSec);
  const day = Math.floor(t / 1000 / 86400);
  const wk = `w:${key}:${win}`, dk = `d:${key}:${day}`;
  const wc = parseInt(await kv.get(wk) || "0", 10);
  const dc = parseInt(await kv.get(dk) || "0", 10);
  if (wc >= rate.maxPerWindow || dc >= rate.dailyMax) return { allowed: false };
  await kv.put(wk, String(wc + 1), { expirationTtl: rate.windowSec + 5 });
  await kv.put(dk, String(dc + 1), { expirationTtl: 86400 + 60 });
  return { allowed: true };
}

export async function verifyTurnstile(secret, token, ip, fetchImpl = fetch) {
  if (!token) return false;
  const body = new URLSearchParams({ secret, response: token });
  if (ip) body.set("remoteip", ip);
  const r = await fetchImpl("https://challenges.cloudflare.com/turnstile/v0/siteverify",
    { method: "POST", body });
  const j = await r.json();
  return j.success === true;
}
