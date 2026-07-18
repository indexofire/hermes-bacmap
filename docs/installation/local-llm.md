# 本地 LLM 配置

默认使用云端 Z.AI（GLM-5.2）推理。当需要**离线**、**数据不出境**或**多并发**时，可切换到本地 LLM。

## Provider 对比

| Provider | 模型 | VRAM | 速度 | 适合场景 |
|---|---|---|---|---|
| **Z.AI**（默认） | GLM-5.2 | 0（云端） | ~200 tok/s | 日常使用，需网络 |
| **Ollama** | Qwen3-14B | ~9 GB | ~124 tok/s | 离线、数据不出境、易用首选 |
| **vLLM** | Qwen3-14B / 32B | 9–19 GB | ~150 tok/s | 高吞吐、多并发生产 |
| **llama.cpp** | Qwen3-14B Q4 | ~9 GB | ~80–120 tok/s | 轻量、CPU/GPU 混合、低资源 |

特性对比：

| 特性 | Z.AI | Ollama | vLLM | llama.cpp |
|---|---|---|---|---|
| 安装复杂度 | 无 | 低（一键脚本） | 中（pip + CUDA） | 中（编译 / 下载） |
| GPU 必需 | 否 | 否（可用 CPU） | 是（CUDA） | 否（原生 CPU） |
| OpenAI 兼容 API | 是 | 是 (`/v1/`) | 是 (`/v1/`) | 是 (`/v1/`) |
| 量化 | — | 自动 | AWQ / GPTQ / FP16 | GGUF (Q4 / Q5 / Q8) |
| 吞吐量 | 高（云端） | 中 | 最高 | 中 |

## 按显存选型

| GPU VRAM | 推荐模型 | 参数量 | 说明 |
|---|---|---|---|
| 8 GB | Qwen3-7B | 7B | 基本可用，tool calling 偶有不稳定 |
| 16 GB | Qwen3-14B | 14B | **推荐**，tool calling 稳定 |
| 24 GB | Qwen3-32B | 32B | 高质量解读 |
| 48+ GB | Qwen3-72B | 72B | 接近 GPT-4 |

## 切换 Provider

所有切换通过 `scripts/switch_llm.py` 完成，它直接改写 Hermes 配置文件。

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

切换后的 Hermes 配置示例（以 Ollama 为例）：

```yaml
model:
  default: qwen3:14b
  provider: custom
  base_url: http://localhost:11434/v1
  api_key: ollama
```

## Provider 启动速查

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

## 切换后验证

启动 Hermes，跑一遍关键工具确认 tool calling 正常：

```
hermes chat
> 列出所有样本              # bio_list_samples
> SAM-TYP-001 的结果       # bio_get_result
> 搜索 Typhimurium          # bio_search_samples
> 系统发育树                # bio_snp_tree
> 注释 SAM-TYP-001          # bio_annotate
```

五个工具都正常返回即说明 provider 切换成功。

## 场景建议

| 场景 | 推荐 provider |
|---|---|
| 开发 / 测试 | Z.AI（云端，零配置） |
| 临床数据（数据不出境） | Ollama / vLLM / llama.cpp |
| 多用户共享工作站 | vLLM（API server） |
| 离线环境 / 无 GPU | llama.cpp（CPU 模式） |
| 低资源老旧工作站 | llama.cpp Q4 量化 |

## 故障速查

| 问题 | 修复 |
|---|---|
| `Connection refused :11434` | `ollama serve &` |
| `Connection refused :8080` | `llama-server -m <model> --port 8080 &` |
| `Connection refused :8000` | vLLM 服务未启动，见上方启动命令 |
| `CUDA out of memory` | 换更小模型；llama.cpp 减 `--n-gpu-layers`；vLLM 减 `--gpu-memory-utilization` |
| Tool calling 不工作 | 确保模型是 Qwen3 系列（tool calling 支持稳定） |
| 响应慢 | `nvidia-smi` 确认 GPU 在用；CPU 推理必然慢 |
