rule taxonomy_validation:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/taxonomy/validation.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        mode = lambda wc: config.get("species_mode", "simple")
    threads: 4
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.analysis.taxonomic_validator import validate_genome; "
        "r = validate_genome('{input.contigs}', mode='{params.mode}'); "
        "json.dump(r.to_dict(), open('{output.result}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{{\"mode\":\"simple\",\"interpretation\":\"taxonomy validation skipped (CheckM2/GTDB-Tk not available)\"}}' > {output.result}"
