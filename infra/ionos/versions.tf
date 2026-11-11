terraform {
  required_version = ">= 1.8.0"
  required_providers {
    ionoscloud = {
      source  = "ionos-cloud/ionoscloud"
      version = "~> 6.7"
    }
  }
  # State in IONOS Object Storage (S3 API), in Germany. Credentials come from Vault in the pipeline.
  backend "s3" {
    bucket                      = "sov-tofu-state"
    key                         = "ionos/terraform.tfstate"
    region                      = "eu-central-3"
    endpoints                   = { s3 = "https://s3.eu-central-3.ionoscloud.com" }
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}

provider "ionoscloud" {}
