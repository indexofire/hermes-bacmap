# 本地 LLM 支持：Ollama + vLLM 配置指南

> **硬件要求**: GPU ≥ 16GB VRAM (推荐 RTX 5060 Ti / RTX 4080)，RAM ≥ 32GB
> **当前环境**: AMD Ryzen 7 5700G, RTX 5060 Ti 16GB, 62GB RAM

---

## 三个 Provider

| Provider | 模型 | VRAM | 速度 | 适合场景 |
|---|---|---|---|---|
| **Z.AI (当前)** | GLM-5.2 | 0 (cloud) | ~200 tok/s | 日常使用，需网络 |
| **Ollama** | Qwen3-14B | ~9 GB | ~124 tok/s | 离线、数据不出境 |
| **vLLM** | Qwen3-14B/32B | 9-19 GB | ~150 tok/s | 高吞吐、多并发 |
| **llama.cpp** | Qwen3-14B Q4 | ~9 GB | ~80-120 tok/s | 轻量、CPU/GPU 混合推理 |

---

## 1. Ollama 安装与配置

### 安装

```bash
# 方式 A: 官方脚本（需要 sudo）
curl -fsSL https://ollama.com/install.sh | sh

# 方式 B: 手动安装（无需 sudo）
mkdir -p ~/.local/bin
# 从 GitHub releases 下载对应平台的二进制
# 或: conda install -c conda-forge ollama
```

### 启动服务 + 拉取模型

```bash
# 启动 Ollama 后台服务
ollama serve &

# 拉取模型（14B 推荐用于 16GB VRAM）
ollama pull qwen3:14b

# 验证
ollama list
ollama run qwen3:14b "Hello"
```

### 切换 Hermes 到 Ollama

```bash
python scripts/switch_llm.py ollama
hermes chat  # 重启 Hermes
```

切换后 Hermes 配置变为：
```yaml
model:
  default: qwen3:14b
  provider: custom
  base_url: http://localhost:11434/v1
  api_key: ollama
```

---

## 2. vLLM 安装与配置

```bash
# 需要 CUDA 12.1+ 和 Python 3.10+
pip install vllm

# 或使用 uv（推荐）
uv pip install vllm
```

### 启动 vLLM 服务

```bash
# 基本启动
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-14B \
    --gpu-memory-utilization 0.85 \
    --max-model-len 8192 \
    --port 8000

# 后台运行
nohup python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-14B \
    --port 8000 > /tmp/vllm.log 2>&1 &
```

### 切换 Hermes 到 vLLM

```bash
python scripts/switch_llm.py vllm
hermes chat
```

切换后 Hermes 配置变为：
```yaml
model:
  default: Qwen/Qwen3-14B
  provider: custom
  base_url: http://localhost:8000/v1
  api_key: vllm
```

---

## 3. llama.cpp 安装与配置

### 安装

```bash
# 方式 A: 预编译二进制（推荐）
# 从 https://github.com/ggerganov/llama.cpp/releases 下载对应平台
# 放到 ~/.local/bin/ 或 /usr/local/bin/

# 方式 B: 从源码编译（GPU 加速）
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j 8
cp build/bin/llama-server ~/.local/bin/
cp build/bin/llama-cli ~/.local/bin/

# 下载 GGUF 模型
# Hugging Face: https://huggingface.co/Qwen/Qwen3-14B-Instruct-GGUF
huggingface-cli download Qwen/Qwen3-14B-Instruct-GGUF \
    qwen3-14b-instruct-q4_k_m.gguf \
    --local-dir ~/models
```

### 启动 llama.cpp 服务

```bash
# GPU 推理（RTX 5060 Ti 16GB）
llama-server \
    -m ~/models/qwen3-14b-instruct-q4_k_m.gguf \
    --port 8080 \
    --n-gpu-layers 99 \
    --ctx-size 8192 \
    --host 0.0.0.0

# CPU 推理（无 GPU 或 VRAM 不足）
llama-server \
    -m ~/models/qwen3-14b-instruct-q4_k_m.gguf \
    --port 8080 \
    --threads 8 \
    --ctx-size 4096

# 验证（OpenAI 兼容 API）
curl http://localhost:8080/v1/models
```

### 切换 Hermes 到 llama.cpp

```bash
python scripts/switch_llm.py llamacpp
hermes chat
```

切换后 Hermes 配置变为：
```yaml
model:
  default: qwen3-14b-instruct
  provider: custom
  base_url: http://localhost:8080/v1
  api_key: llamacpp
```

### llama.cpp vs Ollama vs vLLM

| 特性 | llama.cpp | Ollama | vLLM |
|---|---|---|---|
| 安装复杂度 | 中（编译或下载） | 低（一键脚本） | 中（pip + CUDA） |
| GPU 支持 | ✅ CUDA / Metal | ✅ 自动检测 | ✅ 仅 CUDA |
| CPU 推理 | ✅ 原生支持 | ✅（慢） | ❌ |
| 量化格式 | GGUF (Q4/Q5/Q8) | GGUF (自动选) | AWQ/GPTQ/FP16 |
| OpenAI API | ✅ /v1/ | ✅ /v1/ | ✅ /v1/ |
| 显存效率 | 最高（Q4 量化） | 高 | 中（FP16） |
| 吞吐量 | 中 | 中 | 最高 |
| 适合场景 | 单用户、低资源 | 易用性首选 | 多并发生产 |

---

## 4. Provider 管理

### 查看当前 provider

```bash
python scripts/switch_llm.py status
```

### 切换回云端

```bash
python scripts/switch_llm.py zai
hermes chat
```

### 验证 18 个 tools 正常

切换后启动 Hermes，测试关键 tools：

```
hermes chat
> 列出所有样本              # bio_list_samples
> SAM-TYP-001 的结果       # bio_get_result
> 搜索 Typhimurium          # bio_search_samples
> 系统发育树                # bio_snp_tree
> 注释 SAM-TYP-001          # bio_annotate
```

---

## 5. 模型选择建议

| GPU VRAM | 推荐模型 | 参数量 | 说明 |
|---|---|---|---|
| 8 GB | Qwen3-7B | 7B | 基本可用，tool calling 可能不稳定 |
| 16 GB | Qwen3-14B | 14B | 推荐，tool calling 稳定 |
| 24 GB | Qwen3-32B | 32B | 高质量解读 |
| 48+ GB | Qwen3-72B | 72B | 最佳，接近 GPT-4 |

### Ollama 拉取命令

```bash
ollama pull qwen3:7b     # 8GB VRAM, ~4.5GB download
ollama pull qwen3:14b    # 16GB VRAM, ~8.5GB download
ollama pull qwen3:32b    # 24GB VRAM, ~18.6GB download
```

### vLLM 模型指定

```bash
--model Qwen/Qwen3-7B-Base
--model Qwen/Qwen3-14B
--model Qwen/Qwen3-32B
```

### llama.cpp GGUF 模型

```bash
# Hugging Face 下载（Q4_K_M 量化推荐）
huggingface-cli download Qwen/Qwen3-14B-Instruct-GGUF qwen3-14b-instruct-q4_k_m.gguf --local-dir ~/models
huggingface-cli download Qwen/Qwen3-7B-Instruct-GGUF qwen3-7b-instruct-q4_k_m.gguf --local-dir ~/models

# llama-server 启动时用 -m 指定
llama-server -m ~/models/qwen3-14b-instruct-q4_k_m.gguf --port 8080 --n-gpu-layers 99
```

---

## 6. 故障排查

| 问题 | 原因 | 修复 |
|---|---|---|
| `Connection refused` at :11434 | Ollama 未启动 | `ollama serve &` |
| `Connection refused` at :8080 | llama.cpp 未启动 | `llama-server -m <model> --port 8080 &` |
| `CUDA out of memory` | VRAM 不足 | 更小模型；llama.cpp 减 `--n-gpu-layers`；vLLM 减 `--gpu-memory-utilization` |
| Tool calling 不工作 | 模型不支持 | 确保 Qwen3 系列 |
| 响应速度慢 | CPU 推理 | `nvidia-smi` 确认 GPU；llama.cpp 加 `--n-gpu-layers 99` |
| `model not found` | 未拉取 | Ollama: `ollama pull`; llama.cpp: 检查 `-m` 路径 |

---

## 7. 安全与合规

| 场景 | 推荐 provider |
|---|---|
| 开发/测试 | Z.AI (cloud) |
| 临床数据（数据不出境） | Ollama/vLLM/llama.cpp (local) |
| 多用户共享 | vLLM (API server) |
| 离线环境 / 无 GPU | llama.cpp (CPU 模式) |
| 低资源工作站 | llama.cpp Q4 量化 |
