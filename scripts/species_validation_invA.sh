#!/usr/bin/env bash
# Salmonella 物种验证：用 bwa mem 把 reads 比对到 invA 靶基因。
# FDA BAM Chapter 5 invA PCR 的 in silico 版（Rahn et al. 1992）。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
export PATH="$PROJECT_ROOT/.pixi/envs/default/bin:$PATH"
DATA_DIR="$PROJECT_ROOT/tests/fixtures/gold_standard/salmonella/data"
REF_FASTA="$PROJECT_ROOT/data/reference/salmonella_invA.fasta"
THREADS=8

echo "=== Salmonella invA 物种验证 ==="
echo "参考: $(head -1 "$REF_FASTA")"
echo ""

if [ ! -f "${REF_FASTA}.bwt" ]; then
    bwa index "$REF_FASTA" 2>/dev/null
fi

printf "%-14s %-22s %10s %10s %10s %s\n" "strain_id" "serovar" "total_pe" "mapped" "coverage" "result"
printf '%s\n' "------------------------------------------------------------------------------------"

for dir in "$DATA_DIR"/SAM-*; do
    [ -d "$dir" ] || continue
    sid=$(basename "$dir")
    r1="$dir/${sid}_R1.fastq.gz"
    r2="$dir/${sid}_R2.fastq.gz"

    [ -f "$r1" ] && [ -f "$r2" ] || continue

    stats=$(bwa mem -t "$THREADS" "$REF_FASTA" "$r1" "$r2" 2>/dev/null | \
            samtools flagstat -)

    mapped=$(echo "$stats" | grep "primary" | head -1 | grep -oP '^\d+')
    total=$(echo "$stats" | grep "in total" | grep -oP '^\d+')
    pct=$(echo "$stats" | grep "in total" | grep -oP '\d+\.\d+%' | head -1)

    [ -z "$mapped" ] && mapped=0
    [ -z "$total" ] && total=0
    [ -z "$pct" ] && pct="N/A"

    # 阈值 100 mapped reads = invA 基因确实存在（~50x 覆盖 2.1 kb 基因）
    if [ "$mapped" -gt 100 ]; then
        result="✅ Salmonella"
    elif [ "$mapped" -gt 0 ]; then
        result="⚠️  low mapping"
    else
        result="❌ not Salmonella"
    fi

    serovar=$(python3 -c "
import csv
with open('$PROJECT_ROOT/tests/fixtures/gold_standard/salmonella/gold_standard.csv') as f:
    for r in csv.DictReader(f):
        if r['strain_id'] == '$sid':
            print(r['serovar'])
            break
" 2>/dev/null || echo "?")

    printf "%-14s %-22s %10s %10s %10s %s\n" "$sid" "$serovar" "$total" "$mapped" "$pct" "$result"
done

echo ""
echo "判定标准: mapped reads > 100 = Salmonella 阳性（invA 基因存在）"
echo "参考: FDA BAM Chapter 5 (invA PCR), Rahn et al. 1992"
