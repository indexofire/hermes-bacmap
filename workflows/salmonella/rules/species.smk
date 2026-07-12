rule species_identify:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/species/species_id.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = lambda wc: str(WORKDIR) + f"/{wc.sample}/assembly/contigs.fasta",
        out = lambda wc: str(WORKDIR) + f"/{wc.sample}/species/species_id.json",
        fallback = '{{"species":"Unknown","confidence":"low","detected_markers":[],"interpretation":"species_identify failed"}}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.species_identifier import identify; "
        "import json; r = identify('{params.contigs}'); "
        "json.dump(r.to_dict() if hasattr(r,'to_dict') else r, "
        "open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"
