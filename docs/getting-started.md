# 开发环境搭建指南

本文档介绍如何使用 uv 和 pixi 搭建 hermes-bacmap 的完整开发环境。

## 前置条件

确保系统已安装以下工具:

```bash
# 检查 uv
uv --version        # 需要 uv >= 0.5

# 检查 pixi
pixi --version      # 需要 pixi >= 0.30

# 如果缺少, 按以下方式安装:
# uv:    curl -LsSf https://astral.sh/uv/install.sh | sh
# pixi:  curl -fsSL https://pixi.sh/install.sh | bash
```

## 双环境架构

本项目使用两套独立的环境管理工具, 各管各的事:

```
┌─────────────────────────────────────────────────────┐
│  uv (.venv/)                                        │
│  Python 3.11 开发环境                                │
│                                                     │
│  • biopython        ← 运行时依赖                      │
│  • pytest, ruff     ← 开发依赖                        │
│  • hermes-bacmap    ← 你的插件 (editable install)     │
│                                                     │
│  用途: 写代码、跑测试、lint、import 调试               │
├─────────────────────────────────────────────────────┤
│  pixi (.pixi/)                                      │
│  生信 CLI 工具 (conda-forge + bioconda)              │
│                                                     │
│  • samtools, bwa, minimap2                          │
│  • bcftools, blast, bedtools, seqkit                │
│                                                     │
│  用途: 插件通过 subprocess 调用这些工具               │
│  这些是独立的二进制程序, 不属于 Python 生态            │
├─────────────────────────────────────────────────────┤
│  Hermes venv (~/.hermes/hermes-agent/venv/)          │
│  插件实际运行的环境                                    │
│                                                     │
│  • Python 3.11 (和 uv 环境版本一致)                   │
│  • biopython (需要手动安装到此处)                      │
│                                                     │
│  用途: hermes 启动时加载插件, 用的是这个 Python        │
└─────────────────────────────────────────────────────┘
```

### 为什么需要两套工具?

- **Python 包** (biopython, numpy) 用 uv 管理 — uv 比 pip 快 10-100 倍, 有 lockfile
- **生信 CLI 工具** (samtools, bwa) 用 pixi 管理 — 这些是 C/C++ 编译的二进制,
  不是 pip 包, conda-forge/bioconda 是它们的唯一分发渠道
- 两者互不干扰: uv 的 .venv 里没有 samtools, pixi 的环境里也没有 biopython

### 为什么 Python 版本要和 Hermes 一致?

插件代码最终运行在 Hermes 的 Python 进程里 (被 import 进去)。
如果开发用 3.13、Hermes 用 3.11, 某些语法或 C 扩展可能不兼容。
所以 uv venv 和 pyproject.toml 都锁定 `>=3.11, <3.14`。

---

## 第一步: 初始化 uv Python 环境

```bash
cd ~/repo/github/hermes-bacmap

# 创建虚拟环境, 指定 Python 3.11 (与 Hermes 一致)
uv venv --python 3.11

# 安装项目依赖 (含开发依赖)
# editable 模式 (-e) 让源码修改立即生效, 无需重新安装
uv pip install -e ".[dev]"
```

验证:

```bash
# 检查 Python 版本
uv run python --version
# 期望输出: Python 3.11.x

# 检查 biopython
uv run python -c "import Bio; print(Bio.__version__)"
# 期望输出: 1.87

# 检查 ruff
uv run ruff --version
# 期望输出: ruff 0.x.x
```

### uv 依赖说明

`pyproject.toml` 中的依赖分两组:

```toml
# 运行时依赖 — 插件运行必须的包
# 部署到 Hermes 时也要把这些装到 Hermes venv
dependencies = [
    "biopython>=1.83",
]

# 开发依赖 — 只有开发环境需要
# pytest 跑测试, ruff 做 lint, 不需要进 Hermes venv
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "ruff>=0.5",
]
```

添加新的 Python 依赖时:

```bash
# 运行时依赖 (biopython 这类, Hermes 里也要装)
uv add biopython

# 开发依赖 (只在开发时用)
uv add --group dev mypy
# 或手动编辑 pyproject.toml 的 [project.optional-dependencies] dev 列表

# 然后重新安装
uv pip install -e ".[dev]"
```

---

## 第二步: 初始化 pixi 生信工具环境

```bash
cd ~/repo/github/hermes-bacmap

# 安装 pixi.toml 中声明的所有 CLI 工具
pixi install
```

这会从 conda-forge 和 bioconda 下载 samtools、bwa、minimap2 等工具,
安装到 `.pixi/envs/default/` 目录。

验证:

```bash
# 在 pixi 环境中运行工具 (需要 pixi run 前缀)
pixi run samtools --version
pixi run bwa 2>&1 | head -3
pixi run minimap2 --version
pixi run bcftools --version
```

### pixi 依赖说明

`pixi.toml` 声明的工具:

```toml
[dependencies]
python = "3.11.*"       # pixi 环境也带一个 python (给 conda 包用)
samtools = ">=1.20"      # SAM/BAM 操作
bwa = ">=0.7.17"         # 短读长比对
minimap2 = ">=2.28"      # 长读长比对
bcftools = ">=1.20"      # 变异检测
blast = ">=2.16"         # 序列搜索
bedtools = ">=2.31"      # 区间操作
seqkit = ">=2.8"         # FASTA/Q 快速操作
```

添加新的 CLI 工具:

```bash
# 方式一: 命令行添加
pixi add spades

# 方式二: 手动编辑 pixi.toml 的 [dependencies] 段
# 然后重新安装
pixi install
```

### 版本冲突排查

如果 `pixi install` 报版本找不到:

```bash
# 搜索 bioconda 上的可用版本
pixi search "包名" -c bioconda

# 根据实际版本修正 pixi.toml 中的版本约束
# 然后重新 pixi install
```

---

## 第三步: 日常开发工作流

### 写代码 + 跑测试 (uv 环境)

```bash
cd ~/repo/github/hermes-bacmap

# 跑全部测试
uv run pytest -v

# 跑单个测试文件
uv run pytest tests/test_env.py -v

# 跑特定测试
uv run pytest tests/test_env.py::test_biopython_importable -v

# 带覆盖率
uv run pytest --cov=src/hermes_bacmap --cov-report=term-missing
```

### 代码检查和格式化 (uv 环境)

```bash
# 检查代码风格
uv run ruff check src/ tests/

# 自动修复可修复的问题
uv run ruff check --fix src/ tests/

# 格式化代码
uv run ruff format src/ tests/
```

### 调试时需要生信工具 (uv + pixi 联合)

开发中如果需要同时用 Python 和 CLI 工具 (比如跑集成测试):

```bash
# 方式一: pixi shell 激活 conda 环境, 然后用 uv run
pixi shell
# 此时 samtools, bwa 等在 PATH 中
uv run python -c "
from hermes_bacmap import tools
import json
# tools 模块里的 subprocess 调用能找到 samtools
print(json.loads(tools.samtools_op({'operation': 'flagstat', 'input': 'test.bam'})))
"
exit  # 退出 pixi shell

# 方式二: 在 Python 代码里指定完整路径
# pixi 工具在 .pixi/envs/default/bin/ 下, 可以在代码里引用
```

### 交互式调试

```bash
# 用 uv 的 Python 进入 REPL
uv run python

>>> from hermes_bacmap import tools, schemas
>>> # 测试某个工具函数
>>> import json
>>> result = json.loads(tools.seq_ops({
...     "operation": "reverse_complement",
...     "sequence": "ATGGCC"
... }))
>>> print(result)
```

---

## 第四步: 部署到 Hermes

开发完成后, 需要让 Hermes 能加载到插件。

### 1. 安装运行时依赖到 Hermes venv

```bash
# 把 biopython 装到 Hermes 自己的 Python 环境
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python biopython
```

注意: 只装运行时依赖 (`dependencies`), 不装开发依赖 (`dev`)。
pytest 和 ruff 不需要进 Hermes venv。

### 2. 链接插件目录

```bash
# 用 symlink — 改源码立即生效, 不用重新复制
ln -sf ~/repo/github/hermes-bacmap/src/hermes_bacmap \
        ~/.hermes/plugins/hermes_bacmap
```

Hermes 扫描 `~/.hermes/plugins/` 下含 `plugin.yaml` 的目录。
symlink 指向 `src/hermes_bacmap/`, 里面有 `plugin.yaml`, 所以能被发现。

### 3. 启用插件并测试

```bash
# 启用插件
hermes plugins enable hermes_bacmap

# 验证
hermes plugins list | grep hermes_bacmap

# 新开一个会话测试
hermes chat -q "用 bio_seq_stats 分析 /tmp/test.fasta"
```

### 4. 让 Hermes 找到 pixi 的 CLI 工具

Hermes 运行插件时, 插件代码通过 `shutil.which("samtools")` 查找工具。
默认情况下 Hermes 的 PATH 里没有 pixi 安装的工具。解决方案:

```bash
# 方式一: 把 pixi bin 加入 PATH (写入 ~/.bashrc 或 ~/.zshrc)
export PATH="$HOME/repo/github/hermes-bacmap/.pixi/envs/default/bin:$PATH"

# 方式二: 用 conda/mamba 全局安装 (不依赖 pixi)
conda install -c bioconda samtools bwa minimap2 bcftools

# 方式三: 系统包管理器 (部分工具)
sudo pacman -S samtools minimap2    # Arch Linux
```

---

## 环境管理速查

| 操作 | 命令 |
|------|------|
| 创建 uv 环境 | `uv venv --python 3.11` |
| 安装 Python 依赖 | `uv pip install -e ".[dev]"` |
| 添加 Python 包 | `uv add <包名>` |
| 跑测试 | `uv run pytest -v` |
| 代码检查 | `uv run ruff check src/ tests/` |
| 格式化 | `uv run ruff format src/ tests/` |
| 安装 pixi 工具 | `pixi install` |
| 添加 CLI 工具 | `pixi add <工具名>` |
| 搜索 conda 包 | `pixi search "包名" -c bioconda` |
| 激活 pixi shell | `pixi shell` |
| 更新 uv 依赖 | `uv pip install -e ".[dev]"` (重新 lock) |
| 更新 pixi 工具 | `pixi update` |
| 部署到 Hermes | 见上方第四步 |

---

## 常见问题

### Q: uv run pytest 报 ModuleNotFoundError: No module named 'Bio'

biopython 没装到 uv 的 .venv。运行:

```bash
uv pip install -e ".[dev]"
```

### Q: pixi run samtools 报 command not found

pixi 环境没装好。运行:

```bash
pixi install
```

如果报版本找不到, 用 `pixi search` 查实际版本, 修改 pixi.toml。

### Q: Hermes 里工具报 "samtools not found"

Hermes 的 PATH 里没有 samtools。用 pixi shell 先激活, 或把 `.pixi/envs/default/bin`
加入 PATH, 或全局安装。详见第四步第 4 点。

### Q: 开发环境改了代码, Hermes 里没生效

如果用了 symlink 部署, 改代码后重启 Hermes 会话即可 (`/reset` 或重开)。
如果用的是复制方式, 需要重新复制文件。

### Q: uv 和 pixi 里的 python 会冲突吗?

不会。uv 的 .venv 是独立的虚拟环境, pixi 的 .pixi 也是独立的。
两者互不影响。插件运行时用的是 Hermes venv 的 Python, 和这两个都无关。
pixi 里的 python 只是给 conda 包做依赖用的, 你的代码不会用它。
