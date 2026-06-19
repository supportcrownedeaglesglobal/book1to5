// POST /api/ingest?secret=...&start=0&count=400  — one-time / on-content-change.
// Embeds a slice of the grounding index into Vectorize. Sliced to stay under the
// Workers subrequest cap; repeat with the returned nextStart until it is null.
// Reports embed/upsert errors (with the id it failed near) instead of throwing a bare 1101,
// and skips any vector whose embedding came back malformed.
import { MODEL_EMBED } from "./_config.js";
import CHAPTERS from "./_chapters.json";

const BATCH = 50; // texts per embedding call

export async function onRequestPost({ request, env }) {
  const url = new URL(request.url);
  if (url.searchParams.get("secret") !== env.INGEST_SECRET) return new Response("forbidden", { status: 403 });

  const ids = Object.keys(CHAPTERS);
  const start = parseInt(url.searchParams.get("start") || "0", 10);
  const count = parseInt(url.searchParams.get("count") || "400", 10);
  const slice = ids.slice(start, start + count);

  let done = 0, skipped = 0;
  for (let i = 0; i < slice.length; i += BATCH) {
    const batch = slice.slice(i, i + BATCH);
    const texts = batch.map((id) => `${CHAPTERS[id].title}. ${CHAPTERS[id].excerpt}`.trim().slice(0, 2000) || "untitled");

    let data;
    try {
      ({ data } = await env.AI.run(MODEL_EMBED, { text: texts }));
    } catch (e) {
      return Response.json({ error: "embed", detail: String((e && e.message) || e), failedNear: batch[0], done }, { status: 200 });
    }

    const vectors = [];
    batch.forEach((id, j) => {
      const v = data && data[j];
      if (Array.isArray(v) && v.length) {
        vectors.push({ id, values: v, metadata: { book: CHAPTERS[id].book, title: CHAPTERS[id].title, url: CHAPTERS[id].url } });
      } else {
        skipped++;
      }
    });

    try {
      if (vectors.length) await env.VECTORIZE.upsert(vectors);
    } catch (e) {
      return Response.json({ error: "upsert", detail: String((e && e.message) || e), failedNear: batch[0], done }, { status: 200 });
    }
    done += vectors.length;
  }
  const nextStart = start + count;
  return Response.json({ ingested: done, skipped, nextStart: nextStart < ids.length ? nextStart : null, total: ids.length });
}
