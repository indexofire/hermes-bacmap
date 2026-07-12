_SALMONELLA_REF = str(PROJECT_ROOT / "data/reference/salmonella_LT2_ref.fasta")
_PIXI = str(PROJECT_ROOT / ".pixi/envs/default/bin")
_SALMONELLA_SAMPLES = [s for s in SAMPLES if SAMPLES_DF.loc[s, "species"] == "Salmonella"]

rule snp_calling:
    input:
        r1 = lambda wc: str(WORKDIR) + f"/{wc.sample}/qc/{wc.sample}_clean_R1.fastq.gz",
        r2 = lambda wc: str(WORKDIR) + f"/{wc.sample}/qc/{wc.sample}_clean_R2.fastq.gz"
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
        "bwa mem -t {threads} -Y -M {params.ref} {input.r1} {input.r2} | "
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
            "{bams} | "
            "bcftools call -mv --ploidy 1 | "
            "bcftools reheader -s {output.vcfgz}.rename.tsv | "
            "bcftools view -Oz -o {output.vcfgz} && "
            "bcftools index {output.vcfgz}",
            bams=bam_list,
        )

rule snp_matrix:
    input:
        vcfgz = str(WORKDIR) + "/snp/joint.vcf.gz"
    output:
        fasta = str(WORKDIR) + "/snp/core_snps.fasta"
    params:
        script = str(PROJECT_ROOT / "workflows/salmonella/scripts/generate_snp_matrix.py"),
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python")
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
        "-nt AUTO -pre core && "
        "cp core.treefile {output.tree} && "
        "cp core.iqtree {output.report}"

rule snp_summary:
    input:
        tree = str(WORKDIR) + "/snp/core.treefile",
        fasta = str(WORKDIR) + "/snp/core_snps.fasta"
    output:
        summary = str(WORKDIR) + "/snp/snp_summary.json"
    params:
        script = str(PROJECT_ROOT / "workflows/salmonella/scripts/generate_snp_summary.py"),
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python")
    shell:
        "{params.python} {params.script} {input.tree} {input.fasta} {output.summary}"
