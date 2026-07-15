# Step 1: fastp 质控 (project.md §7.1 step 1)

FASTP_Q = config["tools"]["fastp"]["qualified_quality_phred"]
FASTP_LEN = config["tools"]["fastp"]["length_required"]

rule qc_fastp:
    input:
        r1 = r1_path,
        r2 = r2_path
    output:
        r1_clean = temp(str(WORKDIR) + "/{sample}/qc/{sample}_clean_R1.fastq.gz"),
        r2_clean = temp(str(WORKDIR) + "/{sample}/qc/{sample}_clean_R2.fastq.gz"),
        json = str(WORKDIR) + "/{sample}/qc/{sample}_fastp.json",
        html = str(WORKDIR) + "/{sample}/qc/{sample}_fastp.html"
    threads: config["threads"]
    shell:
        "mkdir -p $(dirname {output.json}) && "
        "fastp -i {input.r1} -I {input.r2} "
        "-o {output.r1_clean} -O {output.r2_clean} "
        "--qualified_quality_phred {FASTP_Q} "
        "--length_required {FASTP_LEN} "
        "--detect_adapter_for_pe "
        "--json {output.json} --html {output.html} "
        "--thread {threads}"
