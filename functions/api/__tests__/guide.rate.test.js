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
});
