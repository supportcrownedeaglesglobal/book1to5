import { describe, it, expect } from "vitest";
import { ok } from "../_config.js";
describe("harness", () => { it("loads config", () => { expect(ok()).toBe(true); }); });
