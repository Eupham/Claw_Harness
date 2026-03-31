# OpenClaw with vLLM Qwen Deployment on Modal

This repository contains the configuration and source code to deploy OpenClaw alongside a vLLM-powered Qwen model on Modal infrastructure.

## Environment Variables

Before setting up and deploying, ensure you have the necessary API tokens exported in your local environment. **You do NOT need any OpenAI or Anthropic API keys.** We are using open-source models deployed via Modal.

You will need the following environment variables:

**For Terminal/Bash:**
```bash
# Modal Authentication (Required for Modal deployment)
export MODAL_TOKEN_ID="your_modal_token_id"
export MODAL_TOKEN_SECRET="your_modal_token_secret"

# Hugging Face Authentication (Required to download models, especially gated ones)
export HF_TOKEN="your_huggingface_api_token"
```

**For Python/Jupyter Notebooks:**
If you are running the deployment or testing code inside a Python script or Jupyter Notebook, you need to set the environment variables using the `os` module. Do not use `export` inside Python cells.
```python
import os

# Modal Authentication
os.environ["MODAL_TOKEN_ID"] = "your_modal_token_id"
os.environ["MODAL_TOKEN_SECRET"] = "your_modal_token_secret"

# Hugging Face Authentication
os.environ["HF_TOKEN"] = "your_huggingface_api_token"
```

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd <repository_name>
   ```

2. **Install requirements:**
   Install the necessary dependencies. This project strictly requires `modal>=1.4.1` and `vllm==0.18.1`.
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Modal Secrets:**
   You must set up Modal secrets so the deployment can access your Hugging Face token.
   The `config.yaml` expects a secret named `huggingface-token`.

   If you have the `HF_TOKEN` environment variable set, you can create the Modal secret using:
   ```bash
   modal secret create huggingface-token HF_TOKEN=$HF_TOKEN
   ```

## Configuration (`config.yaml`)

The `config.yaml` file holds the configuration for the Modal deployment, dependencies, models, and environment variables. The project uses `ruamel.yaml` to ensure formatting and comments are preserved when updated programmatically.

Key sections in `config.yaml`:
- **versions**: Enforces the required dependency versions.
- **modal**: Configuration for the Modal volume and required secrets.
- **models**: Specifies the Hugging Face models to use (default, coder, active).
- **gpu**: Defines the target GPU specification (e.g., A100:1) and whether to use memory snapshots.
- **env**: Environment variables passed directly to the Modal container. This section now contains documentation for the necessary local environment variables (`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `HF_TOKEN`).
- **vllm**: Settings for the vLLM engine, including port, host, max model length, and sleep mode for KV cache management.

## Running Tests

Before deployment, verify the configuration and setup:
```bash
pytest test_modal_gpu.py
```
*(Or simply `python test_modal_gpu.py` if configured as a script).*

## Deployment

Deploy the Modal app using the CLI (adjust the command based on the entry point if different):
```bash
modal deploy
```
*(Ensure you follow the Modal CLI usage as defined by your application's specific entry point in `src/`)*
