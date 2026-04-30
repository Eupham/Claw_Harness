
import json
import os
import pathlib
import subprocess
import time
import urllib.request
import threading

import modal


APP_NAME = 'openclaw-qwen-real-ui-v2'
MODEL_ID = 'Qwen/Qwen1.5-0.5B-Chat'
SERVED_MODEL_NAME = 'qwen25-coder-7b'
GPU = 'A10G'
MAX_MODEL_LEN = 8192
VLLM_API_KEY = 'modal-local-vllm'
OPENCLAW_GATEWAY_TOKEN = 'ucNIk6vnyOTfamLp7NAVzJd9b-W7Y9PjQQ5kbF6Jc38LAYHelxPo9FEkYunwEbrN'

OPENCLAW_PORT = 18789
VLLM_PORT = 8000

app = modal.App(APP_NAME)

hf_cache = modal.Volume.from_name(f"{APP_NAME}-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name(f"{APP_NAME}-vllm-cache", create_if_missing=True)
openclaw_home = modal.Volume.from_name(f"{APP_NAME}-openclaw-home", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "curl",
        "ca-certificates",
        "gnupg",
        "git",
        "lsof",
        "psmisc",
        "procps",
    )
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "node --version",
        "npm --version",
        "npm install -g openclaw@latest",
        "npm install -g "
        "@agentclientprotocol/claude-agent-acp@0.31.0 "
        "@homebridge/ciao@^1.3.6 "
        "@modelcontextprotocol/sdk@1.29.0 "
        "@zed-industries/codex-acp@0.12.0 "
        "acpx@0.6.1 "
        "chokidar@^5.0.0 "
        "commander@^14.0.3 "
        "express@5.2.1 "
        "playwright-core@1.59.1 "
        "semver@7.7.4 "
        "tslog@^4.10.2 "
        "typebox@1.1.33 "
        "undici@8.1.0 "
        "ws@^8.20.0 "
        "zod@^4.3.6",
    )
    .pip_install(
        "vllm",
        "huggingface_hub[hf_transfer]",
        "requests",
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
    })
)


def _write_openclaw_config():
    home = pathlib.Path("/mnt/openclaw-home")
    dot_home = home / ".openclaw"
    root_dot_home = pathlib.Path("/root/.openclaw")

    home.mkdir(parents=True, exist_ok=True)
    dot_home.mkdir(parents=True, exist_ok=True)
    root_dot_home.mkdir(parents=True, exist_ok=True)

    config = {
        "gateway": {
            "mode": "local",
            "auth": {
                "mode": "none"
            },
            "controlUi": {
                "enabled": True,
                "allowedOrigins": ["*"]
            }
        },
        "agents": {
            "defaults": {
                "model": {
                    "primary": f"modal-local/{SERVED_MODEL_NAME}"
                }
            }
        },
        "models": {
            "mode": "merge",
            "providers": {
                "modal-local": {
                    "baseUrl": f"http://127.0.0.1:{VLLM_PORT}/v1",
                    "apiKey": VLLM_API_KEY,
                    "api": "openai-completions",
                    "models": [
                        {
                            "id": SERVED_MODEL_NAME,
                            "name": f"{MODEL_ID} via local vLLM",
                            "reasoning": False,
                            "input": ["text"],
                            "cost": {
                                "input": 0,
                                "output": 0,
                                "cacheRead": 0,
                                "cacheWrite": 0
                            },
                            "contextWindow": MAX_MODEL_LEN,
                            "contextTokens": MAX_MODEL_LEN,
                            "maxTokens": 4096,
                            "compat": {
                                "requiresStringContent": True
                            }
                        }
                    ]
                }
            }
        }
    }

    paths = [
        home / "openclaw.json",
        dot_home / "openclaw.json",
        root_dot_home / "openclaw.json",
    ]

    for path in paths:
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"[modal-openclaw] wrote OpenClaw config: {path}", flush=True)

    token_path = home / "OPENCLAW_GATEWAY_TOKEN.txt"
    token_path.write_text(OPENCLAW_GATEWAY_TOKEN + "\n", encoding="utf-8")
    print(f"[modal-openclaw] wrote token file: {token_path}", flush=True)


def _wait_for_http(url, *, label, headers=None, timeout_s=1200, process=None):
    deadline = time.time() + timeout_s
    last_error = None

    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"{label} exited early with code {process.returncode}. "
                f"Last wait error: {last_error}"
            )

        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=5) as response:
                status = getattr(response, "status", 200)
                if 200 <= status < 500:
                    print(f"[modal-openclaw] {label} is ready: {url}", flush=True)
                    return
        except Exception as exc:
            last_error = repr(exc)
            print(f"[modal-openclaw] waiting for {label}: {last_error}", flush=True)

        time.sleep(3)

    raise TimeoutError(f"Timed out waiting for {label}: {url}. Last error: {last_error}")


@app.function(
    image=image,
    gpu=GPU,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/mnt/vllm-cache": vllm_cache,
        "/mnt/openclaw-home": openclaw_home,
    },
    timeout=60 * 60,
    max_containers=1,
)
@modal.web_server(port=OPENCLAW_PORT, startup_timeout=30 * 60)
def openclaw_ui():
    os.environ["HOME"] = "/mnt/openclaw-home"
    os.environ["OPENCLAW_HOME"] = "/mnt/openclaw-home"
    os.environ["OPENCLAW_CONFIG_PATH"] = "/mnt/openclaw-home/openclaw.json"

    os.environ["HF_HOME"] = "/root/.cache/huggingface"
    os.environ["VLLM_CACHE_ROOT"] = "/mnt/vllm-cache"
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = "/mnt/vllm-cache/torch_compile_cache"

    pathlib.Path("/mnt/vllm-cache").mkdir(parents=True, exist_ok=True)
    pathlib.Path("/mnt/openclaw-home").mkdir(parents=True, exist_ok=True)

    _write_openclaw_config()

    vllm_cmd = [
        "vllm",
        "serve",
        MODEL_ID,
        "--served-model-name",
        SERVED_MODEL_NAME,
        "--host",
        "127.0.0.1",
        "--port",
        str(VLLM_PORT),
        "--dtype",
        "auto",
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--gpu-memory-utilization",
        "0.90",
        "--api-key",
        VLLM_API_KEY,
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "hermes",
    ]

    print("[modal-openclaw] starting vLLM:", " ".join(vllm_cmd), flush=True)
    vllm_proc = subprocess.Popen(vllm_cmd)

    _wait_for_http(
        f"http://127.0.0.1:{VLLM_PORT}/v1/models",
        label="vLLM",
        headers={"Authorization": f"Bearer {VLLM_API_KEY}"},
        timeout_s=20 * 60,
        process=vllm_proc,
    )

    openclaw_cmd = [
        "openclaw",
        "gateway",
        "run",
        "--port",
        str(OPENCLAW_PORT),
        "--bind",
        "lan",
        "--auth",
        "none",
        "--allow-unconfigured",
        "--verbose",
    ]

    safe_cmd = [
        "[token-hidden]" if item == OPENCLAW_GATEWAY_TOKEN else item
        for item in openclaw_cmd
    ]

    print("[modal-openclaw] starting OpenClaw:", " ".join(safe_cmd), flush=True)

    subprocess.Popen(openclaw_cmd)

    def auto_approve_devices():
        while True:
            time.sleep(5)
            try:
                subprocess.run(["openclaw", "devices", "approve", "--latest"], env=os.environ, capture_output=True)
            except Exception as e:
                pass

    threading.Thread(target=auto_approve_devices, daemon=True).start()

    print("[modal-openclaw] OpenClaw process launched; Modal will expose port 18789.", flush=True)
