output "cluster_id" {
  value = ionoscloud_k8s_cluster.sov.id
}

output "models_bucket" {
  value = ionoscloud_s3_bucket.models.name
}
