# Burst capacity on a German sovereign cloud: the fine-tuning pool and the model bucket. Serving stays on
# the authorities' own clusters; only pseudonymised training data may come here (tenants/*.yaml fine_tune.where,
# enforced by the release gate's "training data pseudonymised" check).

resource "ionoscloud_datacenter" "sov" {
  name                = "sov-ml"
  location            = var.location
  description         = "Fine-tuning and model artifacts for the inquiry routers"
  sec_auth_protection = true
}

resource "ionoscloud_k8s_cluster" "sov" {
  name                  = "sov-ml"
  k8s_version           = var.k8s_version
  api_subnet_allow_list = var.api_allow_list
  maintenance_window {
    day_of_the_week = "Sunday"
    time            = "02:00:00Z"
  }
}

resource "ionoscloud_k8s_node_pool" "system" {
  name              = "system"
  datacenter_id     = ionoscloud_datacenter.sov.id
  k8s_cluster_id    = ionoscloud_k8s_cluster.sov.id
  k8s_version       = var.k8s_version
  availability_zone = "AUTO"
  storage_type      = "SSD"
  storage_size      = 100
  node_count        = 2
  cores_count       = 4
  ram_size          = 8192
  labels            = { "sov/pool" = "system" }
  maintenance_window {
    day_of_the_week = "Sunday"
    time            = "03:00:00Z"
  }
}

resource "ionoscloud_k8s_node_pool" "finetune" {
  name              = "finetune"
  datacenter_id     = ionoscloud_datacenter.sov.id
  k8s_cluster_id    = ionoscloud_k8s_cluster.sov.id
  k8s_version       = var.k8s_version
  availability_zone = "AUTO"
  storage_type      = "SSD"
  storage_size      = 200
  node_count        = 1
  cores_count       = 16
  ram_size          = 65536
  labels            = { "sov/pool" = "finetune" }
  auto_scaling {
    min_node_count = 1
    max_node_count = var.finetune_max_nodes
  }
  maintenance_window {
    day_of_the_week = "Sunday"
    time            = "03:30:00Z"
  }
}

resource "ionoscloud_s3_bucket" "models" {
  name = "sov-models"
}

resource "ionoscloud_s3_bucket_versioning" "models" {
  bucket = ionoscloud_s3_bucket.models.name
  versioning_configuration {
    status = "Enabled"
  }
}
