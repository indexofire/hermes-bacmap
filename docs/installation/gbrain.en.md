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

## Known limitations

- **`think` synthesis** requires a separate LLM key (e.g. `ANTHROPIC_API_KEY`);
  GLM coding-plan keys have an incompatible chat endpoint (the embedding
  endpoint works fine)
- Switching embedding models requires `gbrain init --force` and re-import
- The knowledge store lives at `~/.gbrain/brain.pglite` (single file, backup
  by copying)
