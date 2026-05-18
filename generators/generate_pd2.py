"""
Step 10: Generate PD2 — Genomics VCF Files
============================================
Reads patient_stones.csv and generates one VCF file per patient containing
synthetic genetic variants. Patients with kidney stones have pathogenic
variants in stone-associated genes; patients without stones have only
background (benign) variants.

Usage:
    python generators/generate_pd2.py \
        --stones ~/securecomputing-data/pd0/patient_stones.csv \
        --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv \
        --output-dir ~/securecomputing-data/pd2
"""

import argparse
import csv
import json
import random
import numpy as np
from pathlib import Path


# Stone-associated genes with genomic coordinates (GRCh38)
STONE_GENES = {
    'SLC3A1':   {'chr': 'chr2',  'start': 44485000, 'end': 44535000, 'stones': ['cystine']},
    'SLC7A9':   {'chr': 'chr19', 'start': 33053000, 'end': 33075000, 'stones': ['cystine']},
    'CLCN5':    {'chr': 'chrX',  'start': 49850000, 'end': 50020000, 'stones': ['pure_com', 'mixed_com_cod', 'pure_cod', 'com_calcium_phosphate']},
    'CASR':     {'chr': 'chr3',  'start': 122174000, 'end': 122240000, 'stones': ['pure_com', 'mixed_com_cod', 'pure_cod', 'com_calcium_phosphate']},
    'VDR':      {'chr': 'chr12', 'start': 47841000, 'end': 47905000, 'stones': ['pure_com', 'mixed_com_cod', 'pure_cod', 'com_calcium_phosphate']},
    'AGXT':     {'chr': 'chr2',  'start': 241498000, 'end': 241513000, 'stones': ['pure_com', 'mixed_com_cod', 'pure_cod', 'com_calcium_phosphate']},
    'GRHPR':    {'chr': 'chr9',  'start': 37421000, 'end': 37436000, 'stones': ['pure_com', 'mixed_com_cod', 'pure_cod', 'com_calcium_phosphate']},
    'HOGA1':    {'chr': 'chr10', 'start': 97580000, 'end': 97610000, 'stones': ['pure_com', 'mixed_com_cod', 'pure_cod', 'com_calcium_phosphate']},
    'SLC22A12': {'chr': 'chr11', 'start': 64581000, 'end': 64592000, 'stones': ['pure_uric_acid', 'uric_acid_com']},
    'APRT':     {'chr': 'chr16', 'start': 88811000, 'end': 88814000, 'stones': ['mixed_other']},
}

# Common background variant chromosomes and rough gene-dense regions
BACKGROUND_CHROMS = ['chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6', 'chr7',
                     'chr8', 'chr9', 'chr10', 'chr11', 'chr12', 'chr13',
                     'chr14', 'chr15', 'chr16', 'chr17', 'chr18', 'chr19',
                     'chr20', 'chr21', 'chr22']

BASES = ['A', 'C', 'G', 'T']


def get_alt_base(ref):
    """Return a random alternate base different from reference."""
    alts = [b for b in BASES if b != ref]
    return random.choice(alts)


def generate_pathogenic_variants(stone_types):
    """Generate pathogenic variants based on patient's stone type(s)."""
    variants = []
    
    # Collect all stone types this patient has had
    relevant_genes = []
    for gene_name, gene_info in STONE_GENES.items():
        for st in stone_types:
            if st in gene_info['stones']:
                relevant_genes.append((gene_name, gene_info))
                break
    
    # VDR is special — common polymorphism, include at population frequency
    # For stone patients, include 1-3 pathogenic variants in relevant genes
    if relevant_genes:
        # Pick 1-2 genes to have variants in
        n_genes = min(len(relevant_genes), random.randint(1, 2))
        selected = random.sample(relevant_genes, n_genes)
        
        for gene_name, gene_info in selected:
            # Generate 1-2 variants per gene
            n_variants = random.randint(1, 2)
            for _ in range(n_variants):
                pos = random.randint(gene_info['start'], gene_info['end'])
                ref = random.choice(BASES)
                alt = get_alt_base(ref)
                qual = random.randint(25, 50)
                dp = random.randint(30, 100)
                variants.append({
                    'chrom': gene_info['chr'],
                    'pos': pos,
                    'ref': ref,
                    'alt': alt,
                    'qual': qual,
                    'filter': 'PASS',
                    'info': f'DP={dp};GENE={gene_name};PATHOGENIC',
                })
    
    return variants


def generate_background_variants(n_variants):
    """Generate benign background variants across the genome."""
    variants = []
    for _ in range(n_variants):
        chrom = random.choice(BACKGROUND_CHROMS)
        pos = random.randint(1000000, 200000000)
        ref = random.choice(BASES)
        alt = get_alt_base(ref)
        qual = random.randint(15, 45)
        dp = random.randint(20, 80)
        variants.append({
            'chrom': chrom,
            'pos': pos,
            'ref': ref,
            'alt': alt,
            'qual': qual,
            'filter': 'PASS',
            'info': f'DP={dp}',
        })
    return variants


def write_vcf(filepath, mrn, variants):
    """Write a VCF v4.3 file."""
    # Sort variants by chromosome and position
    chrom_order = {f'chr{i}': i for i in range(1, 23)}
    chrom_order['chrX'] = 23
    chrom_order['chrY'] = 24
    variants.sort(key=lambda v: (chrom_order.get(v['chrom'], 99), v['pos']))
    
    with open(filepath, 'w') as f:
        # Header
        f.write("##fileformat=VCFv4.3\n")
        f.write("##source=securecomputing-datagen\n")
        f.write(f"##patient_mrn={mrn}\n")
        f.write("##reference=GRCh38\n")
        f.write('##INFO=<ID=DP,Number=1,Type=Integer,Description="Read Depth">\n')
        f.write('##INFO=<ID=GENE,Number=1,Type=String,Description="Gene name">\n')
        f.write('##INFO=<ID=PATHOGENIC,Number=0,Type=Flag,Description="Pathogenic variant">\n')
        f.write('##FILTER=<ID=PASS,Description="All filters passed">\n')
        f.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        
        # Variants
        for v in variants:
            f.write(f"{v['chrom']}\t{v['pos']}\t.\t{v['ref']}\t{v['alt']}\t"
                    f"{v['qual']}\t{v['filter']}\t{v['info']}\n")


def main():
    parser = argparse.ArgumentParser(description='Generate PD2 genomics VCF files')
    parser.add_argument('--stones', required=True, help='Path to patient_stones.csv')
    parser.add_argument('--phi-mapping', required=True, help='Path to phi_mapping.csv')
    parser.add_argument('--output-dir', required=True, help='Output directory for VCF files')
    parser.add_argument('--seed', type=int, default=43, help='Random seed')
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load stone assignments grouped by patient
    patient_stones = {}  # mrn → list of stone_types
    with open(args.stones, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mrn = row['mrn']
            if mrn not in patient_stones:
                patient_stones[mrn] = []
            if row['stone_type'] != 'none':
                patient_stones[mrn].append(row['stone_type'])

    # Load all patient MRNs (including those without stones)
    all_mrns = []
    with open(args.phi_mapping, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_mrns.append(row['mrn'])

    # Generate VCF for each patient
    files_written = 0
    for mrn in all_mrns:
        stone_types = patient_stones.get(mrn, [])
        
        # Background variants (100-500 per patient)
        n_background = random.randint(100, 500)
        variants = generate_background_variants(n_background)
        
        # Pathogenic variants (only for stone patients)
        if stone_types:
            pathogenic = generate_pathogenic_variants(stone_types)
            variants.extend(pathogenic)
        
        # Write VCF
        filename = f"patient_{mrn}.vcf"
        filepath = output_dir / filename
        write_vcf(filepath, mrn, variants)
        files_written += 1
        
        if files_written % 1000 == 0:
            print(f"  {files_written} files written...")

    print(f"\nPD2 generation complete: {files_written} VCF files → {output_dir}")


if __name__ == '__main__':
    main()
