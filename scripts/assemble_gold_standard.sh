#!/usr/bin/env bash
# SPAdes/Shovill 批量组装 6 株 Salmonella Gold standard。
# 使用 Shovill（封装 SPAdes，含 read correction + contig filtering）。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/.pixi/envs/default/bin:$PATH"
DATA_DIR="$PROJECT_ROOT/tests/fixtures/gold_standard/salmonella/data"
OUT_DIR="$PROJECT_ROOT/data/assemblies"
THREADS=8

mkdir -p "$OUT_DIR"

assemble_strain() {
    local sid="$1"
    local r1="$DATA_DIR/$sid/${sid}_R1.fastq.gz"
    local r2="$DATA_DIR/$sid/${sid}_R2.fastq.gz"
    local out="$OUT_DIR/$sid"

    if [ -f "$out/contigs.fasta" ]; then
        echo "[$sid] already assembled, skip"
        return 0
    fi

    echo "[$(date +%H:%M:%S)] [$sid] assembling with Shovill..."
    shovill \
        --R1 "$r1" --R2 "$r2" \
        --outdir "$out" --force \
        --minlen 500 --cpus "$THREADS" 2>&1 | tail -2

    if [ -f "$out/contigs.fa" ]; then
        cp "$out/contigs.fa" "$OUT_DIR/$sid/contigs.fasta"
        local stats=$(seqkit stats -T "$OUT_DIR/$sid/contigs.fasta" 2>/dev/null | tail -1)
        echo "[$(date +%H:%M:%S)] [$sid] done: $stats"
    else
        echo "[$(date +%H:%M:%S)] [$sid] FAILED"
    fi
}

echo "=== SPAdes 批量组装 ($(date)) ==="
echo "Threads: $THREADS per strain"
echo ""

for sid in SAM-TYP-001 SAM-TYP-002 SAM-ENT-003 SAM-ENT-004 SAM-INF-005 SAM-NEW-006; do
    assemble_strain "$sid"
done

echo ""
echo "=== 组装结果汇总 ==="
printf "%-14s %12s %10s %10s %10s\n" "strain_id" "total_len" "num_contigs" "N50" "max_len"
for sid in SAM-TYP-001 SAM-TYP-002 SAM-ENT-003 SAM-ENT-004 SAM-INF-005 SAM-NEW-006; do
    contigs="$OUT_DIR/$sid/contigs.fasta"
    if [ -f "$contigs" ]; then
        seqkit stats -T "$contigs" 2>/dev/null | tail -1 | awk -F'\t' -v s="$sid" '{printf "%-14s %12s %10s %10s %10s\n", s, $4, $3, $5, $6}'
    fi
done

echo ""
echo "[$(date)] All assemblies complete."
