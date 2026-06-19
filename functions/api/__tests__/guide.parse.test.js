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
