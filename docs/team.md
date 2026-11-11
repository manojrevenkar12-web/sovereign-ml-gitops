# How the DevOps team works on this platform

This page is for the sub-project lead and the DevOps engineers on the project, and for the development
teams who ship onto the platform.

## Who owns what

| Area | Owner | Reviewer |
|---|---|---|
| `tenants/` (onboarding, releases) | Platform on-call of the week | Authority contact for onboarding; ML lead for releases |
| `charts/`, `deploy/argocd/` | Platform team | One other platform engineer |
| `infra/` (OpenTofu) | Platform team | Security for Vault and Keycloak changes |
| `config/pii_rules.yaml` | Data protection champion in the platform team | Data protection officer for new kinds |
| `src/sov/ml/`, `config/platform.toml` | ML lead | Platform lead for gate thresholds |

`.gitlab/CODEOWNERS` enforces the reviewer column in GitLab.

## Git workflow

- **Trunk-based.** Short-lived branches from `main`, merged within two days. No long-running environment
  branches: environments differ by values files, not by branches.
- **Every change to a cluster is a merge request.** `kubectl edit` in production is drift. Argo CD's
  self-heal reverts it, and the alert asks who did it.
- **Conventional commits** (`feat:`, `fix:`, `release:`) so the changelog and the release merge requests
  can be generated.
- **Merge requests need a green pipeline and one review.** A gate threshold or a PII rule needs two reviews.

## Onboarding an authority (golden path, about one day)

1. Add `tenants/<name>.yaml`. Copy a similar authority's file and change the name, contact, critical
   departments and fine-tune location.
2. Run `python scripts/scaffold.py` and commit the generated files.
3. Open the merge request. The pipeline proves the new authority is isolated before anyone reviews it:
   `chart`, `isolation_check` and `tofu-plan` run.
4. After the merge, `infra/platform` creates the realm and the Vault role. Argo CD creates the namespace
   with no pods, because there is no adapter yet.
5. The first fine-tune runs. If the gate promotes, the release merge request pins the digest and the
   authority goes live.

## Teaching the DevOps habits

- **Pair on the first onboarding and the first release** with every new engineer and every development team
  that ships onto the platform.
- **Blameless reviews after every page,** written into `docs/runbook.md` when they change what we do.
- **A monthly drill:**
  - scale a router to zero and watch self-heal;
  - flip a byte in a staging artifact and watch the integrity alert;
  - push a log line with a test citizen's IBAN and find it redacted in Loki.

  The CI jobs `e2e-services` and `e2e-gitops` are the same drills, so new engineers can read them as
  documentation.
