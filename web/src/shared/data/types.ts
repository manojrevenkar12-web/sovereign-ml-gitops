export type Policy = "gate" | "accuracy_only" | "always";

export type PolicyOutcome = {
  bad_shipped: number;
  bad_total: number;
  good_held: number;
  good_total: number;
  privacy_breaches_shipped: number;
};

export type ReleaseRow = {
  seed: number;
  tenant: string;
  candidate: string;
  bad: boolean;
  why_bad: string[];
  gate: boolean;
  gate_summary: string;
  accuracy_only: boolean;
  true_accuracy: number;
  champion_true_accuracy: number;
};

export type Method = { recall: number; precision: number; instances: number; leaked: number; false_finds: number };

export type Layer = { cross_tenant: number; cross_tenant_allowed: number; own: number; own_allowed: number };

export type Tenant = {
  display_name: string;
  kind: string;
  live: boolean;
  adapter: string | null;
  fine_tune: string;
  release: string | null;
  val_accuracy: number | null;
};

export type Data = {
  finetune: {
    by_tenant: Record<string, { base: number; lora: number; full: number }>;
    overall: { base: number; lora: number; full: number };
    base_kb: number;
    adapter_kb: number;
    train_seconds: { lora: number; full: number };
  };
  release: {
    policies: Record<Policy, PolicyOutcome>;
    rows: ReleaseRow[];
    held_good_true_diff_pts: number[];
  };
  pii: {
    methods: Record<string, Method>;
    by_kind: Record<string, number | null>;
    lines: number;
  };
  isolation: Record<string, Layer>;
  heldout: {
    onboarding: {
      tenant: string;
      gate: { promote: boolean; summary: string };
      true_accuracy: { base: number; lora: number };
      true_critical_recall: number;
    };
    logs: { recall: number; precision: number; by_source: Record<string, { instances: number; recall: number; false_finds: number }> };
  };
  tenants: Record<string, Tenant>;
};
