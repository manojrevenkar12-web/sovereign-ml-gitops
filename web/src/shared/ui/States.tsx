import { color, font, radius, size, space, stroke, weight } from "../theme/tokens";

export const buttonStyle = {
  font: `${weight.semibold} ${size.sm}px ${font.body}`,
  color: color.card,
  background: color.ink,
  border: "none",
  borderRadius: radius.md,
  padding: `${space[2]}px ${space[5]}px`,
  cursor: "pointer",
} as const;

/** Grey blocks in the shape of the page that is on its way. */
export function Skeleton({ label }: { label: string }) {
  const block = (h: number, w: string) => ({ height: h, width: w, background: color.panel, borderRadius: radius.sm });
  return (
    <div role="status" aria-busy="true" aria-label={label} style={{ display: "grid", gap: space[5], padding: `${space[8]}px 0` }}>
      <div style={block(space[8], "55%")} />
      <div style={block(space[5], "70%")} />
      {[0, 1, 2].map((i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: space[2] }}>
          {Array.from({ length: 7 }, (_, j) => (
            <div key={j} style={block(space[7], "100%")} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" style={{ borderLeft: `${space[1]}px solid ${color.held}`, background: color.card, padding: `${space[4]}px ${space[5]}px`, margin: `${space[8]}px 0` }}>
      <p style={{ margin: 0, fontWeight: weight.semibold }}>The results did not load: {message}.</p>
      <p style={{ margin: `${space[2]}px 0 ${space[4]}px`, color: color.muted }}>
        <code>web/public/data.json</code> is written by <code>python scripts/report.py</code>. Check that it exists, then load it again.
      </p>
      <button type="button" onClick={onRetry} style={buttonStyle}>
        Load again
      </button>
    </div>
  );
}

export function EmptyNotice({ what, command }: { what: string; command: string }) {
  return (
    <p style={{ margin: 0, padding: `${space[4]}px`, border: `${stroke.hair}px dashed ${color.line}`, color: color.muted }}>
      No {what} yet. Run <code>{command}</code> to produce them.
    </p>
  );
}
