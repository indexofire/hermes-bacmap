# GBrain 知识库安装（可选）

部署 V0.9 知识层：记录生信分析中有生物学意义的发现、支持注册前知识查证与语义检索。
预计耗时 10–20 分钟（含 bge-m3 模型下载 ~1.2GB）。

> 前置条件：Linux x86_64、网络可达 GitHub/Ollama。bun 会由脚本自动安装。

## 一键部署

```bash
bash scripts/setup_gbrain.sh
```

脚本自动完成：

1. 安装 bun（若无）+ 克隆 gbrain 到 `~/gbrain`
2. **应用本地补丁** `scripts/patches/gbrain-ollama-text-embed.patch`
   （修复 gbrain 嵌入对 ollama 的 token 数组不兼容；待上游修复后移除）
3. 用户级安装 Ollama（`~/ollama`，systemd 用户服务，无需 root）
4. 拉取 **bge-m3**（多语言 embedding，1024 维，中英生物医学术语友好）
5. `gbrain init --pglite`（PGLite 单文件知识库）
6. 导入 interpret-results 技能知识作为种子

无 embedding 的最小部署（仅关键词检索）：

```bash
bash scripts/setup_gbrain.sh --no-embedding
```

## 验证

```bash
gbrain --version                # 0.59.x
gbrain doctor                   # 健康检查（Overall 应为 OK）
gbrain search "blaCTX"          # 关键词检索（英文）
gbrain search "碳青霉烯耐药"     # 语义检索（需 embedding，命中英文参考页）
gbrain list -n 5                # 已导入知识页
```

## 与 Hermes 集成

插件侧通过 `gbrain call` 子进程桥调用（`services/gbrain_client.py`），
**运行时自动探测**——未安装时 3 个知识工具（`bio_knowledge_capture/search/think`）
优雅降级返回安装提示，分析主路不受影响。

可选：让 LLM 直接使用 gbrain 全量 MCP 工具（`~/.hermes/config.yaml`）：

```yaml
mcp_servers:
  gbrain:
    command: gbrain
    args: ["serve"]
```

## 已知限制

- **`think` 综合回答**需要独立 LLM key（如 `ANTHROPIC_API_KEY`）；GLM coding
  计划 key 的 chat 端点不兼容（embedding 端点正常）
- 切换 embedding 模型需 `gbrain init --force` 重建并重新导入
- 知识库文件位于 `~/.gbrain/brain.pglite`（单文件，可直接备份）
