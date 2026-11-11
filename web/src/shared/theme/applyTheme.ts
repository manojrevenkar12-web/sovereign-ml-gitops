import { color, font } from "./tokens";

/** Exposes the tokens global.css needs as CSS custom properties. */
export function applyTheme(root: HTMLElement = document.documentElement) {
  root.style.setProperty("--paper", color.paper);
  root.style.setProperty("--ink", color.ink);
  root.style.setProperty("--link", color.link);
  root.style.setProperty("--focus", color.focus);
  root.style.setProperty("--font-body", font.body);
  root.style.setProperty("--font-mono", font.mono);
}
