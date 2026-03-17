variable "catalog_name" {
  description = "Unity Catalog name for EHR write-back tables"
  type        = string
  default     = "ehr_writeback"
}

variable "epic_private_key_pem" {
  description = "PEM-encoded RSA private key for Epic backend JWT auth"
  type        = string
  sensitive   = true
}

variable "epic_client_id" {
  description = "Epic application client ID"
  type        = string
  sensitive   = true
}
