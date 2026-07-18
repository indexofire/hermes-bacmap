#!/usr/bin/env python3
"""Switch Hermes Agent LLM provider between Z.AI / Ollama / vLLM.

Usage:
    python scripts/switch_llm.py zai       # Cloud API (GLM-5.2 via Z.AI)
    python scripts/switch_llm.py ollama    # Local (Ollama, needs ollama installed)
    python scripts/switch_llm.py vllm      # Local (vLLM, needs GPU + vllm server)
    python scripts/switch_llm.py status    # Show current provider
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERMES_CONFIG = Path.home() / ".hermes" / "config.yaml"

PROVIDERS = {
    "zai": {
        "default": "glm-5.2",
        "provider": "zai",
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "note": "Cloud API (GLM-5.2 via Z.AI). Needs GLM_API_KEY in env.",
    },
    "ollama": {
        "default": "qwen3:14b",
        "provider": "custom",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "note": "Local Ollama. Needs: ollama serve + ollama pull qwen3:14b",
    },
    "vllm": {
        "default": "Qwen/Qwen3-14B",
        "provider": "custom",
        "base_url": "http://localhost:8000/v1",
        "api_key": "vllm",
        "note": "Local vLLM. Needs: python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-14B",
    },
    "llamacpp": {
        "default": "qwen3-14b-instruct",
        "provider": "custom",
        "base_url": "http://localhost:8080/v1",
        "api_key": "llamacpp",
        "note": (
            "Local llama.cpp server. Needs: "
            "llama-server -m qwen3-14b-instruct-q4_k_m.gguf --port 8080 "
            "--n-gpu-layers 99"
        ),
    },
}


def read_config() -> str:
    if not HERMES_CONFIG.exists():
        print(f"ERROR: {HERMES_CONFIG} not found")
        sys.exit(1)
    return HERMES_CONFIG.read_text()


def write_config(text: str) -> None:
    backup = HERMES_CONFIG.with_suffix(".yaml.bak")
    shutil.copy2(HERMES_CONFIG, backup)
    HERMES_CONFIG.write_text(text)
    print(f"  Backup saved: {backup}")


def update_model_section(config_text: str, provider_name: str) -> str:
    cfg = PROVIDERS[provider_name]
    lines = config_text.split("\n")
    new_lines: list[str] = []
    in_model_section = False

    for line in lines:
        if line.startswith("model:"):
            in_model_section = True
            new_lines.append("model:")
            new_lines.append(f"  default: {cfg['default']}")
            new_lines.append(f"  provider: {cfg['provider']}")
            new_lines.append(f"  base_url: {cfg['base_url']}")
            if "api_key" in cfg:
                new_lines.append(f"  api_key: {cfg['api_key']}")
            continue

        if in_model_section:
            if line.startswith("  ") and not line.startswith("   "):
                continue
            if line.startswith("providers:"):
                in_model_section = False
                new_lines.append(line)
                continue
            if not line.startswith(" "):
                in_model_section = False
                new_lines.append(line)
                continue
            continue

        new_lines.append(line)

    return "\n".join(new_lines)


def show_status() -> None:
    config_text = read_config()
    lines = config_text.split("\n")
    in_model = False
    current: dict[str, str] = {}

    for line in lines:
        if line.startswith("model:"):
            in_model = True
            continue
        if in_model:
            if line.startswith("  default:"):
                current["model"] = line.split(":", 1)[1].strip()
            elif line.startswith("  provider:"):
                current["provider"] = line.split(":", 1)[1].strip()
            elif line.startswith("  base_url:"):
                current["base_url"] = line.split("base_url:", 1)[1].strip()
            elif not line.startswith(" "):
                break

    print("Current LLM provider:")
    for k, v in current.items():
        print(f"  {k}: {v}")

    detected = "unknown"
    for name, cfg in PROVIDERS.items():
        if current.get("base_url", "") == cfg["base_url"]:
            detected = name
            break
    print(f"  Detected as: {detected}")
    print(f"  Note: {PROVIDERS.get(detected, {}).get('note', 'N/A')}")


def check_service(provider_name: str) -> bool:
    cfg = PROVIDERS[provider_name]
    if provider_name == "zai":
        return True

    import urllib.request

    try:
        base = cfg["base_url"].rstrip("/v1")
        urllib.request.urlopen(f"{base}/api/version", timeout=2)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Switch Hermes LLM provider")
    parser.add_argument(
        "provider",
        choices=["zai", "ollama", "vllm", "llamacpp", "status"],
        help="Provider to switch to",
    )
    args = parser.parse_args()

    if args.provider == "status":
        show_status()
        return 0

    cfg = PROVIDERS[args.provider]
    print(f"=== Switching to {args.provider} ===")
    print(f"  Model: {cfg['default']}")
    print(f"  URL: {cfg['base_url']}")
    print(f"  Note: {cfg['note']}")

    if args.provider != "zai":
        alive = check_service(args.provider)
        if alive:
            print("  Service: ✅ running")
        else:
            print("  Service: ❌ not responding (see note above)")

    config_text = read_config()
    new_text = update_model_section(config_text, args.provider)
    write_config(new_text)

    print("\n✓ Hermes config updated. Restart Hermes to apply:")
    print("  hermes chat  (or restart existing session)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
