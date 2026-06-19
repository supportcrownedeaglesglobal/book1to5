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
