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
    expect(sys).toContain("012-hope");
    expect(msgs.at(-1)).toEqual({ role: "user", content: "I feel hopeless" });
  });
});
