# Discovery & Documentation Notes

## Modal Infrastructure
* **Apps**: Defining a long-lived app is done using `app = modal.App("name")`.
* **Volumes**: Creating and mounting a volume for persistent storage:
  `volume = modal.Volume.from_name("name", create_if_missing=True)`
  This volume is mounted to functions via the `volumes` argument: `@app.function(volumes={"/path": volume})`.
* **Memory Snapshots**:
  - To dramatically reduce cold starts, CPU memory snapshots are enabled via `enable_memory_snapshot=True`.
  - For GPU snapshots (currently an alpha feature), we use `experimental_options={"enable_gpu_snapshot": True}`.
  - Initialization code to be snapshotted should go into a method decorated with `@modal.enter(snap=True)` inside a `modal.Cls`.
* **Web Endpoints**: To host a web server (like OpenClaw GUI) on a specific internal port and expose it publicly, use the `@modal.web_server(port=18789)` decorator.

## vLLM Engine
* **Version**: `0.7.3` (or the latest stable release).
* **Sleep Mode**: vLLM provides `/sleep` and `/wake_up` endpoints to offload the KV cache, which minimizes the memory footprint before taking a GPU snapshot.
* **Environment Variable**: `VLLM_SERVER_DEV_MODE=1` is required to expose the `/sleep` and `/wake_up` endpoints.
* **Serving**: Typically served on port `8000`.

## Qwen Models (Hugging Face)
* **Target Models**:
  - Instruct variant: `Qwen/Qwen2.5-7B-Instruct`
  - Coder variant: `Qwen/Qwen2.5-Coder-7B-Instruct`
* **Weights Storage**: `HF_HOME` should be set to point to the mounted Modal Volume so that vLLM automatically caches and reads from persistent storage.

## OpenClaw
* **Port**: The built-in OpenClaw GUI runs internally on port `18789`.
* **Installation**: Installed via `npm install -g openclaw@latest`. Needs Node 22.16+ or Node 24.
* **Execution**: `openclaw gateway --port 18789` for the backend, or combined UI/gateway depending on exact command layout. We will host this process on Modal's CPU function and route it securely.

## Dependencies & Versions
* `modal`: >=0.73.82
* `vllm`: ==0.7.3
* `huggingface_hub`: >=0.24.0
* `openclaw`: latest
