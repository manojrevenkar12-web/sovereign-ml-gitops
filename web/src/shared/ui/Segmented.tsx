import { motion } from "framer-motion";
import { color, font, motion as m, radius, size, space, stroke, weight } from "../theme/tokens";

/** A radio group; the ink block slides to the chosen option. */
export function Segmented<T extends string>({ label, options, value, onChange }: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} style={{ display: "inline-flex", flexWrap: "wrap", border: `${stroke.rule}px solid ${color.ink}`, borderRadius: radius.md, padding: space[1], gap: space[1] }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            style={{ position: "relative", font: `${weight.semibold} ${size.sm}px ${font.body}`, padding: `${space[2]}px ${space[4]}px`, border: "none", borderRadius: radius.sm, background: "transparent", color: on ? color.card : color.ink, cursor: "pointer" }}
          >
            {on && <motion.span layoutId={`seg-${label}`} transition={{ duration: m.fast, ease: m.ease }} style={{ position: "absolute", inset: 0, background: color.ink, borderRadius: radius.sm }} />}
            <span style={{ position: "relative" }}>{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
