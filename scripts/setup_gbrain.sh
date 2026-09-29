#!/usr/bin/env bash
# GBrain 知识层用户级部署（hermes-bacmap V0.9+）
# 前置：bun（https://bun.sh）、可选 ollama（本地 embedding，推荐 bge-m3 多语言）
# 用法：bash scripts/setup_gbrain.sh [--no-embedding]
set -euo pipefail

NO_EMBEDDING="${1:-}"

say() { printf '\033[1;34m[setup_gbrain]\033[0m %s\n' "$*"; }

if ! command -v bun >/dev/null 2>&1; then
    say "安装 bun"
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
fi

say "克隆 gbrain 到 ~/gbrain"
if [ ! -d ~/gbrain ]; then
    git clone --depth 1 https://github.com/garrytan/gbrain.git ~/gbrain
fi
cd ~/gbrain
say "安装依赖（bun install）"
bun install
# 应用本地补丁：ollama 文本直通（上游 Vercel AI SDK token 化不兼容，待上游修复后移除）
PATCH="$(cd "$(dirname "$0")" && pwd)/patches/gbrain-ollama-text-embed.patch"
if [ -f "$PATCH" ] && ! grep -q "PATCH(hermes-bacmap)" src/core/ai/gateway.ts; then
    git apply "$PATCH" || echo "WARN: 补丁应用失败（可能已合入上游）"
fi
chmod +x src/cli.ts
ln -sf ~/gbrain/src/cli.ts ~/.bun/bin/gbrain
export PATH="$HOME/.bun/bin:$PATH"
gbrain --version

if [ "$NO_EMBEDDING" = "--no-embedding" ]; then
    say "初始化（无 embedding，仅关键词检索）"
    gbrain init --pglite --no-embedding
else
    say "检查 ollama（本地 embedding）"
    if ! command -v ollama >/dev/null 2>&1; then
        say "未找到 ollama —— 用户级安装到 ~/ollama"
        mkdir -p ~/ollama
        curl -sL -o /tmp/ollama.tar.zst \
            "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst"
        tar --use-compress-program=unzstd -xf /tmp/ollama.tar.zst -C ~/ollama
        mkdir -p ~/.config/systemd/user
        cat > ~/.config/systemd/user/ollama.service <<EOF
[Unit]
Description=Ollama embedding server (user-level)
After=network-online.target
[Service]
ExecStart=$HOME/ollama/bin/ollama serve
Environment=OLLAMA_MODELS=$HOME/.ollama/models
Restart=on-failure
[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload && systemctl --user enable --now ollama.service
        export PATH="$HOME/ollama/bin:$PATH"
    fi
    say "拉取 bge-m3（多语言 embedding，~1.2GB）"
    ollama pull bge-m3
    say "初始化 gbrain（PGLite + ollama:bge-m3, 1024 维）"
    gbrain init --force --pglite \
        --embedding-model ollama:bge-m3 --embedding-dimensions 1024
fi

say "导入 bacmap 种子知识（skills 解读知识库）"
gbrain import "$(dirname "$0")/../src/hermes_bacmap/skills/interpret-results/"
gbrain import "$(dirname "$0")/../src/hermes_bacmap/skills/interpret-results/references/"

say "完成。验证：gbrain list -n 10 && gbrain search 'blaCTX'"
say "可选：在 ~/.hermes/config.yaml 挂载 MCP（LLM 直用 gbrain 全量工具）："
say "  mcp_servers: { gbrain: { command: gbrain, args: [serve] } }"
