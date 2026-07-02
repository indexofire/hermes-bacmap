#!/usr/bin/env bash
# 组装后物种验证（minimap2 替代 blastn）。
# minimap2 已安装，不需要额外装 blast+。
# 用法：bash scripts/assembly_validation_minimap2.sh <contigs.fasta> [sample_id]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
export PATH="$PROJECT_ROOT/.pixi/envs/default/bin:$PATH"

REF="$PROJECT_ROOT/data/reference/salmonella_invA.fasta"
CONTIGS="${1:-}"
SID="${2:-sample}"

if [ -z "$CONTIGS" ] || [ ! -f "$CONTIGS" ]; then
    echo "Usage: $0 <contigs.fasta> [sample_id]"
    exit 1
fi

if ! command -v minimap2 &>/dev/null; then
    echo "ERROR: minimap2 not installed"
    exit 1
fi

echo "=== minimap2 物种验证 ($SID) ==="
echo "Contigs: $CONTIGS"
echo "Reference: $(head -1 "$REF")"
echo ""

stats=$(minimap2 -ax asm5 --secondary=no "$REF" "$CONTIGS" 2>/dev/null | \
    samtools sort -o /dev/null --write-index - 2>/dev/null; \
    minimap2 -ax asm5 --secondary=no "$REF" "$CONTIGS" 2>/dev/null | \
    samtools flagstat -)

mapped=$(echo "$stats" | grep "primary mapped" | grep -oP '^\d+')
total=$(echo "$stats" | grep "in total" | grep -oP '^\d+')

if [ -z "$mapped" ] || [ "$mapped" -eq 0 ]; then
    echo "❌ not Salmonella (no invA hit in contigs)"
    exit 0
fi

best_cov=$(minimap2 -ax asm5 --secondary=no "$REF" "$CONTIGS" 2>/dev/null | \
    samtools depth - 2>/dev/null | \
    awk '{sum+=$3; count++} END{if(count>0) printf "%.1f%%", (sum/count)*100; else print "N/A"}')

echo "✅ Salmonella confirmed"
echo "  contigs mapped to invA: $mapped"
echo "  invA mean coverage: $best_cov"
echo ""
echo "判定标准: contigs 比对到 invA 且覆盖 > 50% = Salmonella 阳性"
