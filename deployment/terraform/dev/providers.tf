terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.13.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.13.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7.0"
    }
  }
}

# Default provider used by all resources
provider "google" {
  project = var.dev_project_id
  region  = var.region
}

# Beta provider — required by google_project_service_identity in apis.tf
provider "google-beta" {
  project = var.dev_project_id
  region  = var.region
}
