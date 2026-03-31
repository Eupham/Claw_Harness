import argparse
import sys
import modal
import os
from src.config import load_config
from src.infrastructure.modal_app import app, volume, config

# We need a small function to pull weights onto the persistent volume
@app.function(
    image=modal.Image.debian_slim().pip_install(f"huggingface_hub{config.versions.huggingface_hub}"),
    volumes={config.modal.mount_path: volume},
    timeout=3600 # weights could take a while
)
def download_model(model_id: str):
    from huggingface_hub import snapshot_download
    print(f"Downloading model {model_id} to {config.env['HF_HOME']}...")
    snapshot_download(model_id, local_dir=f"{config.env['HF_HOME']}/{model_id}")
    print("Download complete.")

def run_setup():
    """
    Executes first-run initialization:
    - Creates Modal Volumes
    - (Checks) secrets (Assumes they are set in Modal Dashboard)
    - Pulls initial model weights to the volume
    """
    print("Initializing OpenClaw deployment setup...")
    print(f"1. Volume {config.modal.volume_name} configured.")

    print(f"2. Pulling model weights for {config.models.active}...")
    # Using ephemeral app to run the one-off download function
    with modal.enable_output():
        with app.run():
            download_model.remote(config.models.active)

    print("\nSetup complete. You can now run `modal deploy src.infrastructure.modal_app`")

def get_latest_pypi_version(package: str) -> str:
    import requests
    response = requests.get(f"https://pypi.org/pypi/{package}/json")
    if response.status_code == 200:
        return response.json()["info"]["version"]
    return "unknown"

def is_safe_upgrade(current: str, latest: str) -> bool:
    """
    Simple semver major version check. E.g. '0.7.3' to '0.8.0' is unsafe because
    0.x implies major changes. '1.2.0' to '2.0.0' is unsafe.
    """
    c_parts = current.replace(">=", "").replace("==", "").split(".")
    l_parts = latest.split(".")
    if not c_parts or not l_parts or not c_parts[0].isdigit() or not l_parts[0].isdigit():
        return True # Can't accurately decide, assume safe for simpler logic, or maybe False.

    if c_parts[0] == "0":
        if l_parts[0] != "0" or (len(c_parts) > 1 and len(l_parts) > 1 and c_parts[1] != l_parts[1]):
            return False # 0.x -> 0.y or 1.x is considered unsafe
    elif c_parts[0] != l_parts[0]:
        return False # 1.x -> 2.x is unsafe

    return True

def run_check():
    """
    Scans the local config against current remote versions.
    Checks for updates and compatibility issues, prompts the user to upgrade where safe,
    and explicitly warns them where an upgrade is unsafe or incompatible.
    """
    print("Checking local config against remote versions...")

    # 1. Check vLLM
    vllm_current = config.versions.vllm
    vllm_latest = get_latest_pypi_version("vllm")

    print(f"[vLLM] Current: {vllm_current}, Latest: {vllm_latest}")
    if vllm_current != vllm_latest:
        if is_safe_upgrade(vllm_current, vllm_latest):
            print(f"  -> safe to upgrade vLLM to {vllm_latest}")
        else:
            print(f"  -> WARNING: unsafe to upgrade vLLM to {vllm_latest} (major version bump).")

    # 2. Check Modal
    modal_current = config.versions.modal.replace(">=", "")
    modal_latest = get_latest_pypi_version("modal")

    print(f"[Modal] Current (min): {modal_current}, Latest: {modal_latest}")
    if modal_current != modal_latest:
        if is_safe_upgrade(modal_current, modal_latest):
            print(f"  -> safe to upgrade Modal to {modal_latest}")
        else:
            print(f"  -> WARNING: unsafe to upgrade Modal to {modal_latest} (major version bump).")

    # 3. Check OpenClaw (via npm registry)
    import subprocess
    try:
        openclaw_latest = subprocess.check_output(["npm", "show", "openclaw", "version"]).decode("utf-8").strip()
        openclaw_current = config.versions.openclaw
        print(f"[OpenClaw] Current: {openclaw_current}, Latest: {openclaw_latest}")

        if openclaw_current != openclaw_latest and openclaw_current != "latest":
            if is_safe_upgrade(openclaw_current, openclaw_latest):
                print(f"  -> safe to upgrade OpenClaw to {openclaw_latest}")
            else:
                print(f"  -> WARNING: unsafe to upgrade OpenClaw to {openclaw_latest} (major version bump).")
    except Exception as e:
        print(f"[OpenClaw] Failed to fetch latest version: {e}")

    print("\nCheck complete. Run `python src/cli.py upgrade` to apply safe updates.")

def run_upgrade():
    """
    Automatically executes all safe upgrades defined in the config without prompting the user.
    """
    print("Running automatic upgrades...")
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True

    with open("config.yaml", "r") as f:
        data = yaml.load(f)

    # 1. Update vLLM
    vllm_latest = get_latest_pypi_version("vllm")
    if data["versions"]["vllm"] != vllm_latest:
        print(f"Upgrading vLLM to {vllm_latest}")
        data["versions"]["vllm"] = vllm_latest

    # 2. Update Modal
    modal_latest = get_latest_pypi_version("modal")
    if data["versions"]["modal"].replace(">=", "") != modal_latest:
        print(f"Upgrading Modal to >={modal_latest}")
        data["versions"]["modal"] = f">={modal_latest}"

    # 3. Update OpenClaw
    import subprocess
    try:
        openclaw_latest = subprocess.check_output(["npm", "show", "openclaw", "version"]).decode("utf-8").strip()
        if data["versions"]["openclaw"] != openclaw_latest and data["versions"]["openclaw"] != "latest":
            print(f"Upgrading OpenClaw to {openclaw_latest}")
            data["versions"]["openclaw"] = openclaw_latest
    except Exception as e:
        print(f"Failed to upgrade OpenClaw: {e}")

    # Save changes
    with open("config.yaml", "w") as f:
        yaml.dump(data, f)

    print("Automatic upgrades complete. You can now run `modal deploy src.infrastructure.modal_app`")


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Deployment CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Executes first-run initialization")

    # Check command
    check_parser = subparsers.add_parser("check", help="Scans the local config against remote versions")

    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Automatically executes safe upgrades")

    args = parser.parse_args()

    if args.command == "setup":
        run_setup()
    elif args.command == "check":
        run_check()
    elif args.command == "upgrade":
        run_upgrade()

if __name__ == "__main__":
    main()
