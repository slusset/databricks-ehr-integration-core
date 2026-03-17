terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
  }
}

provider "databricks" {
  # Auth configured via environment variables or ~/.databrickscfg
  # DATABRICKS_HOST, DATABRICKS_TOKEN
}

# --- Secret scope for EHR credentials ---

resource "databricks_secret_scope" "ehr_writeback" {
  name = "ehr-writeback"
}

# Example: Epic private key (value supplied via terraform.tfvars, NOT committed)
resource "databricks_secret" "epic_private_key" {
  scope        = databricks_secret_scope.ehr_writeback.name
  key          = "epic-private-key-pem"
  string_value = var.epic_private_key_pem
}

resource "databricks_secret" "epic_client_id" {
  scope        = databricks_secret_scope.ehr_writeback.name
  key          = "epic-client-id"
  string_value = var.epic_client_id
}

# --- Unity Catalog schema ---

resource "databricks_schema" "ehr_writeback" {
  catalog_name = var.catalog_name
  name         = "ehr_writeback"
  comment      = "EHR write-back integration tables"
}
