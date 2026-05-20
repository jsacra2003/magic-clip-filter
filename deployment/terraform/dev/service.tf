# Read base64-encoded dummy source tarball for initial Agent Engine creation.
# CI/CD will update source code after the first Terraform apply.
data "google_storage_bucket_object_content" "dummy_source_b64" {
  name   = "dummy/source-b64.txt"
  bucket = "agent-starter-pack"
}

resource "google_vertex_ai_reasoning_engine" "app" {
  display_name = var.project_name
  description  = "Magic Clip Filter — Trends → YouTube → PG-16 pipeline"
  region       = var.region
  project      = var.dev_project_id

  spec {
    agent_framework = "google-adk"
    service_account = google_service_account.app_sa.email

    deployment_spec {
      min_instances         = 1
      max_instances         = 10
      container_concurrency = 9

      resource_limits = {
        cpu    = "4"
        memory = "8Gi"
      }

      env {
        name  = "LOGS_BUCKET_NAME"
        value = google_storage_bucket.logs_data_bucket.name
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
        value = "true"
      }

      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }

      env {
        name  = "LINKEDIN_MCP_URL"
        value = google_cloud_run_v2_service.linkedin_mcp.uri
      }
    }

    source_code_spec {
      inline_source {
        source_archive = trimspace(data.google_storage_bucket_object_content.dummy_source_b64.content)
      }

      python_spec {
        entrypoint_module = "google_trends_agent.agent_engine_app"
        entrypoint_object = "agent_engine"
        requirements_file = "google_trends_agent/app_utils/.requirements.txt"
        version           = "3.12"
      }
    }
  }

  # Ignore source_code_spec changes — CI/CD updates these after first apply
  lifecycle {
    ignore_changes = [spec[0].source_code_spec]
  }

  depends_on = [google_project_service.services]
}
