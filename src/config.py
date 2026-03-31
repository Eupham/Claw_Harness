import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional
import os

@dataclass
class VersionsConfig:
    modal: str
    vllm: str
    huggingface_hub: str
    openclaw: str

@dataclass
class ModalConfig:
    volume_name: str
    mount_path: str
    secrets: List[str]

@dataclass
class ModelsConfig:
    default: str
    coder: str
    active: str

@dataclass
class GPUConfig:
    type: str
    count: int
    memory_snapshot: bool

@dataclass
class VLLMConfig:
    port: int
    host: str
    max_model_len: int
    gpu_memory_utilization: float
    sleep_mode: bool

@dataclass
class AppConfig:
    name: str
    versions: VersionsConfig
    modal: ModalConfig
    models: ModelsConfig
    gpu: GPUConfig
    env: Dict[str, str]
    vllm: VLLMConfig

def load_config(path: str = "config.yaml") -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    return AppConfig(
        name=data.get("name", "openclaw-qwen-deployment"),
        versions=VersionsConfig(**data.get("versions", {})),
        modal=ModalConfig(**data.get("modal", {})),
        models=ModelsConfig(**data.get("models", {})),
        gpu=GPUConfig(**data.get("gpu", {})),
        env=data.get("env", {}),
        vllm=VLLMConfig(**data.get("vllm", {}))
    )

if __name__ == "__main__":
    config = load_config()
    print("Config loaded successfully!")
    print(f"App Name: {config.name}")
    print(f"Active Model: {config.models.active}")
    print(f"Volume Name: {config.modal.volume_name}")
