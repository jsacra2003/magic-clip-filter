variable "project_name" {
  type        = string
  description = "Project name used as a base for resource naming"
  default     = "magic-clip-filter"
}

variable "dev_project_id" {
  type        = string
  description = "Google Cloud Project ID for resource deployment."
}

variable "region" {
  type        = string
  description = "Google Cloud region for resource deployment."
  default     = "europe-west1"
}

variable "repository_owner" {
  type        = string
  description = "GitHub username or organisation that owns the repository."
}

variable "repository_name" {
  type        = string
  description = "GitHub repository name to connect to Cloud Build."
}

variable "github_pat_secret_id" {
  type        = string
  description = "Secret Manager secret ID that holds the GitHub Personal Access Token."
  default     = "github-pat"
}

variable "telemetry_logs_filter" {
  type        = string
  description = "Log Sink filter for agent telemetry logs."
  default     = "labels.service_name=\"magic-clip-filter\" labels.type=\"agent_telemetry\""
}

variable "feedback_logs_filter" {
  type        = string
  description = "Log Sink filter for feedback logs."
  default     = "jsonPayload.log_type=\"feedback\" jsonPayload.service_name=\"magic-clip-filter\""
}

variable "app_sa_roles" {
  description = "Roles assigned to the agent runtime service account."
  type        = list(string)
  default = [
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/bigquery.user",
  ]
}
