import logging
import os

import vertexai
from dotenv import load_dotenv
from google.adk.apps import App
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from vertexai.agent_engines.templates.adk import AdkApp

from magic_clip_pipeline.agent import root_agent
from google_trends_agent.app_utils.telemetry import setup_telemetry

load_dotenv()


class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        vertexai.init()
        setup_telemetry()
        super().set_up()
        logging.basicConfig(level=logging.INFO)
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location


gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

_app = App(root_agent=root_agent, name="magic_clip_pipeline")

agent_engine = AgentEngineApp(
    app=_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)
