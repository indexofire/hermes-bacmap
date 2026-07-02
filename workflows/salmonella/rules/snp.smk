_SALMONELLA_REF = str(PROJECT_ROOT / "data/reference/salmonella_LT2_ref.fasta")
_PIXI = str(PROJECT_ROOT / ".pixi/envs/default/bin")
_SALMONELLA_SAMPLES = [s for s in SAMPLES if SAMPLES_DF.loc[s, "species"] == "Salmonella"]

rule snp_calling:
    input:
        r1 = lambda wc: str(PROJECT_ROOT / SAMPLES_DF.loc[wc.sample, "R1"]),
        r2 = lambda wc: str(PROJECT_ROOT / SAMPLES_DF.loc[wc.sample, "R2"])
    output:
        bam = str(WORKDIR) + "/{sample}/snp/snps.bam"
    params:
        outdir = str(WORKDIR) + "/{sample}/snp",
        ref = _SALMONELLA_REF,
        pixi = _PIXI
    threads: 8
    shell:
        "mkdir -p {params.outdir} && "
        "export PATH={params.pixi}:$PATH && "
        "bwa mem -t {threads} -Y -M {params.ref} {input.r1} {input.r2} 2>/dev/null | "
        "samtools sort -@ 4 -o {output.bam} && "
        "samtools index {output.bam}"

rule joint_variant_calling:
    input:
        bams = expand(str(WORKDIR) + "/{sample}/snp/snps.bam", sample=_SALMONELLA_SAMPLES)
    output:
        vcfgz = str(WORKDIR) + "/snp/joint.vcf.gz"
    params:
        ref = _SALMONELLA_REF,
        pixi = _PIXI,
        samples = _SALMONELLA_SAMPLES,
        workdir = str(WORKDIR)
    threads: 8
    run:
        import os
        os.makedirs(params.workdir + "/snp", exist_ok=True)
        bam_list = " ".join(f"{params.workdir}/{s}/snp/snps.bam" for s in params.samples)
        rename_lines = "\n".join(
            f"{params.workdir}/{s}/snp/snps.bam\t{s}" for s in params.samples
        )
        with open(output.vcfgz + ".rename.tsv", "w") as fh:
            fh.write(rename_lines + "\n")
        shell(
            "export PATH={params.pixi}:$PATH && "
            "bcftools mpileup -f {params.ref} -q 20 -Q 20 --max-depth 200 "
            "{bams} 2>/dev/null | "
            "bcftools call -mv --ploidy 1 2>/dev/null | "
            "bcftools reheader -s {output.vcfgz}.rename.tsv 2>/dev/null | "
            "bcftools view -Oz -o {output.vcfgz} 2>/dev/null && "
            "bcftools index {output.vcfgz} 2>/dev/null",
            bams=bam_list,
        )

rule snp_matrix:
    input:
        vcfgz = str(WORKDIR) + "/snp/joint.vcf.gz"
    output:
        fasta = str(WORKDIR) + "/snp/core_snps.fasta"
    params:
        script = str(PROJECT_ROOT / "workflows/salmonella/scripts/generate_snp_matrix.py"),
        python = str(PROJECT_ROOT / ".venv/bin/python")
    shell:
        "mkdir -p $(dirname {output.fasta}) && "
        "{params.python} {params.script} {input.vcfgz} {output.fasta}"

rule phylo_tree:
    input:
        fasta = str(WORKDIR) + "/snp/core_snps.fasta"
    output:
        tree = str(WORKDIR) + "/snp/core.treefile",
        report = str(WORKDIR) + "/snp/core.iqtree"
    params:
        outdir = str(WORKDIR) + "/snp",
        pixi = _PIXI
    shell:
        "export PATH={params.pixi}:$PATH && "
        "cd {params.outdir} && "
        "iqtree -s core_snps.fasta -m GTR -bb 1000 -alrt 1000 "
        "-nt AUTO -pre core 2>&1 | tail -3 && "
        "test -f core.treefile && cp core.treefile {output.tree} && "
        "cp core.iqtree {output.report} || "
        "echo '((placeholder));' > {output.tree}"
