# Step 5-9: MLST + AMR + 毒力 + 质粒 + 血清型 (project.md §7.1 steps 5-9)

import sys as _sys

_sys.path.insert(0, str(PROJECT_ROOT / "src"))
from hermes_bacmap.pathogen_registry import get_workflow_tables  # noqa: E402

_TABLES = get_workflow_tables()

GAPIT_MINID = config["tools"]["gapit"]["minid"]
GAPIT_MINCOV = config["tools"]["gapit"]["mincov"]
GAPIT_BIN = str(PROJECT_ROOT / ".pixi/envs/default/bin/gapit")
_GMLST_SCHEMES = _TABLES.mlst_schemes
GMLST_BIN = str(PROJECT_ROOT / ".pixi/envs/default/bin/gmlst")

_AMRFINDER_ORGANISMS = _TABLES.amrfinder_organisms
_AMRFINDER_DB_BASE = Path(PROJECT_ROOT / "data/db/amrfinderplus")
_AMRFINDER_DB_VERSIONS = sorted(p for p in _AMRFINDER_DB_BASE.iterdir() if p.is_dir()) if _AMRFINDER_DB_BASE.exists() else []
AMRFINDER_DB = str(_AMRFINDER_DB_VERSIONS[-1]) if _AMRFINDER_DB_VERSIONS else str(_AMRFINDER_DB_BASE)
AMRFINDER_MINCOV = config["tools"]["amrfinderplus"]["min_coverage"]

rule typing_mlst:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/typing/mlst.tsv"
    params:
        scheme = lambda wc: _GMLST_SCHEMES.get(
            SAMPLES_DF.loc[wc.sample, "species"], "salmonella_2"
        )
    threads: 4
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{GMLST_BIN} typing mlst -s {params.scheme} "
        "-o {output.result} {input.contigs} || "
        "echo -e 'File\\tScheme\\tST\\n{wildcards.sample}\\t{params.scheme}\\tN/A' > {output.result}"

rule typing_sistr:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        json = str(WORKDIR) + "/{sample}/typing/sistr.json",
        cgmlst = str(WORKDIR) + "/{sample}/typing/sistr_cgmlst.csv"
    threads: config["tools"]["sistr"]["threads"]
    params:
        prefix = str(WORKDIR) + "/{sample}/typing/{sample}_sistr"
    shell:
        "mkdir -p $(dirname {output.json}) && "
        "sistr -i {input.contigs} {wildcards.sample} "
        "-f json -o {params.prefix}.json -MM --more-results "
        "--run-mash -p {output.cgmlst} -t {threads} -T $(dirname {output.json}) && "
        "mv {params.prefix}.json {output.json} || "
        "echo '{{\"serovar\":\"N/A\",\"serogroup\":\"N/A\",\"o_antigen\":\"N/A\",\"h1\":\"N/A\",\"h2\":\"N/A\"}}' > {output.json}"

rule amr_gapit_vfdb:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/amr/gapit_vfdb.tsv"
    params:
        minid = GAPIT_MINID,
        mincov = GAPIT_MINCOV
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{GAPIT_BIN} screen --db vfdb --minid {params.minid} --mincov {params.mincov} "
        "{input.contigs} 2>/dev/null | grep -v '^Processing' > {output.result} || "
        "echo -e '#FILE\\tSEQUENCE\\tSTART\\tEND\\tSTRAND\\tGENE\\tCOVERAGE\\tCOVERAGE_MAP\\tGAPS\\t%COVERAGE\\t%IDENTITY\\tDATABASE\\tACCESSION\\tPRODUCT\\tRESISTANCE' > {output.result}"

rule amr_gapit_card:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/amr/gapit_card.tsv"
    params:
        minid = GAPIT_MINID,
        mincov = GAPIT_MINCOV
    threads: 2
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{GAPIT_BIN} screen --db card --minid {params.minid} --mincov {params.mincov} "
        "{input.contigs} 2>/dev/null | grep -v '^Processing' > {output.result} || "
        "echo -e '#FILE\\tSEQUENCE\\tSTART\\tEND\\tSTRAND\\tGENE\\tCOVERAGE\\tCOVERAGE_MAP\\tGAPS\\t%COVERAGE\\t%IDENTITY\\tDATABASE\\tACCESSION\\tPRODUCT\\tRESISTANCE' > {output.result}"

rule amr_gapit_plasmidfinder:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/plasmid/gapit_plasmidfinder.tsv"
    params:
        minid = GAPIT_MINID,
        mincov = GAPIT_MINCOV
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "{GAPIT_BIN} screen --db plasmidfinder --minid {params.minid} --mincov {params.mincov} "
        "{input.contigs} 2>/dev/null | grep -v '^Processing' > {output.result} || "
        "echo -e '#FILE\\tSEQUENCE\\tSTART\\tEND\\tSTRAND\\tGENE\\tCOVERAGE\\tCOVERAGE_MAP\\tGAPS\\t%COVERAGE\\t%IDENTITY\\tDATABASE\\tACCESSION\\tPRODUCT\\tRESISTANCE' > {output.result}"

rule amr_amrfinderplus:
    input:
        contigs = str(WORKDIR) + "/{sample}/assembly/contigs.fasta"
    output:
        result = str(WORKDIR) + "/{sample}/amr/amrfinderplus.tsv"
    params:
        db = AMRFINDER_DB,
        mincov = AMRFINDER_MINCOV,
        org_flag = lambda wc: (
            f"--organism {_AMRFINDER_ORGANISMS[SAMPLES_DF.loc[wc.sample, 'species']]}"
            if SAMPLES_DF.loc[wc.sample, "species"] in _AMRFINDER_ORGANISMS
            else ""
        )
    threads: 4
    shell:
        "mkdir -p $(dirname {output.result}) && "
        "amrfinder -n {input.contigs} -d {params.db} {params.org_flag} "
        "--coverage_min {params.mincov} --threads {threads} "
        "-o {output.result} || touch {output.result}"
