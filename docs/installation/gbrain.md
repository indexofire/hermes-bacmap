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

## 运行与维护

### 进程模型：gbrain 无需常驻

- **插件/CLI 使用（capture/search）：无需启动任何 gbrain 进程**——`gbrain call` 每次调用
  自取 PGLite 锁，即用即走
- **必须运行的是 Ollama**（查询期 embedding + think 本地模型）：
  `systemctl --user status ollama`（部署脚本已设开机自启）
- 可选 `gbrain serve`（MCP，仅当让 LLM 直用 gbrain 全量工具时）
- 检查：`gbrain call get_health '{}' | jq .missing_embeddings`（应为 0）

### think 模型配置（推荐：复用 GLM 编程套餐，旗舰质量零额外费用）

think 需要一个**聊天**模型（与 embedding 无关）。**首选：复用你的 GLM 编程套餐
key + 编程端点 + `glm-5.3-flash`**（套餐内旗舰 flash 档，实测输出带行内引用与
缺口分析，质量远超免费档）：

```bash
# ① ~/.hermes/.env 追加（与 GLM_API_KEY 同值）：
echo "ZHIPUAI_API_KEY=$GLM_API_KEY" >> ~/.hermes/.env

# ② gbrain 持久配置（本机已完成）：
gbrain config set provider_base_urls.zhipu https://open.bigmodel.cn/api/coding/paas/v4
gbrain config set models.think   zhipu:glm-5.3-flash
gbrain config set models.default zhipu:glm-5.3-flash
```

- 解析链：`models.think → models.default → GBRAIN_MODEL → Anthropic 默认`
- 备选（免费档，标准端点，无需上述 base_url 覆盖）：`zhipu:glm-4.5-flash`
- 离线替代：`ollama pull qwen2.5:7b-instruct` + `models.think ollama:qwen2.5:7b-instruct`
- 云端替代：`ANTHROPIC_API_KEY`
- ⚠️ 关键坑（实测）：**旗舰/新模型（glm-5.3*）只在编程端点
  `/api/coding/paas/v4` 套餐内开放**；标准端点 `/api/paas/v4` 上它们是按量付费
  （无余额报 1113）。`openai:` provider 前缀对接 GLM 不通（须 `zhipu:`）；qwen3
  系列经兼容端点有思考输出问题

### 日常操作

```bash
gbrain capture "现场观察：..."          # 手动记录
gbrain search "关键词/中文语义"          # 检索（中英均可）
gbrain sweep --once                    # 批量捕获后补自动连线
gbrain dream --dry-run                 # 维护预览（去重/矛盾检测）
```

### 故障排查

| 现象 | 处置 |
|---|---|
| `pglite_busy` | 有 serve/迁移持锁——稍候重试（插件侧自动识别为可重试） |
| 语义检索无结果 | ① ollama 是否 active；② `get_health` 的 missing_embeddings 是否 >0（重跑 `gbrain migrate embeddings --to ollama:bge-m3 --yes --max-cost-usd 1`） |
| `gbrain self-upgrade` 后嵌入失败 | 升级覆盖补丁——重跑 `git apply scripts/patches/gbrain-ollama-text-embed.patch`（~/gbrain） |

## 已知限制

- **`think` 综合回答**已打通旗舰档：GLM 编程套餐 + 编程端点 + `zhipu:glm-5.3-flash`
  （实测带行内引用与缺口分析；免费档 glm-4.5-flash 为备选）
- 切换 embedding 模型需 `gbrain init --force` 重建并重新导入
- 知识库文件位于 `~/.gbrain/brain.pglite`（单文件，可直接备份）
