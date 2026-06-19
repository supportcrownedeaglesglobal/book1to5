// POST /api/chat  {message, history, turnstileToken} -> {reply, chapters[], plan[]}
// Verify Turnstile -> rate-limit -> embed -> Vectorize retrieve -> grounded Workers AI -> shaped reply.
import { MODEL_CHAT, MODEL_EMBED, TOP_K, MAX_OUTPUT_TOKENS, MAX_TURNS, RATE } from "./_config.js";
import CHAPTERS from "./_chapters.json";
import { buildMessages, shapeReply, checkRate, verifyTurnstile } from "./_guide.js";

const FALLBACK = {
  reply: "I'm here to help you find where to begin. A gentle place to start is Book 1 — Behold My Glory.",
  chapters: [],
  plan: [],
};

export async function onRequestPost({ request, env }) {
  try {
    const ip = request.headers.get("CF-Connecting-IP") || "anon";
    const { message, history = [], turnstileToken } = await request.json();
    if (!message || typeof message !== "string") return Response.json({ error: "empty" }, { status: 400 });
    const hist = Array.isArray(history) ? history.slice(-MAX_TURNS) : [];

    if (!(await verifyTurnstile(env.TURNSTILE_SECRET, turnstileToken, ip))) {
      return Response.json({ error: "turnstile", reply: "Please confirm you're human and try again." }, { status: 403 });
    }
    if (!(await checkRate(env.GUIDE_RATE, ip, RATE)).allowed) {
      return Response.json({ error: "rate", reply: "The guide is resting — please try again in a little while." }, { status: 429 });
    }

    const emb = await env.AI.run(MODEL_EMBED, { text: [message] });
    const vector = emb.data[0];
    const q = await env.VECTORIZE.query(vector, { topK: TOP_K, returnMetadata: true });
    const retrieved = (q.matches || []).map((m) => ({ id: m.id, ...CHAPTERS[m.id] })).filter((r) => r && r.title);
    if (!retrieved.length) return Response.json(FALLBACK);

    const messages = buildMessages({ message, history: hist, retrieved });
    const ai = await env.AI.run(MODEL_CHAT, { messages, max_tokens: MAX_OUTPUT_TOKENS });
    const text = ai.response || ai.result || "";
    const knownIds = new Set(retrieved.map((r) => r.id));
    return Response.json(shapeReply(text, knownIds, CHAPTERS));
  } catch (e) {
    return Response.json({ ...FALLBACK, note: String(e && e.message || e) }, { status: 200 }); // never strand the reader
  }
}
