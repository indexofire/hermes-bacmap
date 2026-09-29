# Local LLM Configuration

Inference uses the cloud Z.AI (GLM-5.2) by default. Switch to a local LLM when you need **offline** use, **data that must not leave the premises**, or **high concurrency**.

## Provider Comparison

| Provider | Model | VRAM | Speed | Best for |
|---|---|---|---|---|
| **Z.AI** (default) | GLM-5.2 | 0 (cloud) | ~200 tok/s | Daily use; requires network |
| **Ollama** | Qwen3-14B | ~9 GB | ~124 tok/s | Offline, on-premises data, easiest option |
| **vLLM** | Qwen3-14B / 32B | 9–19 GB | ~150 tok/s | High-throughput, multi-concurrency production |
| **llama.cpp** | Qwen3-14B Q4 | ~9 GB | ~80–120 tok/s | Lightweight, CPU/GPU hybrid, low resources |

Feature comparison:

| Feature | Z.AI | Ollama | vLLM | llama.cpp |
|---|---|---|---|---|
| Installation complexity | None | Low (one-line script) | Medium (pip + CUDA) | Medium (compile / download) |
| GPU required | No | No (CPU works) | Yes (CUDA) | No (native CPU) |
| OpenAI-compatible API | Yes | Yes (`/v1/`) | Yes (`/v1/`) | Yes (`/v1/`) |
| Quantization | — | Automatic | AWQ / GPTQ / FP16 | GGUF (Q4 / Q5 / Q8) |
| Throughput | High (cloud) | Medium | Highest | Medium |

## Choosing by VRAM

| GPU VRAM | Recommended model | Parameters | Notes |
|---|---|---|---|
| 8 GB | Qwen3-7B | 7B | Basically usable; tool calling occasionally unstable |
| 16 GB | Qwen3-14B | 14B | **Recommended**; stable tool calling |
| 24 GB | Qwen3-32B | 32B | High-quality interpretation |
| 48+ GB | Qwen3-72B | 72B | Close to GPT-4 |

## Switching Providers

All switching is done through `scripts/switch_llm.py`, which rewrites the Hermes configuration file directly.

```bash
# 查看当前 provider
python scripts/switch_llm.py status

# 切换到 Ollama
python scripts/switch_llm.py ollama

# 切换到 vLLM
python scripts/switch_llm.py vllm

# 切换到 llama.cpp
python scripts/switch_llm.py llamacpp

# 切回云端 Z.AI
python scripts/switch_llm.py zai

# 切换后必须重启 Hermes
hermes chat
```

Example Hermes configuration after switching (Ollama shown):

```yaml
model:
  default: qwen3:14b
  provider: custom
  base_url: http://localhost:11434/v1
  api_key: ollama
```

## Provider Quick Start

### Ollama

```bash
# 安装
curl -fsSL https://ollama.com/install.sh | sh

# 启动服务 + 拉取模型
ollama serve &
ollama pull qwen3:14b

# 切换
python scripts/switch_llm.py ollama && hermes chat
```

### vLLM

```bash
pip install vllm   # 或 uv pip install vllm，需 CUDA 12.1+

# 后台启动 API server
nohup python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-14B \
    --gpu-memory-utilization 0.85 \
    --max-model-len 8192 \
    --port 8000 > /tmp/vllm.log 2>&1 &

# 切换
python scripts/switch_llm.py vllm && hermes chat
```

### llama.cpp

```bash
# 下载 GGUF 模型
huggingface-cli download Qwen/Qwen3-14B-Instruct-GGUF \
    qwen3-14b-instruct-q4_k_m.gguf --local-dir ~/models

# 启动 OpenAI 兼容 server
llama-server -m ~/models/qwen3-14b-instruct-q4_k_m.gguf \
    --port 8080 --n-gpu-layers 99 --ctx-size 8192

# 切换
python scripts/switch_llm.py llamacpp && hermes chat
```

## Verifying After the Switch

Start Hermes and run through the key tools to confirm tool calling works:

```
hermes chat
> 列出所有样本              # bio_list_samples
> SAM-TYP-001 的结果       # bio_get_result
> 搜索 Typhimurium          # bio_search_samples
> 系统发育树                # bio_snp_tree
> 注释 SAM-TYP-001          # bio_annotate
```

If all five tools return normally, the provider switch succeeded.

## Scenario Recommendations

| Scenario | Recommended provider |
|---|---|
| Development / testing | Z.AI (cloud, zero configuration) |
| Clinical data (data must not leave the premises) | Ollama / vLLM / llama.cpp |
| Multi-user shared workstation | vLLM (API server) |
| Offline environment / no GPU | llama.cpp (CPU mode) |
| Low-resource older workstation | llama.cpp Q4 quantization |

## Troubleshooting Quick Reference

| Problem | Fix |
|---|---|
| `Connection refused :11434` | `ollama serve &` |
| `Connection refused :8080` | `llama-server -m <model> --port 8080 &` |
| `Connection refused :8000` | vLLM service not started; see the launch command above |
| `CUDA out of memory` | Switch to a smaller model; reduce `--n-gpu-layers` for llama.cpp; reduce `--gpu-memory-utilization` for vLLM |
| Tool calling does not work | Make sure the model is from the Qwen3 series (stable tool-calling support) |
| Slow responses | Confirm the GPU is in use with `nvidia-smi`; CPU inference is inherently slow |
