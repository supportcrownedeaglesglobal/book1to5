import { describe, it, expect } from "vitest";
import { checkRate } from "../_guide.js";
function fakeKV(){ const s=new Map(); return { store:s,
  async get(k){return s.get(k)??null;}, async put(k,v){s.set(k,v);} }; }
const rate = { windowSec:60, maxPerWindow:2, dailyMax:5 };
describe("checkRate", () => {
  it("allows up to maxPerWindow then blocks", async () => {
    const kv = fakeKV();
    expect((await checkRate(kv,"ip1",rate,1000)).allowed).toBe(true);
    expect((await checkRate(kv,"ip1",rate,1000)).allowed).toBe(true);
    expect((await checkRate(kv,"ip1",rate,1000)).allowed).toBe(false);
  });
  it("blocks once dailyMax is reached even across windows", async () => {
    const kv = fakeKV();
    const r = { windowSec: 60, maxPerWindow: 100, dailyMax: 3 };
    // 3 allowed across 3 different windows (same day), 4th blocked by daily cap
    expect((await checkRate(kv,"ip2",r, 1000_000)).allowed).toBe(true);
    expect((await checkRate(kv,"ip2",r, 1100_000)).allowed).toBe(true);
    expect((await checkRate(kv,"ip2",r, 1200_000)).allowed).toBe(true);
    expect((await checkRate(kv,"ip2",r, 1300_000)).allowed).toBe(false);
  });
});
