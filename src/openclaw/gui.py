import modal
from src.infrastructure.modal_app import app, openclaw_image, config, secrets

@app.function(
    image=openclaw_image,
    secrets=secrets,
    env=config.env,
    # OpenClaw can run perfectly fine on a standard CPU node.
    cpu=1.0,
    memory=2048
)
@modal.web_server(port=int(config.env["PORT"]))
def openclaw_gui():
    """
    Hosts the built-in OpenClaw GUI here.
    It routes its internal port to a secure, public-facing Modal web endpoint.
    """
    import subprocess

    port = config.env["PORT"]
    print(f"Starting OpenClaw Gateway on internal port {port}...")

    # We use subprocess to run the long-lived openclaw process
    # `modal.web_server` takes care of proxying the external request to localhost:PORT
    # OpenClaw's CLI should be run in verbose mode to capture logs.
    # Note: We must wait() for the subprocess, otherwise the function returns
    # immediately and the Modal container exits, causing the link to keep spooling.
    process = subprocess.Popen(
        ["openclaw", "gateway", "--port", port, "--verbose"]
    )
    process.wait()
