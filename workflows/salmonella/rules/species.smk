rule species_identify:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/species/species_id.json"
    params:
        venv_py = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        pixi_bin = str(PROJECT_ROOT / ".pixi/envs/default/bin"),
        fallback = '{{"species":"Unknown","confidence":"low","detected_markers":[],"interpretation":"species_identify failed"}}'
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "export PATH={params.pixi_bin}:$PATH && "
        "{params.venv_py} -m hermes_bacmap.species_identifier "
        "{input.contigs} --json > {output.result} || "
        "echo '{params.fallback}' > {output.result}"
