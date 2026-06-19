export const MODEL_CHAT = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
export const MODEL_EMBED = "@cf/baai/bge-base-en-v1.5";
export const TOP_K = 6;
export const MAX_OUTPUT_TOKENS = 600;
export const MAX_TURNS = 12;
export const RATE = { windowSec: 60, maxPerWindow: 8, dailyMax: 200 };
export function ok() { return true; }
