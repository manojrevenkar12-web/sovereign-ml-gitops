import { motion, useReducedMotion } from "framer-motion";
import { color, motion as m, radius, size, space, stroke, weight } from "../theme/tokens";

/** The office stamp: what the gate decided, pressed onto the release. */
export function Stamp({ kind, delay = 0 }: { kind: "approved" | "held"; delay?: number }) {
  const reduce = useReducedMotion();
  const c = kind === "approved" ? color.approved : color.held;
  return (
    <motion.span
      initial={reduce ? false : { scale: 1.6, opacity: 0, rotate: -9 }}
      animate={{ scale: 1, opacity: 1, rotate: -4 }}
      transition={{ delay, duration: m.base, ease: m.ease }}
      style={{
        display: "inline-block",
        padding: `${space[1]}px ${space[3]}px`,
        border: `${stroke.stamp}px double ${c}`,
        borderRadius: radius.sm,
        color: c,
        fontWeight: weight.heavy,
        fontSize: size.sm,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
      }}
    >
      {kind === "approved" ? "Approved" : "Held"}
    </motion.span>
  );
}
