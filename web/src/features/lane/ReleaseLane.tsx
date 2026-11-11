import { motion, useReducedMotion } from "framer-motion";
import type { Data } from "../../shared/data/types";
import { pct, short } from "../../shared/format";
import { color, font, leading, motion as m, radius, size, space, stroke, weight } from "../../shared/theme/tokens";
import { Stamp } from "../../shared/ui/Stamp";
import { useNarrow } from "../../shared/ui/useNarrow";

export const STATIONS = ["Export", "Contract", "Pseudonymise", "Fine-tune", "Gate", "Merge request", "Argo CD"] as const;
const GATE = STATIONS.indexOf("Gate");
const TOKEN = space[5];

function reason(summary: string | null): string {
  if (!summary) return "no release yet";
  return summary.replace(/^hold: /, "");
}

/** Each authority's latest release travels the pipeline and stops where it stopped. */
export function ReleaseLane({ tenants }: { tenants: Data["tenants"] }) {
  const reduce = useReducedMotion();
  const narrow = useNarrow();
  const rows = Object.entries(tenants);
  const last = STATIONS.length - 1;
  return (
    <div role="list" aria-label="Latest release per authority" style={{ display: "grid", gap: space[6] }}>
      {!narrow && (
        <div aria-hidden style={{ display: "grid", gridTemplateColumns: `minmax(${space[9] * 2}px, 1fr) 4fr`, gap: space[5] }}>
          <span />
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${STATIONS.length}, 1fr)`, color: color.muted, fontSize: size.xs }}>
            {STATIONS.map((s, i) => (
              <span key={s} style={{ textAlign: i === 0 ? "left" : i === last ? "right" : "center", fontWeight: i === GATE ? weight.heavy : weight.regular, color: i === GATE ? color.ink : color.muted }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
      {rows.map(([name, t], row) => {
        const stop = t.live ? last : GATE;
        const pos = (stop / last) * 100;
        const delay = row * m.stagger;
        const arrive = reduce ? 0 : delay + m.travel;
        return (
          <div role="listitem" key={name} style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : `minmax(${space[9] * 2}px, 1fr) 4fr`, gap: narrow ? space[2] : space[5], alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: weight.heavy, fontSize: size.lg, lineHeight: leading.snug }}>{t.display_name}</div>
              <div style={{ color: color.muted, fontSize: size.sm }}>
                {t.kind} · fine-tunes {t.fine_tune === "ionos" ? "on IONOS Cloud" : "on premises"}
              </div>
            </div>
            <div>
              <div style={{ position: "relative", height: TOKEN + space[2] }}>
                <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: stroke.rule, background: color.line }} />
                {STATIONS.map((s, i) => (
                  <span key={s} aria-hidden style={{ position: "absolute", left: `calc(${(i / last) * 100}% - ${stroke.stamp}px)`, top: `calc(50% - ${space[2]}px)`, width: stroke.stamp * 2, height: space[4], background: i <= stop ? color.ink : color.line, borderRadius: radius.sm }} />
                ))}
                <motion.div
                  initial={reduce ? false : { width: "0%" }}
                  animate={{ width: `${pos}%` }}
                  transition={{ delay, duration: m.travel, ease: m.ease }}
                  style={{ position: "absolute", left: 0, top: "50%", height: stroke.stamp, marginTop: -1, background: t.live ? color.approved : color.held }}
                />
                <motion.div
                  aria-hidden
                  initial={reduce ? false : { left: `calc(0% - ${TOKEN / 2}px)` }}
                  animate={{ left: `calc(${pos}% - ${TOKEN / 2}px)` }}
                  transition={{ delay, duration: m.travel, ease: m.ease }}
                  style={{ position: "absolute", top: `calc(50% - ${TOKEN / 2}px)`, width: TOKEN, height: TOKEN, borderRadius: radius.pill, background: t.live ? color.approved : color.held, border: `${stroke.stamp}px solid ${color.card}`, boxShadow: `0 0 0 ${stroke.hair}px ${t.live ? color.approved : color.held}` }}
                />
              </div>
              <motion.div
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: arrive, duration: m.base }}
                style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: space[3], marginTop: space[2], fontSize: size.sm }}
              >
                <Stamp kind={t.live ? "approved" : "held"} delay={arrive} />
                {t.live ? (
                  <span>
                    Running adapter <code style={{ fontFamily: font.mono }}>{short(t.adapter)}</code>
                    {t.val_accuracy != null && <> · validation accuracy {pct(t.val_accuracy)}</>}
                  </span>
                ) : (
                  <span>
                    Stopped at the gate: {reason(t.release)}. Not live until the district supplies more labelled hazard reports.
                  </span>
                )}
              </motion.div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
