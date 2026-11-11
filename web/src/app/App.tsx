import { ReleaseLane } from "../features/lane/ReleaseLane";
import { GateMatrix } from "../features/gate/GateMatrix";
import { FineTune } from "../features/finetune/FineTune";
import { Privacy } from "../features/privacy/Privacy";
import { Isolation } from "../features/isolation/Isolation";
import type { Data } from "../shared/data/types";
import { useJson, type Fetcher, browserFetch } from "../shared/data/useJson";
import { color, leading, measure, size, space, weight } from "../shared/theme/tokens";
import { Section } from "../shared/ui/Section";
import { ErrorNotice, Skeleton } from "../shared/ui/States";

export function App({ fetcher = browserFetch }: { fetcher?: Fetcher }) {
  const load = useJson<Data>("./data.json", fetcher);
  return (
    <main style={{ maxWidth: measure.page, margin: "0 auto", padding: `${space[8]}px ${space[5]}px` }}>
      <header style={{ marginBottom: space[8] }}>
        <h1 style={{ margin: 0, fontSize: size.display, fontWeight: weight.heavy, lineHeight: leading.tight, letterSpacing: "-0.025em", maxWidth: "18ch" }}>
          One platform, many authorities
        </h1>
        <p style={{ margin: `${space[4]}px 0 0`, maxWidth: `${measure.text}ch`, fontSize: size.lg, color: color.muted }}>
          Each authority gets its own fine-tuned inquiry router, released through GitLab CI, a release gate and Argo CD onto on-premises
          Kubernetes. Keycloak, Vault and Loki keep the authorities apart, and Fluent Bit removes citizens' data from the logs.
        </p>
      </header>
      {load.state === "loading" && <Skeleton label="Loading the release results" />}
      {load.state === "error" && <ErrorNotice message={load.message} onRetry={load.retry} />}
      {load.state === "ready" && (
        <>
          <div style={{ marginBottom: space[8] }}>
            <ReleaseLane tenants={load.data.tenants} />
          </div>
          <Section id="gate" title="54 releases with known faults, decided three ways" lede="Six kinds of release candidate per authority, three authorities, three seeds. The simulation knows which ones are faulty; the gate does not.">
            <GateMatrix release={load.data.release} />
          </Section>
          <Section id="finetune" title="A shared base and a small adapter per authority" lede="Routing accuracy on each authority's own inquiries, scored against the true department.">
            <FineTune finetune={load.data.finetune} heldout={load.data.heldout} />
          </Section>
          <Section id="privacy" title="What reaches Loki" lede="The filter is generated from one rule file and also pseudonymises the training data. On formats it was not written for, it misses most personal data; that is why a new log format needs a rule review before it ships.">
            <Privacy pii={load.data.pii} heldout={load.data.heldout} />
          </Section>
          <Section id="isolation" title="No authority reaches another" lede="Every probe asks whether one authority can do something to another, with its own access as the control. CI runs the same probes against live Keycloak, Vault, Loki and a kind cluster.">
            <Isolation isolation={load.data.isolation} />
          </Section>
          <footer style={{ borderTop: `1px solid ${color.line}`, paddingTop: space[5], color: color.muted, fontSize: size.sm }}>
            Every number on this page comes from <code>reports/*.json</code>, collected by <code>python scripts/report.py</code>.
          </footer>
        </>
      )}
    </main>
  );
}
