# Artifact Registry repository for Docker images
resource "google_artifact_registry_repository" "docker_repo" {
  project       = var.dev_project_id
  location      = var.region
  repository_id = var.project_name
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# Grant CI/CD SA push access to Artifact Registry
resource "google_artifact_registry_repository_iam_member" "cicd_sa_ar_writer" {
  project    = var.dev_project_id
  location   = var.region
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cicd_sa.email}"
}

# Grant app SA pull access to Artifact Registry (needed to run the Cloud Run image)
resource "google_artifact_registry_repository_iam_member" "app_sa_ar_reader" {
  project    = var.dev_project_id
  location   = var.region
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.app_sa.email}"
}

# Secret Manager secret for the LinkedIn access token
resource "google_secret_manager_secret" "linkedin_access_token" {
  project   = var.dev_project_id
  secret_id = "linkedin-access-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.services]
}

# Placeholder secret version — replace with a real token via 'make linkedin-auth'
resource "google_secret_manager_secret_version" "linkedin_access_token_placeholder" {
  secret      = google_secret_manager_secret.linkedin_access_token.id
  secret_data = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Grant app SA access to read the LinkedIn token at Cloud Run runtime
resource "google_secret_manager_secret_iam_member" "app_sa_linkedin_token" {
  project   = var.dev_project_id
  secret_id = google_secret_manager_secret.linkedin_access_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app_sa.email}"
}

locals {
  linkedin_mcp_image = "${var.region}-docker.pkg.dev/${var.dev_project_id}/${var.project_name}/linkedin-mcp-server"
}

# Cloud Run service for the LinkedIn MCP server (SSE transport)
resource "google_cloud_run_v2_service" "linkedin_mcp" {
  name     = "${var.project_name}-linkedin-mcp"
  location = var.region
  project  = var.dev_project_id

  template {
    service_account = google_service_account.app_sa.email

    containers {
      # Placeholder image — CI/CD replaces this on first deploy
      image = "gcr.io/cloudrun/placeholder"

      env {
        name  = "MCP_TRANSPORT"
        value = "sse"
      }

      env {
        name = "LINKEDIN_ACCESS_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.linkedin_access_token.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  lifecycle {
    # CI/CD manages the image after initial creation
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    google_project_service.services,
    google_service_account.app_sa,
    google_secret_manager_secret_version.linkedin_access_token_placeholder,
    google_artifact_registry_repository.docker_repo,
  ]
}

# Allow public invocations — LinkedIn token is stored server-side in Secret Manager
resource "google_cloud_run_v2_service_iam_member" "linkedin_mcp_public" {
  project  = var.dev_project_id
  location = var.region
  name     = google_cloud_run_v2_service.linkedin_mcp.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
