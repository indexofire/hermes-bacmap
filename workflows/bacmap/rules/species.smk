rule species_identify:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/species/species_id.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/species/species_id.json",
        fallback = '{"species":"Unknown","confidence":"low","detected_markers":[],"interpretation":"species_identify failed"}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.analysis.species_identifier import identify; "
        "import json; r = identify('{params.contigs}'); "
        "json.dump(r.to_dict() if hasattr(r,'to_dict') else r, "
        "open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"


# sourmash gather identification (species-id plan B). Same gating model as
# species_ani: Snakefile adds the target only when mode=sourmash AND the
# signature database is installed.
rule species_sourmash:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/species/species_sourmash.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/species/species_sourmash.json",
        fallback = '{"analysis_type":"species_identification","method":"sourmash","database":{"name":"sourmash_gtdb","version":"unknown"},"result":{"species":"Unknown","confidence":"low"}}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.analysis.sourmash_identifier import identify_by_sourmash; "
        "r = identify_by_sourmash('{params.contigs}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"
rule species_ani:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/species/species_ani.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        mode = config["species_mode"],
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/species/species_ani.json",
        fallback = '{"analysis_type":"species_identification","method":"PLACEHOLDER","database":{"name":"x","version":"unknown"},"result":{"species":"Unknown","confidence":"low","interpretation":"species_ani failed"}}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.analysis.ani_identifier import identify_by_ani; "
        "r = identify_by_ani('{params.contigs}', '{params.mode}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"
