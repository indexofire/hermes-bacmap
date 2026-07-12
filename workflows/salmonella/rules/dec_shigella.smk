# DEC + Shigella 分析 (project.md §7.3.2-3)

rule dec_ecoh_serotype:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/dec/ecoh_serotype.json"
    threads: 4
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = lambda wc: str(WORKDIR) + f"/{wc.sample}/assembly/contigs.fasta",
        out = lambda wc: str(WORKDIR) + f"/{wc.sample}/dec/ecoh_serotype.json",
        fallback = '{{"serotype":"-:-","o_type":"-","h_type":"-","o_antigen_hits":[],"h_antigen_hits":[],"interpretation":"ecoh_serotyper failed"}}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.ecoh_serotyper import EcohSerotyper; "
        "import json; r = EcohSerotyper.identify('{params.contigs}'); "
        "json.dump(r.to_dict() if hasattr(r,'to_dict') else r, "
        "open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"

rule dec_pathotype:
    input:
        vfdb = str(WORKDIR) + "/{sample}/amr/abricate_vfdb.tsv"
    output:
        result = str(WORKDIR) + "/{sample}/dec/pathotype.tsv"
    params:
        py_script = str(PROJECT_ROOT / "workflows/salmonella/scripts/call_pathotype.py"),
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python")
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{params.python} {params.py_script} --vfdb {input.vfdb} --output {output.result}"


rule shigella_serotype:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/dec/shigella_serotype.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = lambda wc: str(WORKDIR) + f"/{wc.sample}/assembly/contigs.fasta",
        out = lambda wc: str(WORKDIR) + f"/{wc.sample}/dec/shigella_serotype.json",
        fallback = '{{"species":"N/A","serotype":"Undetermined","confidence":"low","detected_genes":[],"interpretation":"shigella_serotyper failed"}}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.shigella_serotyper import ShigellaSerotyper; "
        "import json; r = ShigellaSerotyper.identify('{params.contigs}'); "
        "json.dump(r.to_dict() if hasattr(r,'to_dict') else r, "
        "open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"
