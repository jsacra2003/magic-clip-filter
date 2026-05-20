# Firestore database — stores posted clip records for duplicate detection
resource "google_firestore_database" "default" {
  project     = var.dev_project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.services]
}

# Grant app SA read/write access to Firestore (used by the LinkedIn MCP server)
resource "google_project_iam_member" "app_sa_firestore" {
  project    = var.dev_project_id
  role       = "roles/datastore.user"
  member     = "serviceAccount:${google_service_account.app_sa.email}"
  depends_on = [google_firestore_database.default]
}
