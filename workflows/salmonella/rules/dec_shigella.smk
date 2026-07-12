# DEC + Shigella 分析 (project.md §7.3.2-3)
# ecoh_serotyper O:H 血清型 + pathotype + ipaH 物种鉴别

rule dec_ecoh_serotype:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/dec/ecoh_serotype.json"
    threads: 4
    params:
        venv_py = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        pixi_bin = str(PROJECT_ROOT / ".pixi/envs/default/bin"),
        fallback = '{{"serotype":"-:-","o_type":"-","h_type":"-","o_antigen_hits":[],"h_antigen_hits":[],"interpretation":"ecoh_serotyper failed"}}'
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "export PATH={params.pixi_bin}:$PATH && "
        "{params.venv_py} -m hermes_bacmap.ecoh_serotyper "
        "{input.contigs} --json > {output.result} || "
        "echo '{params.fallback}' > {output.result}"

rule dec_pathotype:
    input:
        vfdb = str(WORKDIR) + "/{sample}/amr/abricate_vfdb.tsv"
    output:
        result = str(WORKDIR) + "/{sample}/dec/pathotype.tsv"
    params:
        py_script = str(PROJECT_ROOT / "workflows/salmonella/scripts/call_pathotype.py")
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "python3 {params.py_script} --vfdb {input.vfdb} --output {output.result}"


rule shigella_serotype:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/dec/shigella_serotype.json"
    params:
        venv_py = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        pixi_bin = str(PROJECT_ROOT / ".pixi/envs/default/bin"),
        fallback = '{{"species":"N/A","serotype":"Undetermined","confidence":"low","detected_genes":[],"interpretation":"shigella_serotyper failed"}}'
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "export PATH={params.pixi_bin}:$PATH && "
        "{params.venv_py} -m hermes_bacmap.shigella_serotyper "
        "{input.contigs} --json > {output.result} || "
        "echo '{params.fallback}' > {output.result}"
