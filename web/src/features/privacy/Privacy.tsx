import type { Data } from "../../shared/data/types";
import { pct } from "../../shared/format";
import { color, radius, size, space, stroke, weight } from "../../shared/theme/tokens";

const LABELS: Record<string, string> = {
  none: "No filter",
  "regex (email + IBAN)": "Email and IBAN pattern",
  "generated filter": "Generated Fluent Bit filter",
};

const SOURCES: Record<string, string> = {
  "app-json-ascii": "JSON with \\u escapes",
  "csv-export": "CSV export, “Surname, First name”",
  "sepa-debug": "Lower-case IBAN, “holder=” name",
  "form-v2": "Single-digit birth dates",
  audit: "Audit lines (no personal data)",
};

export function Privacy({ pii, heldout }: { pii: Data["pii"]; heldout: Data["heldout"] }) {
  return (
    <div style={{ display: "grid", gap: space[7] }}>
      <div role="list" aria-label="Personal data that reached Loki" style={{ display: "grid", gap: space[4] }}>
        {Object.entries(pii.methods).map(([k, m]) => {
          const leak = 1 - m.recall;
          return (
            <div role="listitem" key={k} style={{ display: "grid", gridTemplateColumns: `${space[9] * 2.4}px 1fr ${space[9]}px`, gap: space[4], alignItems: "center" }}>
              <span style={{ fontWeight: weight.semibold }}>{LABELS[k] ?? k}</span>
              <div style={{ height: space[5], background: color.panel, borderRadius: radius.sm }}>
                <div style={{ width: `${Math.max(leak * 100, 0.4)}%`, height: "100%", background: leak > 0.05 ? color.held : color.approved, borderRadius: radius.sm }} />
              </div>
              <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: weight.heavy }}>{pct(leak)}</span>
            </div>
          );
        })}
        <p style={{ margin: 0, color: color.muted, fontSize: size.sm }}>
          Share of {pii.methods["none"]?.instances.toLocaleString("en")} pieces of personal data in {pii.lines.toLocaleString("en")} log lines
          that reach Loki. The generated filter finds {pct(pii.methods["generated filter"].precision)} of its matches correctly, so audit lines stay readable.
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${space[9] * 3.2}px, 1fr))`, gap: space[7] }}>
        <table style={{ borderCollapse: "collapse", fontSize: size.sm }}>
          <caption style={{ textAlign: "left", fontWeight: weight.heavy, fontSize: size.md, paddingBottom: space[2] }}>Formats the rules were written for</caption>
          <tbody>
            {Object.entries(pii.by_kind).map(([k, r]) => (
              <tr key={k} style={{ borderTop: `${stroke.hair}px solid ${color.line}` }}>
                <th scope="row" style={{ textAlign: "left", fontWeight: weight.regular, padding: `${space[2]}px 0` }}>{k}</th>
                <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{r == null ? "–" : `${pct(r)} found`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <table style={{ borderCollapse: "collapse", fontSize: size.sm }}>
          <caption style={{ textAlign: "left", fontWeight: weight.heavy, fontSize: size.md, paddingBottom: space[2] }}>
            Held out: formats nobody wrote rules for ({pct(heldout.logs.recall)} found)
          </caption>
          <tbody>
            {Object.entries(heldout.logs.by_source).map(([k, s]) => (
              <tr key={k} style={{ borderTop: `${stroke.hair}px solid ${color.line}` }}>
                <th scope="row" style={{ textAlign: "left", fontWeight: weight.regular, padding: `${space[2]}px 0` }}>{SOURCES[k] ?? k}</th>
                <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", color: s.instances && s.recall < 0.9 ? color.held : color.ink }}>
                  {s.instances ? `${pct(s.recall)} found` : `${s.false_finds} false finds`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
