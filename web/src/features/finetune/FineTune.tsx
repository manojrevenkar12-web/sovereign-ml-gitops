import type { Data } from "../../shared/data/types";
import { authority, pct } from "../../shared/format";
import { color, radius, size, space, stroke, weight } from "../../shared/theme/tokens";

const LO = 0.4;
const at = (x: number) => `${((x - LO) / (1 - LO)) * 100}%`;
const MARK = space[4];

const SERIES = [
  { key: "base", label: "Shared base only", shape: "ring" },
  { key: "lora", label: "Base + the authority's adapter", shape: "dot" },
  { key: "full", label: "Full fine-tune per authority", shape: "square" },
] as const;

function Marker({ shape, x, label }: { shape: "ring" | "dot" | "square"; x: number; label: string }) {
  const common = { position: "absolute" as const, top: `calc(50% - ${MARK / 2}px)`, left: `calc(${at(x)} - ${MARK / 2}px)`, width: MARK, height: MARK };
  const style =
    shape === "ring"
      ? { ...common, borderRadius: radius.pill, border: `${stroke.rule}px solid ${color.muted}`, background: color.card }
      : shape === "dot"
        ? { ...common, borderRadius: radius.pill, background: color.approved }
        : { ...common, border: `${stroke.rule}px solid ${color.ink}`, background: "transparent" };
  return <span role="img" aria-label={label} title={label} style={style} />;
}

export function FineTune({ finetune, heldout }: { finetune: Data["finetune"]; heldout: Data["heldout"] }) {
  const rows: [string, { base: number; lora: number; full?: number }, boolean][] = [
    ...Object.entries(finetune.by_tenant).map(([k, v]) => [k, v, false] as [string, typeof v, boolean]),
    [heldout.onboarding.tenant, heldout.onboarding.true_accuracy, true],
  ];
  return (
    <div style={{ display: "grid", gap: space[7] }}>
      <div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: space[5], fontSize: size.sm, color: color.muted, marginBottom: space[5] }}>
          {SERIES.map((s) => (
            <span key={s.key} style={{ display: "inline-flex", alignItems: "center", gap: space[2] }}>
              <span style={{ position: "relative", width: MARK, height: MARK, display: "inline-block" }}>
                <Marker shape={s.shape} x={LO} label="" />
              </span>
              {s.label}
            </span>
          ))}
        </div>
        <div style={{ display: "grid", gap: space[4] }}>
          {rows.map(([name, v, held]) => (
            <div key={name} style={{ display: "grid", gridTemplateColumns: `${space[9] * 1.6}px 1fr`, gap: space[4], alignItems: "center" }}>
              <span style={{ fontWeight: weight.semibold }}>
                {authority(name)}
                {held && <span style={{ display: "block", color: color.muted, fontWeight: weight.regular, fontSize: size.xs }}>held out, scored once</span>}
              </span>
              <div style={{ position: "relative", height: space[6], borderBottom: `${stroke.hair}px solid ${color.line}` }}>
                {SERIES.map((s) => {
                  const x = (v as Record<string, number | undefined>)[s.key];
                  return x == null ? null : <Marker key={s.key} shape={s.shape} x={x} label={`${authority(name)}, ${s.label}: ${pct(x)}`} />;
                })}
                <span style={{ position: "absolute", right: 0, top: -space[1], fontSize: size.xs, color: color.muted }}>{pct(v.lora)}</span>
              </div>
            </div>
          ))}
          <div style={{ display: "grid", gridTemplateColumns: `${space[9] * 1.6}px 1fr`, gap: space[4] }}>
            <span />
            <div style={{ position: "relative", height: space[5], fontSize: size.xs, color: color.muted }}>
              {[0.4, 0.6, 0.8, 1].map((t) => (
                <span key={t} style={{ position: "absolute", left: at(t), transform: "translateX(-50%)" }}>
                  {pct(t, 0)}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
      <dl style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${space[9] * 2.2}px, 1fr))`, gap: space[6], margin: 0 }}>
        {[
          [`${finetune.adapter_kb.toFixed(0)} kB`, `per authority with an adapter, against ${(finetune.base_kb / 1024).toFixed(1)} MB for its own full model`],
          [`${finetune.train_seconds.lora.toFixed(1)} s`, `to fine-tune an adapter on CPU (${finetune.train_seconds.full.toFixed(1)} s for the full model)`],
          [pct(finetune.overall.full - finetune.overall.lora), "accuracy the full fine-tune still has over the adapter: the price of one shared base"],
        ].map(([n, label]) => (
          <div key={label} style={{ borderTop: `${stroke.rule}px solid ${color.ink}`, paddingTop: space[3] }}>
            <dt style={{ fontSize: size.xl, fontWeight: weight.heavy, fontVariantNumeric: "tabular-nums" }}>{n}</dt>
            <dd style={{ margin: 0, color: color.muted, fontSize: size.sm }}>{label}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
