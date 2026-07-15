# Step 5-9: MLST + AMR + 毒力 + 质粒 + 血清型 (project.md §7.1 steps 5-9)

ABRICATE_MINID = config["tools"]["abricate"]["minid"]
ABRICATE_MINCOV = config["tools"]["abricate"]["mincov"]
_GMLST_SCHEMES = {
    "Salmonella": "salmonella_2",
    "E.coli": "ecoli_1",
    "Shigella": "ecoli_1",
    "V.parahaemolyticus": "vparahaemolyticus_1",
}
GMLST_BIN = str(PROJECT_ROOT / ".pixi/envs/default/bin/gmlst")

rule typing_mlst:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/mlst.tsv"
    params:
        scheme = lambda wc: _GMLST_SCHEMES.get(
            SAMPLES_DF.loc[wc.sample, "species"], "salmonella_2"
        )
    threads: 4
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{GMLST_BIN} typing mlst -s {params.scheme} "
        "-o {output.result} {input.contigs} || "
        "echo -e 'File\\tScheme\\tST\\n{wildcards.sample}\\t{params.scheme}\\tN/A' > {output.result}"

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
        "mv {params.prefix}.json {output.json} || "
        "echo '{{\"serovar\":\"N/A\",\"serogroup\":\"N/A\",\"o_antigen\":\"N/A\",\"h1\":\"N/A\",\"h2\":\"N/A\"}}' > {output.json}"

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
        pixi = str(PROJECT_ROOT / ".pixi/envs/default/bin"),
        minid = ABRICATE_MINID,
        mincov = ABRICATE_MINCOV
    threads: 2
    shell:
        "mkdir -p $(dirname {output.result}) && "
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
