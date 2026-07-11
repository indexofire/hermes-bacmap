rule genome_annotation:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        annotation = str(WORKDIR) + "/{sample}/annotation/annotation.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = lambda wc: str(WORKDIR) + f"/{wc.sample}/assembly/contigs.fasta",
        sample = lambda wc: wc.sample,
        out = lambda wc: str(WORKDIR) + f"/{wc.sample}/annotation/annotation.json"
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.genome_annotator import annotate; "
        "r = annotate('{params.contigs}', '{params.sample}'); "
        "r.save('{params.out}')"
        "\""
