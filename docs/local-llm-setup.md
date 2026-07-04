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

### 安装

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

## 3. Provider 管理

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

## 4. 模型选择建议

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

---

## 5. 故障排查

| 问题 | 原因 | 修复 |
|---|---|---|
| `Connection refused` at localhost:11434 | Ollama 服务未启动 | `ollama serve &` |
| `CUDA out of memory` | VRAM 不足 | 换更小模型或减小 `--gpu-memory-utilization` |
| Tool calling 不工作 | 模型不支持 function calling | 确保 Qwen3 系列（支持 tool calling） |
| 响应速度慢 | CPU 推理（无 GPU） | 确认 `nvidia-smi` 可用；Ollama 自动用 GPU |
| `model not found` | 模型未拉取 | `ollama pull qwen3:14b` |

---

## 6. 安全与合规

| 场景 | 推荐 provider |
|---|---|
| 开发/测试 | Z.AI (cloud) |
| 临床数据（数据不出境） | Ollama/vLLM (local) |
| 多用户共享 | vLLM (API server) |
| 离线环境 | Ollama |
