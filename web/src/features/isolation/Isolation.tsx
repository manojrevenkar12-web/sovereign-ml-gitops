import type { Data } from "../../shared/data/types";
import { color, size, space, stroke, weight } from "../../shared/theme/tokens";
import { EmptyNotice } from "../../shared/ui/States";

const LAYERS: Record<string, string> = {
  vault: "Vault: read, list or write another authority's secrets",
  keycloak: "Keycloak: call another authority's router with your realm's token",
  loki: "Loki: read another authority's logs through Grafana",
  network: "Network: open a connection to another authority's pods",
};

export function Isolation({ isolation }: { isolation: Data["isolation"] }) {
  const rows = Object.entries(isolation);
  if (rows.length === 0) return <EmptyNotice what="isolation probes" command="python scripts/isolation_check.py" />;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ textAlign: "left", fontSize: size.sm, color: color.muted }}>
          <th scope="col" style={{ fontWeight: weight.regular, padding: `${space[2]}px 0` }}>Attempt</th>
          <th scope="col" style={{ fontWeight: weight.regular, textAlign: "right" }}>Across authorities</th>
          <th scope="col" style={{ fontWeight: weight.regular, textAlign: "right" }}>Own (control)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([k, l]) => (
          <tr key={k} style={{ borderTop: `${stroke.hair}px solid ${color.line}` }}>
            <th scope="row" style={{ textAlign: "left", fontWeight: weight.semibold, padding: `${space[3]}px ${space[4]}px ${space[3]}px 0` }}>{LAYERS[k] ?? k}</th>
            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: weight.heavy, color: l.cross_tenant_allowed ? color.held : color.approved }}>
              {l.cross_tenant_allowed} of {l.cross_tenant} allowed
            </td>
            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", color: color.muted }}>
              {l.own_allowed} of {l.own} allowed
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
