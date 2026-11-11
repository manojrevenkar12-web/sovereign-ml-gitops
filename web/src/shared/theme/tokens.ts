/** Design tokens. Components read these; no colour, size or duration is written anywhere else.
 * Palette: the paper and ink of an official form, with the two stamp colours an office uses
 * for "approved" and "held", and an ochre for "goes to a person". */
export const color = {
  paper: "#EDF0F2",
  card: "#FFFFFF",
  ink: "#15212C",
  muted: "#526170",
  line: "#C9D1D8",
  panel: "#DCE2E7",
  approved: "#1F6146",
  approvedSoft: "#D6E8DF",
  held: "#A3251B",
  heldSoft: "#F3DAD7",
  person: "#9A6A00",
  link: "#1D4C96",
  focus: "#1D4C96",
} as const;

export const font = {
  body: '"Atkinson Hyperlegible Next", system-ui, sans-serif',
  mono: '"Atkinson Hyperlegible Mono", ui-monospace, monospace',
} as const;

/** Type scale on a 1.25 ratio from 16 px. */
export const size = { xs: 12.8, sm: 14, md: 16, lg: 20, xl: 25, xxl: 31.25, display: 48.8 } as const;
export const weight = { regular: 400, medium: 500, semibold: 600, bold: 700, heavy: 800 } as const;
export const leading = { tight: 1.1, snug: 1.3, body: 1.55 } as const;
export const space = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96] as const;
export const radius = { sm: 3, md: 6, pill: 999 } as const;
export const measure = { text: 68, page: 1180 } as const;
export const stroke = { hair: 1, rule: 2, stamp: 3 } as const;

export const motion = {
  fast: 0.18,
  base: 0.32,
  travel: 1.1,
  stagger: 0.16,
  ease: [0.22, 1, 0.36, 1] as [number, number, number, number],
} as const;

export const breakpoint = { narrow: 760 } as const;
