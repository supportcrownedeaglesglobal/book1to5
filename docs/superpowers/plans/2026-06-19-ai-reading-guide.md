# AI Reading Guide ("Guide Me") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floating "Guide me" AI companion that, strictly from the books' content (KJV-only scripture), recommends chapters and builds a saved listening plan from a reader's free-text problem.

**Architecture:** Static frontend widget → Cloudflare Pages Function (`/api/chat`) → Turnstile verify → KV rate-limit → Workers AI embeddings → Vectorize semantic retrieval → Workers AI chat with grounded prompt → shaped JSON `{reply, chapters[], plan?}`. No API key (Workers AI + Vectorize via Pages bindings). Device-local memory (localStorage).

**Tech Stack:** Cloudflare Pages Functions (JS, ES modules), Workers AI (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`, embeddings `@cf/baai/bge-base-en-v1.5` 768-dim), Vectorize, Workers KV, Turnstile; vanilla JS/CSS frontend; Python 3.14 (stdlib `unittest`) for the build-time index; vitest for JS unit tests.

## Global Constraints
- **Branch `changev4` only.** Never push to `main`/live in this plan. (Cloudflare gives `changev4` a preview deployment.)
- **No API key anywhere.** Workers AI + Vectorize via Pages bindings; Turnstile *secret* + ingest secret via Pages env secrets (never in client code or git).
- **Grounding is absolute:** answers use ONLY supplied book excerpts; never invent teaching/quotes; **all Bible references must be KJV**; off-book questions are gently redirected.
- **mp3s stay gitignored.** Commit only code/docs/data.
- **Branding:** floating button uses the gold/`.ceg` palette, large tap target, honors `prefers-reduced-motion`; never name the TTS/model engine on customer-facing UI.
- **Model IDs:** verify each `@cf/...` id against current Workers AI availability at build time; if renamed, update the single constant in `functions/api/_config.js`.

---

### Task 0: Cloudflare setup — OWNER prerequisite (blocks Tasks 7, 8, 12)
Not a code task. These happen in the owner's Cloudflare dashboard/`wrangler`; integration tasks can't run until done. Build/unit tasks (1–6, 9–11) do NOT need this.

- [ ] Enable **Workers AI** on the account.
- [ ] Create a **Vectorize** index: name `bmm-guide`, dimensions `768`, metric `cosine`.
      `wrangler vectorize create bmm-guide --dimensions=768 --metric=cosine`
- [ ] Create a **KV** namespace `GUIDE_RATE`: `wrangler kv namespace create GUIDE_RATE`.
- [ ] Create a **Turnstile** widget for the site domain(s) → note **site key** (public) + **secret key**.
- [ ] In the **Pages project** settings (or `wrangler.toml`, Task 1), add bindings: `AI` (Workers AI), `VECTORIZE` → `bmm-guide`, `GUIDE_RATE` → the KV id. Add env **secrets** `TURNSTILE_SECRET` and `INGEST_SECRET` (a random string you choose).
- [ ] Verify: `wrangler whoami` succeeds and the bindings list shows AI/VECTORIZE/GUIDE_RATE.

---

### Task 1: JS test + local dev harness

**Files:**
- Create: `package.json`, `vitest.config.js`, `wrangler.toml`
- Test: `functions/api/__tests__/smoke.test.js`

**Interfaces:**
- Produces: `npm test` (vitest) and `npm run dev` (`wrangler pages dev`) commands used by every later JS task.

- [ ] **Step 1: Write the failing test**
```js
// functions/api/__tests__/smoke.test.js
import { describe, it, expect } from "vitest";
import { ok } from "../_config.js";
describe("harness", () => { it("loads config", () => { expect(ok()).toBe(true); }); });
```

- [ ] **Step 2: Run it, verify it fails**
Run: `npm test` → Expected: FAIL ("Cannot find module ../_config.js").

- [ ] **Step 3: Create config + package files**
```js
// functions/api/_config.js
export const MODEL_CHAT = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
export const MODEL_EMBED = "@cf/baai/bge-base-en-v1.5";
export const TOP_K = 6;
export const MAX_OUTPUT_TOKENS = 600;
export const MAX_TURNS = 12;
export const RATE = { windowSec: 60, maxPerWindow: 8, dailyMax: 200 };
export function ok() { return true; }
```
```json
// package.json
{ "name": "bmm-guide", "private": true, "type": "module",
  "scripts": { "test": "vitest run", "dev": "wrangler pages dev . --compatibility-date=2025-06-01" },
  "devDependencies": { "vitest": "^2.0.0", "wrangler": "^3.60.0" } }
```
```toml
# wrangler.toml  (Pages project + bindings; ids filled from Task 0)
name = "bmm-guide"
pages_build_output_dir = "."
compatibility_date = "2025-06-01"
[ai]
binding = "AI"
[[vectorize]]
binding = "VECTORIZE"
index_name = "bmm-guide"
[[kv_namespaces]]
binding = "GUIDE_RATE"
id = "<<from Task 0>>"
```

- [ ] **Step 4: Install + run, verify pass**
Run: `npm install && npm test` → Expected: PASS (1 test).

- [ ] **Step 5: Commit**
```bash
git add package.json vitest.config.js wrangler.toml functions/api/_config.js functions/api/__tests__/smoke.test.js
git commit -m "chore(guide): JS test + wrangler pages dev harness"
```
(Note: add `node_modules/` to `.gitignore` if not already present, in this commit.)

---

### Task 2: Grounding index builder (`_chapters.json`)

**Files:**
- Create: `audiobook/scripts/build_guide_index.py`, `functions/api/__tests__/fixtures/mini_chapters.json`
- Test: `audiobook/scripts/test_build_guide_index.py` (stdlib `unittest`)
- Produces (output, generated): `functions/api/_chapters.json` = `{ "<id>": {"book": N, "title": str, "url": "book-N.html#<id>", "excerpt": str} }`

**Interfaces:**
- Consumes: `audiobook/data/chapters.json` (Book 5) + `audiobook/data/book-{1..4}/chapters.json`.
- Produces: `_chapters.json` map consumed by Tasks 7 (ingest) and 8 (chat excerpt lookup).

- [ ] **Step 1: Write the failing test**
```python
# audiobook/scripts/test_build_guide_index.py
import unittest, json, tempfile, os
from build_guide_index import build_map

class T(unittest.TestCase):
    def test_shape_and_excerpt(self):
        tracks = [{"id":"001-intro","title":"Introduction","level":1,
                   "segments":[{"role":"chapter_title","text":"Introduction"},
                               {"role":"body","text":"Word "*200}]}]
        m = build_map({5: tracks})
        self.assertIn("001-intro", m)
        e = m["001-intro"]
        self.assertEqual(e["book"], 5)
        self.assertEqual(e["url"], "book-5.html#001-intro")
        self.assertLessEqual(len(e["excerpt"].split()), 160)  # capped
if __name__ == "__main__": unittest.main()
```

- [ ] **Step 2: Run, verify it fails**
Run: `C:\Python314\python.exe audiobook/scripts/test_build_guide_index.py` → FAIL ("No module named build_guide_index").

- [ ] **Step 3: Implement the builder**
```python
# audiobook/scripts/build_guide_index.py
"""Build functions/api/_chapters.json (compact grounding map) from all books' chapters.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT  = HERE.parent.parent / "functions" / "api" / "_chapters.json"
EXCERPT_WORDS = 150

def _excerpt(track):
    txt = " ".join(s["text"] for s in track.get("segments", []) if s.get("role") != "chapter_title")
    return " ".join(txt.split()[:EXCERPT_WORDS])

def build_map(books):  # books: {book_num: [tracks]}
    m = {}
    for n, tracks in books.items():
        for t in tracks:
            if not t.get("segments"): continue
            m[t["id"]] = {"book": n, "title": t["title"],
                          "url": f"book-{n}.html#{t['id']}", "excerpt": _excerpt(t)}
    return m

def _load(n):
    p = DATA / ("chapters.json" if n == 5 else f"book-{n}/chapters.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

def main():
    books = {n: _load(n) for n in (1, 2, 3, 4, 5)}
    m = build_map(books)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}  ({len(m)} tracks)")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test, verify pass**
Run: `C:\Python314\python.exe audiobook/scripts/test_build_guide_index.py` → PASS.

- [ ] **Step 5: Generate the real index + commit**
```bash
C:\Python314\python.exe audiobook/scripts/build_guide_index.py   # writes functions/api/_chapters.json
git add audiobook/scripts/build_guide_index.py audiobook/scripts/test_build_guide_index.py functions/api/_chapters.json
git commit -m "feat(guide): build grounding index from chapters.json"
```

---

### Task 3: Prompt assembly + guardrails (`_guide.js`)

**Files:**
- Create: `functions/api/_guide.js`
- Test: `functions/api/__tests__/guide.prompt.test.js`

**Interfaces:**
- Produces: `buildMessages({message, history, retrieved})` → `[{role,content}...]` where `retrieved` is `[{id,book,title,url,excerpt}]`. System message embeds the hard rules + excerpts. Consumed by Task 8.

- [ ] **Step 1: Write the failing test**
```js
import { describe, it, expect } from "vitest";
import { buildMessages, SYSTEM_RULES } from "../_guide.js";
describe("buildMessages", () => {
  it("embeds only retrieved excerpts and the KJV/book-only rules", () => {
    const msgs = buildMessages({ message: "I feel hopeless", history: [],
      retrieved: [{id:"012-hope",book:3,title:"Hope",url:"book-3.html#012-hope",excerpt:"He is risen."}] });
    const sys = msgs[0].content;
    expect(msgs[0].role).toBe("system");
    expect(sys).toContain("KJV");
    expect(sys).toContain("only");
    expect(sys).toContain("012-hope");        // excerpt/metadata injected
    expect(msgs.at(-1)).toEqual({ role: "user", content: "I feel hopeless" });
  });
});
```

- [ ] **Step 2: Run, verify fail** — `npm test guide.prompt` → FAIL (no `_guide.js`).

- [ ] **Step 3: Implement**
```js
// functions/api/_guide.js  (part 1 of several tasks; later tasks append exports)
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
```

- [ ] **Step 4: Run, verify pass** — `npm test guide.prompt` → PASS.
- [ ] **Step 5: Commit** — `git add functions/api/_guide.js functions/api/__tests__/guide.prompt.test.js && git commit -m "feat(guide): grounded prompt assembly + KJV/book-only rules"`

---

### Task 4: Response parsing/shaping (`_guide.js`)

**Files:** Modify `functions/api/_guide.js` · Test `functions/api/__tests__/guide.parse.test.js`

**Interfaces:**
- Produces: `shapeReply(modelText, knownIds, chapterMap)` → `{reply, chapters:[{id,book,title,url}], plan:[{id,title,why}]}`; drops any id not in `knownIds`; falls back to plain text if JSON is malformed. Consumed by Task 8.

- [ ] **Step 1: Failing test**
```js
import { describe, it, expect } from "vitest";
import { shapeReply } from "../_guide.js";
const map = { "012-hope": {book:3,title:"Hope",url:"book-3.html#012-hope"} };
describe("shapeReply", () => {
  it("keeps only known ids and resolves metadata", () => {
    const txt = JSON.stringify({reply:"Listen to Hope.",chapters:[{id:"012-hope"},{id:"FAKE"}],plan:[{id:"012-hope",why:"start here"}]});
    const out = shapeReply(txt, new Set(["012-hope"]), map);
    expect(out.reply).toContain("Hope");
    expect(out.chapters).toEqual([{id:"012-hope",book:3,title:"Hope",url:"book-3.html#012-hope"}]);
    expect(out.plan[0]).toMatchObject({id:"012-hope",title:"Hope",why:"start here"});
  });
  it("falls back gracefully on non-JSON", () => {
    const out = shapeReply("just words", new Set(), {});
    expect(out.reply).toBe("just words");
    expect(out.chapters).toEqual([]);
  });
});
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement (append to `_guide.js`)**
```js
export function shapeReply(modelText, knownIds, chapterMap) {
  let data = null;
  try { const m = modelText.match(/\{[\s\S]*\}/); if (m) data = JSON.parse(m[0]); } catch { /* fall through */ }
  if (!data || typeof data.reply !== "string") return { reply: String(modelText).trim(), chapters: [], plan: [] };
  const resolve = (id) => { const c = chapterMap[id]; return c ? { id, book: c.book, title: c.title, url: c.url } : null; };
  const chapters = (data.chapters || []).map(x => x && x.id).filter(id => knownIds.has(id)).map(resolve).filter(Boolean);
  const plan = (data.plan || []).filter(p => p && knownIds.has(p.id))
      .map(p => { const c = chapterMap[p.id]; return { id: p.id, title: c?.title || p.id, why: String(p.why || "") }; });
  return { reply: data.reply.trim(), chapters, plan };
}
```
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(guide): parse + sanitize model reply to known chapter ids"`

---

### Task 5: Rate limit (`_guide.js`)

**Files:** Modify `functions/api/_guide.js` · Test `functions/api/__tests__/guide.rate.test.js`

**Interfaces:**
- Produces: `async checkRate(kv, key, rate)` → `{allowed:boolean}`; increments a per-window counter and a per-day counter in KV. `kv` is the `GUIDE_RATE` binding (interface: `get(k)`, `put(k,v,{expirationTtl})`). Consumed by Task 8.

- [ ] **Step 1: Failing test** (mock KV)
```js
import { describe, it, expect } from "vitest";
import { checkRate } from "../_guide.js";
function fakeKV(){ const s=new Map(); return { store:s,
  async get(k){return s.get(k)??null;}, async put(k,v){s.set(k,v);} }; }
const rate = { windowSec:60, maxPerWindow:2, dailyMax:5 };
describe("checkRate", () => {
  it("allows up to maxPerWindow then blocks", async () => {
    const kv = fakeKV();
    expect((await checkRate(kv,"ip1",rate)).allowed).toBe(true);
    expect((await checkRate(kv,"ip1",rate)).allowed).toBe(true);
    expect((await checkRate(kv,"ip1",rate)).allowed).toBe(false);
  });
});
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement (append)**
```js
export async function checkRate(kv, key, rate, now = 0) {
  const win = Math.floor((now || Date.now()) / 1000 / rate.windowSec);
  const day = Math.floor((now || Date.now()) / 1000 / 86400);
  const wk = `w:${key}:${win}`, dk = `d:${key}:${day}`;
  const wc = parseInt(await kv.get(wk) || "0", 10);
  const dc = parseInt(await kv.get(dk) || "0", 10);
  if (wc >= rate.maxPerWindow || dc >= rate.dailyMax) return { allowed: false };
  await kv.put(wk, String(wc + 1), { expirationTtl: rate.windowSec + 5 });
  await kv.put(dk, String(dc + 1), { expirationTtl: 86400 + 60 });
  return { allowed: true };
}
```
(`Date.now()` is available in Workers at runtime; the test passes an explicit `now`.)
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(guide): KV sliding-window + daily rate limit"`

---

### Task 6: Turnstile verify (`_guide.js`)

**Files:** Modify `functions/api/_guide.js` · Test `functions/api/__tests__/guide.turnstile.test.js`

**Interfaces:**
- Produces: `async verifyTurnstile(secret, token, ip, fetchImpl=fetch)` → `boolean`. Consumed by Task 8.

- [ ] **Step 1: Failing test** (mock fetch)
```js
import { describe, it, expect } from "vitest";
import { verifyTurnstile } from "../_guide.js";
const f = (body) => async () => ({ json: async () => body });
describe("verifyTurnstile", () => {
  it("true on success", async () => { expect(await verifyTurnstile("s","t","1.1.1.1", f({success:true}))).toBe(true); });
  it("false on failure/empty token", async () => {
    expect(await verifyTurnstile("s","t","1.1.1.1", f({success:false}))).toBe(false);
    expect(await verifyTurnstile("s","", "1.1.1.1", f({success:true}))).toBe(false);
  });
});
```
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement (append)**
```js
export async function verifyTurnstile(secret, token, ip, fetchImpl = fetch) {
  if (!token) return false;
  const body = new URLSearchParams({ secret, response: token });
  if (ip) body.set("remoteip", ip);
  const r = await fetchImpl("https://challenges.cloudflare.com/turnstile/v0/siteverify",
    { method: "POST", body });
  const j = await r.json();
  return j.success === true;
}
```
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(guide): server-side Turnstile verification"`

---

### Task 7: Ingest route (populate Vectorize) — needs Task 0

**Files:** Create `functions/api/ingest.js` · Verify with `wrangler pages dev` + curl

**Interfaces:**
- Consumes: `_chapters.json` (Task 2), `env.AI`, `env.VECTORIZE`, `env.INGEST_SECRET`.
- Produces: a populated `bmm-guide` Vectorize index (vectors keyed by track id, metadata `{book,title,url}`).

- [ ] **Step 1: Implement the route**
```js
// functions/api/ingest.js  — POST /api/ingest?secret=...  (one-time / on content change)
import { MODEL_EMBED } from "./_config.js";
import CHAPTERS from "./_chapters.json" assert { type: "json" };
export async function onRequestPost({ request, env }) {
  const url = new URL(request.url);
  if (url.searchParams.get("secret") !== env.INGEST_SECRET) return new Response("forbidden", { status: 403 });
  const ids = Object.keys(CHAPTERS);
  let done = 0;
  for (let i = 0; i < ids.length; i += 20) {                 // batch to stay within limits
    const batch = ids.slice(i, i + 20);
    const texts = batch.map(id => `${CHAPTERS[id].title}. ${CHAPTERS[id].excerpt}`);
    const { data } = await env.AI.run(MODEL_EMBED, { text: texts });
    const vectors = batch.map((id, j) => ({ id, values: data[j],
      metadata: { book: CHAPTERS[id].book, title: CHAPTERS[id].title, url: CHAPTERS[id].url } }));
    await env.VECTORIZE.upsert(vectors);
    done += batch.length;
  }
  return Response.json({ ingested: done });
}
```
- [ ] **Step 2: Run the dev server**
Run: `npm run dev` (uses remote bindings from Task 0). Expected: serves at `http://localhost:8788`.
- [ ] **Step 3: Trigger ingest + verify count**
Run: `curl -X POST "http://localhost:8788/api/ingest?secret=<INGEST_SECRET>"`
Expected: JSON `{"ingested": <≈ total track count>}` (a few hundred). Verify: `wrangler vectorize info bmm-guide` shows a matching vector count.
- [ ] **Step 4: Commit** — `git add functions/api/ingest.js && git commit -m "feat(guide): secret-gated Vectorize ingest via Workers AI embeddings"`

---

### Task 8: Chat orchestration route (`/api/chat`) — needs Tasks 3–7

**Files:** Create `functions/api/chat.js` · Verify with `wrangler pages dev` + curl

**Interfaces:**
- Consumes: `_guide.js` (buildMessages, shapeReply, checkRate, verifyTurnstile), `_chapters.json`, `_config.js`, `env.AI`, `env.VECTORIZE`, `env.GUIDE_RATE`, `env.TURNSTILE_SECRET`.
- Produces: `POST /api/chat {message, history, turnstileToken}` → `{reply, chapters[], plan[]}` (200) | `{error}` (400/403/429/500).

- [ ] **Step 1: Implement**
```js
// functions/api/chat.js
import { MODEL_CHAT, MODEL_EMBED, TOP_K, MAX_OUTPUT_TOKENS, MAX_TURNS, RATE } from "./_config.js";
import CHAPTERS from "./_chapters.json" assert { type: "json" };
import { buildMessages, shapeReply, checkRate, verifyTurnstile } from "./_guide.js";

const FALLBACK = { reply: "I'm here to help you find where to begin. A gentle place to start is Book 1 — Behold My Glory.", chapters: [], plan: [] };

export async function onRequestPost({ request, env }) {
  try {
    const ip = request.headers.get("CF-Connecting-IP") || "anon";
    const { message, history = [], turnstileToken } = await request.json();
    if (!message || typeof message !== "string") return Response.json({ error: "empty" }, { status: 400 });
    if (history.length > MAX_TURNS) history.splice(0, history.length - MAX_TURNS);
    if (!(await verifyTurnstile(env.TURNSTILE_SECRET, turnstileToken, ip))) return Response.json({ error: "turnstile" }, { status: 403 });
    if (!(await checkRate(env.GUIDE_RATE, ip, RATE)).allowed) return Response.json({ error: "rate", reply: "The guide is resting — please try again in a little while." }, { status: 429 });

    const { data } = await env.AI.run(MODEL_EMBED, { text: [message] });
    const q = await env.VECTORIZE.query(data[0], { topK: TOP_K, returnMetadata: true });
    const retrieved = q.matches.map(m => ({ id: m.id, ...CHAPTERS[m.id] })).filter(r => r.title);
    if (!retrieved.length) return Response.json(FALLBACK);

    const messages = buildMessages({ message, history, retrieved });
    const ai = await env.AI.run(MODEL_CHAT, { messages, max_tokens: MAX_OUTPUT_TOKENS });
    const text = ai.response || ai.result || "";
    const knownIds = new Set(retrieved.map(r => r.id));
    return Response.json(shapeReply(text, knownIds, CHAPTERS));
  } catch (e) {
    return Response.json(FALLBACK, { status: 200 });   // never strand the reader
  }
}
```
- [ ] **Step 2: Grounding/integration checks** (`npm run dev` running)
Run each and read the JSON:
```bash
curl -s localhost:8788/api/chat -H 'content-type: application/json' \
  -d '{"message":"I feel hopeless and grieving","turnstileToken":"<dev-token>"}'
```
Expected: `reply` is warm + book-grounded; `chapters[]` contains REAL ids present in `_chapters.json`; any scripture is KJV; deep-link urls look like `book-N.html#<id>`.
Adversarial: `-d '{"message":"What does the Quran say about X?","turnstileToken":"..."}'` → reply redirects to what the books cover, recommends no off-book content.
(Use a Turnstile test token, or temporarily set a dev bypass env; never commit a bypass.)
- [ ] **Step 3: Commit** — `git add functions/api/chat.js && git commit -m "feat(guide): /api/chat orchestration (retrieve→Workers AI→grounded reply)"`

---

### Task 9: Widget styles (`assets/guide.css`)

**Files:** Create `assets/guide.css` · Verify in browser

**Interfaces:** Produces CSS classes `.guide-fab`, `.guide-panel`, `.guide-msg`, `.guide-card`, `.guide-plan` used by Task 10.

- [ ] **Step 1: Implement** — gold FAB, slide-up panel, large readable text, focus rings; `@media (prefers-reduced-motion: reduce){ .guide-panel{transition:none} }`; mobile full-width panel. (Match `index.html` gold tokens; ≥44px tap target.)
```css
/* assets/guide.css — see index.html for gold vars; mirror them here */
.guide-fab{position:fixed;right:18px;bottom:18px;z-index:60;min-width:56px;min-height:56px;border-radius:30px;
  padding:0 20px;font:600 17px/1 system-ui;color:#1a1205;background:linear-gradient(180deg,#f6d774,#c79a2e);
  border:1px solid #a87f1f;box-shadow:0 6px 20px rgba(0,0,0,.35);cursor:pointer}
.guide-panel{position:fixed;right:18px;bottom:84px;z-index:60;width:min(420px,94vw);max-height:72vh;display:none;
  flex-direction:column;background:#0f0c06;border:1px solid #6b531c;border-radius:16px;overflow:hidden}
.guide-panel.open{display:flex}
.guide-log{flex:1;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:10px}
.guide-msg{font-size:17px;line-height:1.5;color:#f3e8c8;white-space:pre-wrap}
.guide-msg.me{align-self:flex-end;color:#fff}
.guide-card{display:block;padding:10px 12px;border:1px solid #6b531c;border-radius:10px;color:#f6d774;text-decoration:none}
.guide-plan{margin:6px 0;padding-left:18px;color:#e8d9ad}
.guide-form{display:flex;gap:8px;padding:10px;border-top:1px solid #3a2f12}
.guide-form input{flex:1;font-size:17px;padding:10px;border-radius:10px;border:1px solid #6b531c;background:#1a1408;color:#fff}
@media (prefers-reduced-motion: reduce){.guide-panel{transition:none}}
```
- [ ] **Step 2: Verify** — open a scratch HTML including the CSS in browser; FAB visible bottom-right, panel readable, 44px+ target. (Visual check.)
- [ ] **Step 3: Commit** — `git add assets/guide.css && git commit -m "feat(guide): widget styles (brand gold, accessible)"`

---

### Task 10: Widget script (`assets/guide.js`)

**Files:** Create `assets/guide.js` · Verify in browser against `npm run dev`

**Interfaces:**
- Consumes: `POST /api/chat`, Turnstile JS (`window.turnstile`), localStorage.
- Produces: global init `window.BMMGuide.mount({siteKey})` called by Task 11.

- [ ] **Step 1: Implement** — render FAB + panel; on open, render Turnstile (invisible) to get a token; on submit POST `{message, history, turnstileToken}`; render reply, chapter cards (anchor → `url`), and plan; persist `{plan, history}` in `localStorage["bmm_guide"]`; on load, restore. Handle 429/403/error with the returned/friendly message.
```js
// assets/guide.js  (abridged structure — full logic in this step at execution)
window.BMMGuide = (function () {
  const KEY = "bmm_guide";
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {history:[],plan:[]}; } catch { return {history:[],plan:[]}; } };
  const save = (s) => localStorage.setItem(KEY, JSON.stringify(s));
  async function send(state, panel, siteKey) {
    const token = await new Promise(res => window.turnstile.render(panel.querySelector(".guide-ts"),
      { sitekey: siteKey, size: "invisible", callback: res }) && window.turnstile.execute());
    const r = await fetch("/api/chat", { method:"POST", headers:{ "content-type":"application/json" },
      body: JSON.stringify({ message: state.pending, history: state.history.slice(-8), turnstileToken: token }) });
    return r.json();
  }
  function mount({ siteKey }) { /* build FAB+panel from guide.css classes, wire submit→send→render, persist via save() */ }
  return { mount };
})();
```
(Execution writes the full `mount()` + render functions; structure above fixes the public interface and storage key.)
- [ ] **Step 2: Verify in browser** — `npm run dev`; click FAB; ask "where do I start?"; confirm reply + tappable chapter cards that navigate to `book-N.html#<id>`; reload page → plan/history restored.
- [ ] **Step 3: Commit** — `git add assets/guide.js && git commit -m "feat(guide): chat widget (Turnstile, chapter cards, saved plan)"`

---

### Task 11: Wire widget into pages

**Files:** Modify `index.html`, `book-1.html`…`book-5.html` (one include block each, before `</body>`)

**Interfaces:** Consumes `window.BMMGuide.mount`; loads Turnstile + `assets/guide.css`/`assets/guide.js`.

- [ ] **Step 1: Add the include block to each page** (identical block, 6 files)
```html
<link rel="stylesheet" href="assets/guide.css">
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<script src="assets/guide.js" defer></script>
<script>addEventListener("DOMContentLoaded",()=>window.BMMGuide.mount({siteKey:"<<TURNSTILE_SITE_KEY>>"}));</script>
```
- [ ] **Step 2: Verify deep-link anchors exist** — confirm the reader page scrolls/opens to `#<id>` (the existing player uses track ids; if no `#id` handler exists, the card should instead pass `?track=<id>`; check `book-5.html` for how a track is opened and match it). Adjust `url` format in `build_guide_index.py` if the player expects a query param, and regenerate `_chapters.json`.
- [ ] **Step 3: Verify in browser** on all 6 pages — FAB present, opens, recommends, navigates.
- [ ] **Step 4: Commit** — `git add index.html book-*.html && git commit -m "feat(guide): mount Guide widget on landing + all players"`

---

### Task 12: End-to-end verification on `changev4` preview — needs Task 0

- [ ] **Step 1: Push** `git push origin changev4` → Cloudflare builds a **preview** deployment (non-production; not live).
- [ ] **Step 2: On the preview URL**, run the grounding suite: "I'm grieving", "I doubt God", "I'm afraid of death", "where do I start?" → each returns real chapters, KJV-only scripture, no invented content, working deep links.
- [ ] **Step 3: Abuse checks** — call `/api/chat` with no/invalid `turnstileToken` → 403; exceed `maxPerWindow` quickly → 429 "resting" message.
- [ ] **Step 4: Accessibility** — large fonts, keyboard focus to FAB + input, panel usable at 380px width, reduced-motion respected.
- [ ] **Step 5: Report** the preview URL + results to the owner. Do NOT merge to `main`/live without explicit approval.

---

## Self-Review (author checklist)
- **Spec coverage:** floating widget everywhere (T9–11) ✓; Workers AI no-key (T1 binding, T7/T8) ✓; semantic retrieval via Vectorize (T7 ingest, T8 query) ✓; strictly book-grounded + KJV (T3 rules, T4 id-sanitize, T8) ✓; device-local plan (T10) ✓; Turnstile + rate limit + caps (T1 config, T5, T6, T8) ✓; safety/fallback (T3 rules, T8 FALLBACK) ✓; changev4 preview only (T12, Global Constraints) ✓; owner setup (T0) ✓.
- **Placeholders:** the only intentional `<<...>>` are values that come from the owner's account (KV id, secrets, Turnstile site key) — filled at execution, not logic gaps. Task 10's `mount()` body is summarized with a fixed public interface; execution writes the full DOM logic (no behavioral ambiguity remains: classes from T9, storage key `bmm_guide`, endpoint contract from T8).
- **Type consistency:** `buildMessages`/`shapeReply`/`checkRate`/`verifyTurnstile` signatures match their uses in `chat.js` (T8); `_chapters.json` shape `{book,title,url,excerpt}` is identical across T2/T7/T8; chapter id is the single join key everywhere.
- **Open risk:** deep-link format (`#id` vs `?track=`) is verified in T11 Step 2 against the real player and fixed in one place (`build_guide_index.py`).
