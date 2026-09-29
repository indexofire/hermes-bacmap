# Phase 3 typing rules: V. cholerae / L. monocytogenes / C. difficile / B. cereus
# Follows the dec_shigella.smk pattern: Python module call with fallback JSON.

_TYPING_PYTHON = str(PROJECT_ROOT / ".pixi/envs/default/bin/python")
_SRC_PATH = str(PROJECT_ROOT / "src")

rule vcholerae_genotype:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/vcholerae_genotype.json"
    params:
        python = _TYPING_PYTHON,
        src_path = _SRC_PATH,
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/typing/vcholerae_genotype.json",
        fallback = '{"species":"Unknown","toxigenic":false,"ctxa_positive":false,"ompw_positive":false,"confidence":"low","interpretation":"vcholerae_genotype failed"}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.typing.vcholerae_genotype import genotype; "
        "r = genotype('{params.contigs}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"

rule lmono_serogroup:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/lmono_serogroup.json"
    params:
        python = _TYPING_PYTHON,
        src_path = _SRC_PATH,
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/typing/lmono_serogroup.json",
        fallback = '{"species":"Unknown","serogroup":"Nontypeable","confidence":"low","interpretation":"lmono_serogroup failed"}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.typing.lmono_serogroup import serogroup; "
        "r = serogroup('{params.contigs}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"

rule cdiff_toxin:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/cdiff_toxin.json"
    params:
        python = _TYPING_PYTHON,
        src_path = _SRC_PATH,
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/typing/cdiff_toxin.json",
        fallback = '{"species":"Unknown","toxigenic":false,"toxinotype":"unknown","confidence":"low","interpretation":"cdiff_toxin failed"}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.typing.cdiff_toxin import toxin_type; "
        "r = toxin_type('{params.contigs}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"

rule bcereus_toxin:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/bcereus_toxin.json"
    params:
        python = _TYPING_PYTHON,
        src_path = _SRC_PATH,
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta",
        out = str(WORKDIR) + "/{sample}/typing/bcereus_toxin.json",
        fallback = '{"species":"Unknown","toxin_type":"non-toxigenic","confidence":"low","interpretation":"bcereus_toxin failed"}'
    shell:
        "mkdir -p $(dirname {params.out}) && "
        "{params.python} -c \""
        "import sys, json; sys.path.insert(0, '{params.src_path}'); "
        "from hermes_bacmap.typing.bcereus_toxin import toxin_type; "
        "r = toxin_type('{params.contigs}'); "
        "json.dump(r.to_dict(), open('{params.out}', 'w'), ensure_ascii=False, indent=2)"
        "\" || echo '{params.fallback}' > {params.out}"
