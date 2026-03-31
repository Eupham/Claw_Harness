import os
import time
import subprocess
import requests
import modal
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import ClientDisconnect

from src.infrastructure.modal_app import app, vllm_image, volume, config, secrets

# Global FastAPI App to serve as a proxy to the local vLLM server
fastapi_app = FastAPI(title="vLLM Proxy App")

def wait_for_server(url: str, timeout: int = 120):
    """Wait for the vLLM server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Server is ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    raise RuntimeError("Server did not start within the timeout.")


@app.cls(
    image=vllm_image,
    gpu=f"{config.gpu.type}:{config.gpu.count}" if config.gpu.count > 1 else config.gpu.type,
    volumes={config.modal.mount_path: volume},
    secrets=secrets,
    env=config.env,
    # Enable memory snapshot
    enable_memory_snapshot=config.gpu.memory_snapshot,
)
class VllmEngine:
    @modal.enter(snap=True)
    def start_server(self):
        """
        Initialization logic executed during the memory snapshot phase.
        It starts the vLLM API server as a subprocess, waits for it to be ready,
        and then calls the /sleep endpoint to clear the KV cache and offload weights.
        """
        print(f"Starting vLLM server for model {config.models.active}...")

        # Construct the vLLM server command
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", config.models.active,
            "--max-model-len", str(config.vllm.max_model_len),
            "--gpu-memory-utilization", str(config.vllm.gpu_memory_utilization),
            "--port", str(config.vllm.port),
            "--host", config.vllm.host
        ]

        # Ensure VLLM_SERVER_DEV_MODE=1 is set in the environment to expose /sleep and /wake_up
        env = os.environ.copy()
        env["VLLM_SERVER_DEV_MODE"] = "1"

        # Start the vLLM server as a background process
        self.process = subprocess.Popen(cmd, env=env)

        # Wait for the server to be ready
        health_url = f"http://{config.vllm.host}:{config.vllm.port}/health"
        wait_for_server(health_url)

        # Send /sleep request to offload KV cache before snapshot
        print("Putting vLLM engine to sleep before snapshotting...")
        sleep_url = f"http://{config.vllm.host}:{config.vllm.port}/sleep"
        try:
            response = requests.post(sleep_url)
            if response.status_code == 200:
                print("Engine is asleep. Ready for snapshot.")
            else:
                print(f"Failed to put engine to sleep: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Error calling /sleep: {e}")

    @modal.exit()
    def stop_server(self):
        """Terminate the vLLM server when the container exits."""
        if self.process:
            self.process.terminate()

    @modal.asgi_app()
    def web_endpoint(self):
        """
        Exposes the FastAPI app that proxies requests to the local vLLM server.
        It wakes up the vLLM engine if necessary.
        """
        import httpx

        # We create an async HTTP client for proxying requests
        client = httpx.AsyncClient(base_url=f"http://{config.vllm.host}:{config.vllm.port}", timeout=600.0)

        @fastapi_app.on_event("startup")
        async def on_startup():
            # Wake up the engine on the first request
            print("Waking up vLLM engine...")
            try:
                response = await client.post("/wake_up")
                if response.status_code == 200:
                    print("Engine is awake.")
                else:
                    print(f"Failed to wake up engine: {response.status_code} {response.text}")
            except Exception as e:
                print(f"Error calling /wake_up: {e}")

        @fastapi_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"])
        async def proxy(request: Request, path: str):
            """Proxy all requests to the underlying vLLM server."""
            url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))

            # Forward the request to the vLLM server
            req = client.build_request(
                request.method,
                url,
                headers=request.headers.raw,
                content=request.stream()
            )

            # Send the request and stream the response
            try:
                # Need to stream the response back
                response = await client.send(req, stream=True)

                async def stream_generator():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_generator(),
                    status_code=response.status_code,
                    headers=response.headers
                )
            except ClientDisconnect:
                print("Client disconnected.")
                return JSONResponse(status_code=499, content={"detail": "Client Disconnected"})
            except Exception as e:
                print(f"Proxy error: {e}")
                return JSONResponse(status_code=500, content={"detail": str(e)})

        return fastapi_app
