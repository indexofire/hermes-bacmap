rule vpara_targets:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/vpara/targets_blastn.tsv",
        verdict = str(WORKDIR) + "/{sample}/vpara/species_verdict.txt"
    params:
        db = str(PROJECT_ROOT / "data/reference/vpara_targets_blastdb")
    threads: 4
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "blastn -query {input.contigs} -db {params.db} "
        "-outfmt '6 qseqid sseqid pident length slen evalue bitscore' "
        "-evalue 1e-50 -word_size 28 -num_threads {threads} "
        "> {output.result}; "
        "if [ -s {output.result} ]; then "
        "  if blastn -query {input.contigs} -db {params.db} "
        "  -outfmt '6 sseqid' -evalue 1e-50 -word_size 28 "
        "  | grep -qi 'toxR\\|tlh'; then "
        "    echo 'V_parahaemolyticus' > {output.verdict}; "
        "  else echo 'ambiguous_vpara' > {output.verdict}; fi; "
        "else echo 'not_V_parahaemolyticus' > {output.verdict}; fi"

rule vpara_virulence:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/vpara/virulence.json"
    params:
        venv_py = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        pixi_bin = str(PROJECT_ROOT / ".pixi/envs/default/bin")
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "export PATH={params.pixi_bin}:$PATH && "
        "{params.venv_py} -c \""
        "import json, subprocess, re; "
        "contigs='{input.contigs}'; "
        "genes={{}}; "
        "[genes.update({{m.group(1): True}}) for gene_name in ['tdh','trh','tlh'] for m in [re.search(r'('+gene_name+r')', gene_name, re.I)] if m]; "
        "for g in ['tdh','trh','tlh']: "
        "  r=subprocess.run(['blastn','-query',contigs,'-db','data/reference/vpara_targets_blastdb','-outfmt','6 sseqid pident','-evalue','1e-50','-word_size','28'],capture_output=True,text=True,timeout=60); "
        "  hits=[l for l in r.stdout.split('\\n') if g.upper() in l.upper()]; "
        "  genes[g]=len(hits)>0; "
        "json.dump({{k:v for k,v in genes.items()}},open('{output.result}','w')); "
        "\" || echo '{{\"tdh\":false,\"trh\":false,\"tlh\":false}}' > {output.result}"

rule vpara_serotype:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/vpa/vpa_serotype.json"
    params:
        python = str(PROJECT_ROOT / ".pixi/envs/default/bin/python"),
        src_path = str(PROJECT_ROOT / "src"),
        contigs = lambda wc: str(WORKDIR) + f"/{wc.sample}/assembly/contigs.fasta",
        sample = lambda wc: wc.sample,
        out = lambda wc: str(WORKDIR) + f"/{wc.sample}/vpa/vpa_serotype.json"
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.vpa_serotyper import VpaSerotyper; "
        "s = VpaSerotyper(); "
        "r = s.analyze('{params.contigs}', '{params.sample}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\""
