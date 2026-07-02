rule genome_annotation:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        annotation = str(WORKDIR) + "/{sample}/annotation/annotation.json"
    params:
        script = str(PROJECT_ROOT / "src/hermes_bacmap/genome_annotator.py"),
        python = str(PROJECT_ROOT / ".venv/bin/python")
    shell:
        "mkdir -p $(dirname {output.annotation}) && "
        "{params.python} -c \""
        "import sys; sys.path.insert(0, '{PROJECT_ROOT}/src'); "
        "from hermes_bacmap.genome_annotator import annotate; "
        "r = annotate('{input.contigs}', '{wildcards.sample}'); "
        "r.save('{output.annotation}')"
        "\""
