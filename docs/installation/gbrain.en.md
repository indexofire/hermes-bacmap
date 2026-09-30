# GBrain Knowledge Base Setup (Optional)

Deploy the V0.9 knowledge layer: record biologically significant findings, support
pre-registration knowledge checks and semantic retrieval. Expect 10–20 minutes
(includes a ~1.2 GB bge-m3 model download).

> Prerequisites: Linux x86_64, network access to GitHub/Ollama. bun is installed
> automatically by the script.

## One-command deploy

```bash
bash scripts/setup_gbrain.sh
```

The script automatically:

1. Installs bun (if missing) and clones gbrain into `~/gbrain`
2. **Applies the local patch** `scripts/patches/gbrain-ollama-text-embed.patch`
   (fixes gbrain's token-array incompatibility with ollama embeddings; remove
   once fixed upstream)
3. Installs Ollama user-level (`~/ollama`, systemd user service, no root needed)
4. Pulls **bge-m3** (multilingual embedding, 1024 dims, strong on zh/en
   biomedical terms)
5. Runs `gbrain init --pglite` (single-file PGLite knowledge store)
6. Imports the interpret-results skill knowledge as seed content

Minimal deploy without embeddings (keyword search only):

```bash
bash scripts/setup_gbrain.sh --no-embedding
```

## Verification

```bash
gbrain --version                # 0.59.x
gbrain doctor                   # health check (Overall should be OK)
gbrain search "blaCTX"          # keyword retrieval (English)
gbrain search "碳青霉烯耐药"     # semantic retrieval (needs embeddings; hits the English reference page)
gbrain list -n 5                # imported knowledge pages
```

## Hermes integration

The plugin talks to gbrain through the `gbrain call` subprocess bridge
(`services/gbrain_client.py`) and **probes at runtime** — when gbrain is absent
the three knowledge tools (`bio_knowledge_capture/search/think`) degrade
gracefully with an install hint; the analysis main path is never blocked.

Optional: let the LLM use gbrain's full MCP toolset (`~/.hermes/config.yaml`):

```yaml
mcp_servers:
  gbrain:
    command: gbrain
    args: ["serve"]
```

## Running and maintenance

### Process model: no resident gbrain needed

- **Plugin/CLI use (capture/search): no gbrain process to start** — `gbrain call`
  acquires the PGLite lock per invocation
- **Ollama must be running** (query-time embeddings + local think model):
  `systemctl --user status ollama` (auto-enabled by the setup script)
- Optional `gbrain serve` (MCP, only for direct LLM use of the full toolset)
- Check: `gbrain call get_health '{}' | jq .missing_embeddings` (should be 0)

### think model configuration

think needs a **chat** model (independent of embeddings); resolution chain
`models.think → models.default → GBRAIN_MODEL → Anthropic default`:

```bash
# Recommended (local, zh-friendly, pull first):
ollama pull qwen2.5:7b-instruct      # ~4.7GB, no think-tags, good schema-following
# or ollama pull glm4:9b
export GBRAIN_MODEL="ollama:qwen2.5:7b-instruct"   # persistent: gbrain config set models.think ollama:qwen2.5:7b-instruct
```

- Cloud alternative: `ANTHROPIC_API_KEY` (claude-sonnet default) or any
  OpenAI-compatible key
- ⚠️ qwen3 series emits thinking output / empty content via the OpenAI-compat
  endpoint; 0.6b-class models lack schema-following — link-verification only

### Daily operations

```bash
gbrain capture "field observation: ..."   # manual note
gbrain search "keyword or Chinese query"  # retrieval (zh/en)
gbrain sweep --once                       # backfill auto-links after batch captures
gbrain dream --dry-run                    # maintenance preview (dedup/contradictions)
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| `pglite_busy` | A serve/migration holds the lock — retry shortly (plugin marks it retryable) |
| Semantic search empty | ① is ollama active; ② `get_health` missing_embeddings >0 → re-run `gbrain migrate embeddings --to ollama:bge-m3 --yes --max-cost-usd 1` |
| Embedding fails after `gbrain self-upgrade` | Upgrade overwrote the patch — re-apply `git apply scripts/patches/gbrain-ollama-text-embed.patch` (in ~/gbrain) |

## Known limitations

- **`think` synthesis** needs a chat model configured (local
  qwen2.5:7b-instruct recommended / cloud ANTHROPIC_API_KEY); GLM coding-plan
  keys have an incompatible chat endpoint (embeddings work fine)
- Switching embedding models requires `gbrain init --force` and re-import
- The knowledge store lives at `~/.gbrain/brain.pglite` (single file, backup
  by copying)
