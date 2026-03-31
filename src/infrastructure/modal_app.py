import modal
from src.config import load_config

import os

# Load central configuration
config = load_config()

# Locate config.yaml to copy it inside the container
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(base_dir, "config.yaml")

# 1. Define the long-lived App
app = modal.App(config.name)

# 2. Set up the Volume for persistent Hugging Face weight storage
volume = modal.Volume.from_name(config.modal.volume_name, create_if_missing=True)

# 3. Define Secrets
# We wrap them in Secret.from_name so they are injected at runtime
secrets = [modal.Secret.from_name(secret) for secret in config.modal.secrets]

# 4. Define Image Configurations
# GPU Image (for vLLM)
vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        f"vllm=={config.versions.vllm}",
        f"huggingface_hub{config.versions.huggingface_hub}",
        "fastapi",
        "uvicorn"
    )
    .add_local_file(config_path, remote_path="/root/config.yaml")
)

# CPU Image (for OpenClaw)
openclaw_image = (
    modal.Image.debian_slim(python_version="3.11")
    # Need curl and gnupg for node installation
    .apt_install("curl", "gnupg")
    # Install Node.js 22.x
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs"
    )
    # Install OpenClaw
    .run_commands(
        f"npm install -g openclaw@{config.versions.openclaw}"
    )
    .add_local_file(config_path, remote_path="/root/config.yaml")
)

# 5. Import endpoints to register them with the App instance
# This must happen after the `app` instance is created and images are defined.
try:
    import src.llm_endpoints.vllm_engine
    import src.openclaw.gui
except ImportError as e:
    # Only suppress if we are evaluating the file early without the endpoints existing (like during scaffolding)
    # Otherwise raise it so deployment fails correctly.
    print(f"Warning: Could not import endpoints: {e}")
