# Step 5-9: MLST + AMR + 毒力 + 质粒 + 血清型 (project.md §7.1 steps 5-9)

ABRICATE_MINID = config["tools"]["abricate"]["minid"]
ABRICATE_MINCOV = config["tools"]["abricate"]["mincov"]
GMLST_BIN = str(PROJECT_ROOT / ".venv-gmlst/bin/gmlst")

rule typing_mlst:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/mlst.tsv"
    params:
        scheme = "salmonella_2"
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "export PATH={GMLST_BIN}:$PATH && "
        "{GMLST_BIN} typing mlst -s {params.scheme} "
        "-o {output.result} {input.contigs} 2>/dev/null || "
        "echo -e 'File\\tScheme\\tST\\taroC\\tdnaN\\themD\\thisD\\tpurE\\tsucA\\tthrA\\n{wildcards.sample}\\tsalmonella_2\\tN/A\\t-\\t-\\t-\\t-\\t-\\t-\\t-' > {output.result}"

rule typing_sistr:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        json = str(WORKDIR) + "/{sample}/typing/sistr.json",
        cgmlst = str(WORKDIR) + "/{sample}/typing/sistr_cgmlst.csv"
    threads: config["tools"]["sistr"]["threads"]
    params:
        prefix = str(WORKDIR) + "/{sample}/typing/{sample}_sistr"
    shell:
        "mkdir -p $(dirname {output.json}) && "
        "sistr -i {input.contigs} {wildcards.sample} "
        "-f json -o {params.prefix}.json -MM --more-results "
        "--run-mash -p {output.cgmlst} -t {threads} -T $(dirname {output.json}) && "
        "mv {params.prefix}.json {output.json}"

rule amr_abricate_vfdb:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/amr/abricate_vfdb.tsv"
    params:
        minid = ABRICATE_MINID,
        mincov = ABRICATE_MINCOV
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "abricate --db vfdb --minid {params.minid} --mincov {params.mincov} "
        "{input.contigs} > {output.result}"

rule amr_abricate_card:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/amr/abricate_card.tsv"
    params:
        minid = ABRICATE_MINID,
        mincov = ABRICATE_MINCOV
    shell:
        "abricate --db card --minid {params.minid} --mincov {params.mincov} "
        "{input.contigs} > {output.result}"

rule amr_abricate_plasmidfinder:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/plasmid/abricate_plasmidfinder.tsv"
    params:
        minid = ABRICATE_MINID,
        mincov = ABRICATE_MINCOV
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "abricate --db plasmidfinder --minid {params.minid} --mincov {params.mincov} "
        "{input.contigs} > {output.result}"
