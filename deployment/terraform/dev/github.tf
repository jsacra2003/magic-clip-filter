# Requires a GitHub PAT stored in Secret Manager before running terraform apply.
# Create it once with:
#   gcloud secrets create github-pat --project ge-bootcamp26lis-902
#   echo -n "ghp_YOUR_TOKEN" | gcloud secrets versions add github-pat --data-file=-
# The PAT needs scopes: repo, read:org

data "google_secret_manager_secret" "github_pat" {
  project   = var.dev_project_id
  secret_id = var.github_pat_secret_id
  depends_on = [google_project_service.services]
}

# Grant the Cloud Build service agent access to read the PAT secret
resource "google_secret_manager_secret_iam_member" "cloudbuild_secret_accessor" {
  project   = var.dev_project_id
  secret_id = data.google_secret_manager_secret.github_pat.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:service-${data.google_project.dev_project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
  depends_on = [google_project_service.services]
}

# Cloud Build v2 connection to GitHub using OAuth token
resource "google_cloudbuildv2_connection" "github_connection" {
  project  = var.dev_project_id
  location = var.region
  name     = "${var.project_name}-github-connection"

  github_config {
    authorizer_credential {
      oauth_token_secret_version = "${data.google_secret_manager_secret.github_pat.id}/versions/latest"
    }
  }

  depends_on = [
    google_project_service.services,
    google_secret_manager_secret_iam_member.cloudbuild_secret_accessor,
  ]
}

# Link the GitHub repository to the connection
resource "google_cloudbuildv2_repository" "repo" {
  project           = var.dev_project_id
  location          = var.region
  name              = var.repository_name
  parent_connection = google_cloudbuildv2_connection.github_connection.id
  remote_uri        = "https://github.com/${var.repository_owner}/${var.repository_name}.git"
  depends_on        = [google_cloudbuildv2_connection.github_connection]
}
