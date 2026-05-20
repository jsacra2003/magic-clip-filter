# Dedicated service account for CI/CD pipeline execution
resource "google_service_account" "cicd_sa" {
  account_id   = "${var.project_name}-cicd"
  display_name = "${var.project_name} CI/CD Service Account"
  project      = var.dev_project_id
  depends_on   = [google_project_service.services]
}

locals {
  cicd_roles = [
    "roles/aiplatform.user",
    "roles/storage.admin",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/cloudbuild.builds.builder",
    "roles/iam.serviceAccountUser",
    "roles/serviceusage.serviceUsageConsumer",
  ]
}

resource "google_project_iam_member" "cicd_sa_roles" {
  for_each   = toset(local.cicd_roles)
  project    = var.dev_project_id
  role       = each.value
  member     = "serviceAccount:${google_service_account.cicd_sa.email}"
  depends_on = [google_project_service.services]
}

# --- Trigger 1: PR checks — runs tests on every pull request targeting main ---
resource "google_cloudbuild_trigger" "pr_checks" {
  name            = "pr-checks-${var.project_name}"
  project         = var.dev_project_id
  location        = var.region
  description     = "Run unit and integration tests on pull requests"
  service_account = google_service_account.cicd_sa.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.repo.id
    pull_request {
      branch = "^main$"
    }
  }

  filename = ".cloudbuild/pr_checks.yaml"
  included_files = [
    "google_trends_agent/**",
    "agent04_media_check_agent/**",
    "agent05_youtube_highlights_agent/**",
    "magic_clip_pipeline/**",
    "tests/**",
    "pyproject.toml",
    "uv.lock",
  ]
  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  depends_on = [
    google_cloudbuildv2_repository.repo,
    google_service_account.cicd_sa,
    google_project_iam_member.cicd_sa_roles,
  ]
}

# --- Trigger 2: Deploy — deploys to Agent Engine on every push to main ---
resource "google_cloudbuild_trigger" "deploy" {
  name            = "deploy-${var.project_name}"
  project         = var.dev_project_id
  location        = var.region
  description     = "Deploy to Vertex AI Agent Engine on push to main"
  service_account = google_service_account.cicd_sa.id

  repository_event_config {
    repository = google_cloudbuildv2_repository.repo.id
    push {
      branch = "^main$"
    }
  }

  filename = ".cloudbuild/deploy.yaml"
  included_files = [
    "google_trends_agent/**",
    "agent04_media_check_agent/**",
    "agent05_youtube_highlights_agent/**",
    "magic_clip_pipeline/**",
    "pyproject.toml",
    "uv.lock",
  ]

  substitutions = {
    _PROJECT_ID          = var.dev_project_id
    _REGION              = var.region
    _LOGS_BUCKET_NAME    = google_storage_bucket.logs_data_bucket.name
    _APP_SERVICE_ACCOUNT = google_service_account.app_sa.email
  }

  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"

  depends_on = [
    google_cloudbuildv2_repository.repo,
    google_service_account.cicd_sa,
    google_project_iam_member.cicd_sa_roles,
  ]
}
