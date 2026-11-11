variable "location" {
  description = "IONOS data centre location (de/txl Berlin, de/fra Frankfurt)"
  type        = string
  default     = "de/txl"
}

variable "k8s_version" {
  description = "Kubernetes version of the managed cluster"
  type        = string
  default     = "1.33.4"
}

variable "api_allow_list" {
  description = "Networks allowed to reach the Kubernetes API (the authorities' admin networks and the GitLab runners)"
  type        = list(string)
}

variable "finetune_max_nodes" {
  description = "Upper bound of the fine-tuning pool; it scales back down when no Job is pending"
  type        = number
  default     = 3
}
