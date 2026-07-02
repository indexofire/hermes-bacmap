#!/usr/bin/env bash
# 组装后物种验证：blastn 把 contigs 比对到 invA 靶基因。
# 比 reads-based bwa 更特异（contigs 更长，比对更可靠）。
# 需要：blast+ (pixi add blast)
# 用法：bash scripts/assembly_validation_blastn.sh <contigs.fasta> [sample_id]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
export PATH="$PROJECT_ROOT/.pixi/envs/default/bin:$PATH"

REF="$PROJECT_ROOT/data/reference/salmonella_invA.fasta"
DB="$PROJECT_ROOT/data/reference/salmonella_invA_blastdb"
CONTIGS="${1:-}"
SID="${2:-sample}"

if [ -z "$CONTIGS" ] || [ ! -f "$CONTIGS" ]; then
    echo "Usage: $0 <contigs.fasta> [sample_id]"
    echo "  contigs.fasta: SPAdes/Unicycler 组装后的 contigs 文件"
    exit 1
fi

if ! command -v blastn &>/dev/null; then
    echo "ERROR: blastn not installed. Run: pixi add blast"
    exit 1
fi

if [ ! -f "${DB}.ndb" ]; then
    makeblastdb -in "$REF" -dbtype nucl -out "$DB" -parse_seqids 2>/dev/null
fi

echo "=== blastn 物种验证 ($SID) ==="
echo "Contigs: $CONTIGS"
echo "Reference: $(head -1 "$REF")"
echo ""

blastn \
    -query "$CONTIGS" \
    -db "$DB" \
    -outfmt "6 qseqid sseqid pident length qlen qstart qend evalue bitscore" \
    -evalue 1e-50 \
    -word_size 28 \
    -num_threads 4 \
    2>/dev/null > /tmp/blastn_result_${SID}.tsv

if [ ! -s /tmp/blastn_result_${SID}.tsv ]; then
    echo "❌ not Salmonella (no invA hit)"
    echo ""
    echo "结论：contigs 中未找到 invA 基因，样本不是 Salmonella。"
    exit 0
fi

echo "blastn hits (raw):"
cat /tmp/blastn_result_${SID}.tsv
echo ""

echo "=== 过滤后（identity > 90% AND coverage > 80%）==="
significant_hits=$(awk -F'\t' '$3 > 90 && ($4/$5) > 0.8 { print; count++ } END { if(count>0) exit 0; else exit 1 }' /tmp/blastn_result_${SID}.tsv)

if [ $? -eq 0 ]; then
    echo "$significant_hits"
    hit_count=$(echo "$significant_hits" | wc -l)
    best_identity=$(echo "$significant_hits" | sort -t$'\t' -k3 -rn | head -1 | cut -f3)
    best_coverage=$(echo "$significant_hits" | awk -F'\t' '{cov=($4/$5)*100; if(cov>max) max=cov} END{printf "%.1f%%", max}')
    echo ""
    echo "✅ Salmonella confirmed"
    echo "  significant hits: $hit_count"
    echo "  best identity: ${best_identity}%"
    echo "  best coverage: $best_coverage"
else
    echo "（无显著命中）"
    echo ""
    echo "⚠️  ambiguous (low identity or coverage)"
    echo "  可能有 invA 同源基因但非 Salmonella invA，建议人工检查。"
fi

echo ""
echo "判定标准: identity > 90% AND query coverage > 80%"
echo "参考: FDA BAM Chapter 5, invA gene (M90846.1)"
