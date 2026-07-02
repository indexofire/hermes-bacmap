"""Snakemake script: collect all analysis results into a summary JSON."""
import json
import sys
from pathlib import Path

sample = snakemake.wildcards.sample
summary = {"sample": sample, "steps": {}}

def read_file(path, default="N/A"):
    p = Path(path)
    if p.exists() and p.stat().st_size > 0:
        return p.read_text().strip()
    return default

def read_json(path, default=None):
    p = Path(path)
    if p.exists() and p.stat().st_size > 0:
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return default
    return default

def parse_tsv(path, default=None):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return default
    lines = p.read_text().strip().split("\n")
    if len(lines) < 2:
        return default
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        fields = line.split("\t")
        if len(fields) >= len(headers):
            rows.append(dict(zip(headers, fields)))
    return rows

qc = read_json(snakemake.input.qc_json, {})
summary["steps"]["qc"] = {
    "after_filtering": qc.get("filtering_result", {}),
    "before_filtering": qc.get("summary", {}).get("before_filtering", {}),
}

asm_text = read_file(snakemake.input.assembly_stats, "")
summary["steps"]["assembly"] = asm_text

species_id = read_json(snakemake.input.species_id, {})
if not isinstance(species_id, dict):
    species_id = {}
summary["steps"]["species"] = species_id

mlst_text = read_file(snakemake.input.mlst, "")
summary["steps"]["mlst"] = mlst_text

sistr = read_json(snakemake.input.sistr, [])
if isinstance(sistr, list) and sistr:
    sistr = sistr[0]
if not isinstance(sistr, dict):
    sistr = {}
summary["steps"]["serotype"] = {
    "sistr": sistr.get("serovar", "N/A"),
    "serogroup": sistr.get("serogroup", "N/A"),
    "o_antigen": sistr.get("o_antigen", "N/A"),
    "h1": sistr.get("h1", "N/A"),
    "h2": sistr.get("h2", "N/A"),
}

summary["steps"]["amr"] = {
    "abricate_vfdb": parse_tsv(snakemake.input.vfdb, []),
    "abricate_card": parse_tsv(snakemake.input.card, []),
}

summary["steps"]["plasmid"] = {
    "plasmidfinder": parse_tsv(snakemake.input.plasmidfinder, []),
}

dec_serotype = read_json(snakemake.input.ectyper, {})
if not isinstance(dec_serotype, dict):
    dec_serotype = {}
dec_pathotype = read_file(snakemake.input.pathotype, "N/A")
ipah = "ipaH_positive" if any(m.get("gene") == "ipaH" for m in species_id.get("detected_markers", [])) else "ipaH_negative"
summary["steps"]["dec"] = {
    "ecoh_serotype": dec_serotype.get("serotype", "N/A"),
    "o_type": dec_serotype.get("o_type", "-"),
    "h_type": dec_serotype.get("h_type", "-"),
    "interpretation": dec_serotype.get("interpretation", ""),
    "pathotype": dec_pathotype,
    "ipaH": ipah,
}

shigella_serotype = read_json(snakemake.input.shigella_serotype, {})
if not isinstance(shigella_serotype, dict):
    shigella_serotype = {}
summary["steps"]["dec"]["shigella_serotype"] = shigella_serotype.get("serotype", "N/A")
summary["steps"]["dec"]["shigella_species"] = shigella_serotype.get("species", "N/A")

ecoh_serotype_val = dec_serotype.get("serotype", "-:-")
shigella_species_val = shigella_serotype.get("species", "N/A")
shigella_serotype_val = shigella_serotype.get("serotype", "Undetermined")

if "Shigella" in shigella_species_val and "Undetermined" not in shigella_serotype_val:
    primary_serotype = shigella_serotype_val
    serotype_method = "shigella_serotyper"
elif ecoh_serotype_val != "-:-":
    primary_serotype = ecoh_serotype_val
    serotype_method = "ecoh_serotyper (DEC/EIEC)"
else:
    sistr_serovar = sistr.get("serovar", "N/A") if isinstance(sistr, dict) else "N/A"
    primary_serotype = sistr_serovar
    serotype_method = "SISTR (Salmonella)"

summary["steps"]["dec"]["primary_serotype"] = primary_serotype
summary["steps"]["dec"]["serotype_method"] = serotype_method


Path(snakemake.output.summary).parent.mkdir(parents=True, exist_ok=True)
Path(snakemake.output.summary).write_text(
    json.dumps(summary, ensure_ascii=False, indent=2)
)
