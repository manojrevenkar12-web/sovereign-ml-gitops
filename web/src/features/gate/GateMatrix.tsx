import { motion } from "framer-motion";
import { useState } from "react";
import type { Data, Policy, ReleaseRow } from "../../shared/data/types";
import { authority } from "../../shared/format";
import { color, leading, motion as m, radius, size, space, stroke, weight } from "../../shared/theme/tokens";
import { Segmented } from "../../shared/ui/Segmented";
import { EmptyNotice } from "../../shared/ui/States";

const KINDS: { key: string; label: string }[] = [
  { key: "refresh", label: "Fresh export" },
  { key: "unredacted", label: "Skipped pseudonymisation" },
  { key: "wrong-tenant", label: "Another authority's export" },
  { key: "stale", label: "Export from before a reorganisation" },
  { key: "label-noise", label: "Export bug scrambled 30% of labels" },
  { key: "missing-urgent", label: "Hazard reports lost upstream" },
];

const POLICIES: { value: Policy; label: string }[] = [
  { value: "gate", label: "Release gate" },
  { value: "accuracy_only", label: "Accuracy only" },
  { value: "always", label: "Always ship" },
];

const signed = (x: number) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(1)}`;

function shipped(r: ReleaseRow, p: Policy): boolean {
  return p === "gate" ? r.gate : p === "accuracy_only" ? r.accuracy_only : true;
}

function Cell({ r, policy }: { r: ReleaseRow; policy: Policy }) {
  const ship = shipped(r, policy);
  const tone = r.bad ? color.held : color.approved;
  const what = `${authority(r.tenant)}, seed ${r.seed}: ${r.bad ? `faulty (${r.why_bad.join("; ")})` : "good"}, ${ship ? "shipped" : "held"}`;
  return (
    <motion.div
      role="img"
      aria-label={what}
      title={policy === "gate" ? `${what}. Gate: ${r.gate_summary}` : what}
      animate={{ backgroundColor: ship ? tone : color.card }}
      transition={{ duration: m.base, ease: m.ease }}
      style={{ aspectRatio: "1", border: `${stroke.rule}px solid ${tone}`, borderRadius: radius.sm }}
    />
  );
}

export function GateMatrix({ release }: { release: Data["release"] }) {
  const [policy, setPolicy] = useState<Policy>("gate");
  if (release.rows.length === 0) return <EmptyNotice what="release candidates" command="python scripts/release_eval.py" />;
  const o = release.policies[policy];
  const cols = [...new Set(release.rows.map((r) => `${r.tenant}|${r.seed}`))].sort();
  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: space[6], alignItems: "center", marginBottom: space[6] }}>
        <Segmented label="Release policy" options={POLICIES} value={policy} onChange={setPolicy} />
        <dl style={{ display: "flex", flexWrap: "wrap", gap: space[6], margin: 0 }}>
          {[
            [`${o.bad_shipped} of ${o.bad_total}`, "faulty releases reached citizens"],
            [`${o.privacy_breaches_shipped}`, "models trained on raw personal data went live"],
            [`${o.good_held} of ${o.good_total}`, "good releases held back"],
          ].map(([n, label]) => (
            <div key={label}>
              <dt style={{ fontSize: size.xxl, fontWeight: weight.heavy, lineHeight: leading.tight, fontVariantNumeric: "tabular-nums" }}>{n}</dt>
              <dd style={{ margin: 0, color: color.muted, fontSize: size.sm, maxWidth: `${space[9] * 2}px` }}>{label}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: `minmax(${space[9] * 2.4}px, 1.4fr) repeat(${cols.length}, minmax(${space[6]}px, ${space[7]}px))`, gap: space[2], alignItems: "center", minWidth: space[9] * 7 }}>
          <span />
          {cols.map((c, i) => {
            const [tenant, seed] = c.split("|");
            const first = i === 0 || cols[i - 1].split("|")[0] !== tenant;
            return (
              <span key={c} style={{ fontSize: size.xs, color: color.muted, textAlign: "center" }}>
                {first ? authority(tenant) : ""}
                <br />
                <span aria-label={`seed ${seed}`}>{seed}</span>
              </span>
            );
          })}
          {KINDS.map((k) => (
            <div key={k.key} style={{ display: "contents" }}>
              <span style={{ fontSize: size.sm, fontWeight: weight.semibold }}>{k.label}</span>
              {cols.map((c) => {
                const r = release.rows.find((x) => `${x.tenant}|${x.seed}` === c && x.candidate === k.key);
                return r ? <Cell key={c} r={r} policy={policy} /> : <span key={c} />;
              })}
            </div>
          ))}
        </div>
      </div>
      <p style={{ color: color.muted, fontSize: size.sm, marginTop: space[5] }}>
        Filled: shipped. Outlined: held. Red: faulty by the truth of the simulation (worse than the model it replaces, trained on raw
        personal data, or missing hazard reports); green: good. The good releases the gate held scored between{" "}
        {signed(Math.min(...release.held_good_true_diff_pts))} and {signed(Math.max(...release.held_good_true_diff_pts))} points against
        the model already running, which kept serving: the price of deciding on 600 validation inquiries.
      </p>
    </div>
  );
}
