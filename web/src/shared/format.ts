export const pct = (x: number, digits = 1) => `${(100 * x).toFixed(digits)}%`;
export const short = (digest: string | null) => (digest ? `${digest.slice(0, 15)}…${digest.slice(-4)}` : "none");
export const authority = (name: string) =>
  name.replace(/^stadt-/, "").replace(/^kreis-/, "").replace(/^\w/, (c) => c.toUpperCase());
