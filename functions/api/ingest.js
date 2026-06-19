// POST /api/ingest?secret=...&start=0&count=400  — one-time / on-content-change.
// Embeds a slice of the grounding index into Vectorize. Sliced to stay well under
// the Workers subrequest cap; repeat with the returned nextStart until it is null.
import { MODEL_EMBED } from "./_config.js";
import CHAPTERS from "./_chapters.json" with { type: "json" };

const BATCH = 50; // texts per embedding call

export async function onRequestPost({ request, env }) {
  const url = new URL(request.url);
  if (url.searchParams.get("secret") !== env.INGEST_SECRET) return new Response("forbidden", { status: 403 });

  const ids = Object.keys(CHAPTERS);
  const start = parseInt(url.searchParams.get("start") || "0", 10);
  const count = parseInt(url.searchParams.get("count") || "400", 10);
  const slice = ids.slice(start, start + count);

  let done = 0;
  for (let i = 0; i < slice.length; i += BATCH) {
    const batch = slice.slice(i, i + BATCH);
    const texts = batch.map((id) => `${CHAPTERS[id].title}. ${CHAPTERS[id].excerpt}`);
    const { data } = await env.AI.run(MODEL_EMBED, { text: texts });
    const vectors = batch.map((id, j) => ({
      id,
      values: data[j],
      metadata: { book: CHAPTERS[id].book, title: CHAPTERS[id].title, url: CHAPTERS[id].url },
    }));
    await env.VECTORIZE.upsert(vectors);
    done += batch.length;
  }
  const nextStart = start + count;
  return Response.json({ ingested: done, nextStart: nextStart < ids.length ? nextStart : null, total: ids.length });
}
