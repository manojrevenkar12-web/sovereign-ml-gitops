import type { ReactNode } from "react";
import { color, leading, measure, size, space, stroke, weight } from "../theme/tokens";

export function Section({ id, title, lede, aside, children }: { id: string; title: string; lede?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={`${id}-h`} style={{ padding: `${space[8]}px 0`, borderTop: `${stroke.rule}px solid ${color.ink}` }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "end", gap: space[5] }}>
        <div style={{ maxWidth: `${measure.text}ch` }}>
          <h2 id={`${id}-h`} style={{ margin: 0, fontSize: size.xxl, fontWeight: weight.heavy, lineHeight: leading.tight, letterSpacing: "-0.015em" }}>
            {title}
          </h2>
          {lede && <p style={{ margin: `${space[3]}px 0 0`, color: color.muted, fontSize: size.md }}>{lede}</p>}
        </div>
        {aside}
      </div>
      <div style={{ marginTop: space[6] }}>{children}</div>
    </section>
  );
}
