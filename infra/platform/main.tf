# Identity and secrets for every authority, from the same tenants/*.yaml that Argo CD reads.
terraform {
  required_version = ">= 1.8.0"
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.0"
    }
    keycloak = {
      source  = "keycloak/keycloak"
      version = "~> 5.2"
    }
  }
}

provider "vault" {}
provider "keycloak" {}

locals {
  tenants = {
    for f in fileset("${path.module}/../../tenants", "*.yaml") :
    trimsuffix(f, ".yaml") => yamldecode(file("${path.module}/../../tenants/${f}"))
  }
  groups = merge([
    for name, t in local.tenants : {
      for g in t.access.groups : "${name}/${g.name}" => { tenant = name, group = g.name, roles = g.roles }
    }
  ]...)
  roles = merge([
    for name, t in local.tenants : {
      for r in ["inquiry-router", "audit-reader"] : "${name}/${r}" => { tenant = name, role = r }
    }
  ]...)
}

# ------------------------------------------------------------------------------------------------ Vault

resource "vault_policy" "tenant" {
  for_each = local.tenants
  name     = "sov-${each.key}"
  policy   = templatefile("${path.module}/../templates/vault-policy.hcl.tftpl", { tenant = each.key })
}

resource "vault_kubernetes_auth_backend_role" "tenant" {
  for_each                         = local.tenants
  backend                          = "kubernetes"
  role_name                        = "sov-${each.key}"
  bound_service_account_names      = ["sov-model"]
  bound_service_account_namespaces = ["sov-${each.key}"]
  token_policies                   = [vault_policy.tenant[each.key].name]
  token_ttl                        = 900
}

# --------------------------------------------------------------------------------------------- Keycloak

resource "keycloak_realm" "tenant" {
  for_each              = local.tenants
  realm                 = each.key
  display_name          = each.value.display_name
  ssl_required          = "external"
  access_token_lifespan = "5m"
  security_defenses {
    brute_force_detection {
      permanent_lockout = false
    }
  }
}

resource "keycloak_role" "tenant" {
  for_each = local.roles
  realm_id = keycloak_realm.tenant[each.value.tenant].id
  name     = each.value.role
}

resource "keycloak_group" "tenant" {
  for_each = local.groups
  realm_id = keycloak_realm.tenant[each.value.tenant].id
  name     = each.value.group
}

resource "keycloak_group_roles" "tenant" {
  for_each = local.groups
  realm_id = keycloak_realm.tenant[each.value.tenant].id
  group_id = keycloak_group.tenant[each.key].id
  role_ids = [for r in each.value.roles : keycloak_role.tenant["${each.value.tenant}/${r}"].id]
}

resource "keycloak_openid_client" "api" {
  for_each    = local.tenants
  realm_id    = keycloak_realm.tenant[each.key].id
  client_id   = "inquiry-router-api"
  access_type = "BEARER-ONLY"
}

resource "keycloak_openid_client" "portal" {
  for_each                     = local.tenants
  realm_id                     = keycloak_realm.tenant[each.key].id
  client_id                    = "inquiry-portal"
  access_type                  = "PUBLIC"
  standard_flow_enabled        = true
  direct_access_grants_enabled = false
  pkce_code_challenge_method   = "S256"
  valid_redirect_uris          = ["https://${each.key}.portal.example/*"]
  web_origins                  = ["https://${each.key}.portal.example"]
}

resource "keycloak_openid_audience_protocol_mapper" "portal" {
  for_each                 = local.tenants
  realm_id                 = keycloak_realm.tenant[each.key].id
  client_id                = keycloak_openid_client.portal[each.key].id
  name                     = "audience"
  included_client_audience = keycloak_openid_client.api[each.key].client_id
}
