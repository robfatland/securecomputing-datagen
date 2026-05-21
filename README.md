# securecomputing-datagen

Generate synthetic data as a proxy for PHI. Used as source data in the `securecomputing` analysis infrastructure.

## Purpose

This repository contains tooling to generate synthetic patient records that mimic real PHI in structure and complexity without using actual patient information. The generated data is loaded into the analysis environment (`securecomputing`) via the standard upload path, dogfooding the upload security, validation, and handoff protocol.

## Relationship to the Analysis System

```
securecomputing-datagen              securecomputing (analysis environment)
────────────────────────             ─────────────────────────────────────
Generate synthetic PHI  ──(upload)──►  S3 landing zone → validation → use
                                      (same path real PHI would take)
```

**Isolation principle:** This repo has no access to the analysis environment. The analysis environment has no dependency on this repo's internals — only on the output data format. If synthetic data is later replaced with real PHI, nothing in the analysis environment changes.

## Output Summary

| Dataset | Description | Format | Volume |
|---------|-------------|--------|--------|
| **PD0** | Patient EHR (OMOP CDM v5.4) | CSV (8 OMOP tables) | 11,272 patients, ~7.3M rows |
| **PD1** | Kidney stone composition (PXRD + FTIR) | CIF files | 14,638 files, 58 MB |
| **PD2** | Gene sequence data (10 stone-associated genes) | VCF files | 11,272 files, 143 MB |
| **PD3** | Lab test results (longitudinal, correlated with stone type) | CSV | 1,468,728 rows, 99 MB |

**Total:** 25,928 files, 896 MB. All linked by synthetic MRN.

**Output location:** `~/securecomputing-data/` (not in this repo — data stays out of git).

## Repository Structure

```
securecomputing-datagen/
├── README.md                 # This file
├── BUILD.md                  # Step-by-step generation instructions
├── LICENSE
├── .gitignore
├── generators/               # Data generation scripts (all working)
│   ├── synthea_to_omop.py   # Step 4: Custom Synthea → OMOP ETL
│   ├── generate_phi.py      # Step 5: PHI mapping (MRNs, names, etc.)
│   ├── assign_stones.py     # Step 6: Stone episode/type assignment
│   ├── enrich_omop_stones.py # Step 7: Add stone records to OMOP
│   ├── generate_pd1.py      # Step 9: CIF files (PXRD + FTIR)
│   ├── generate_pd2.py      # Step 10: VCF files (genomics)
│   ├── generate_pd3.py      # Step 11: Lab results CSV
│   └── generate_manifest.py # Step 12: SHA-256 checksums
├── docs/
│   └── DATA_DESIGN.md       # Specifications, distributions, coherence rules
├── config/
├── schemas/
└── output/                   # Legacy (output now goes to ~/securecomputing-data/)
```

## Quick Start

See `BUILD.md` for full instructions. Summary:

```bash
# One-time: Install Synthea (Java 17), configure CSV export, generate patients
# Then:
cd ~/securecomputing-datagen
python generators/synthea_to_omop.py --synthea-dir ~/securecomputing-data/synthea_raw --output-dir ~/securecomputing-data/pd0
python generators/generate_phi.py --synthea-patients ~/securecomputing-data/synthea_raw/patients.csv --output ~/securecomputing-data/pd0/phi_mapping.csv
python generators/assign_stones.py --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv --output ~/securecomputing-data/pd0/patient_stones.csv
python generators/enrich_omop_stones.py --stones ~/securecomputing-data/pd0/patient_stones.csv --omop-dir ~/securecomputing-data/pd0
python generators/generate_pd1.py --stones ~/securecomputing-data/pd0/patient_stones.csv --output-dir ~/securecomputing-data/pd1
python generators/generate_pd2.py --stones ~/securecomputing-data/pd0/patient_stones.csv --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv --output-dir ~/securecomputing-data/pd2
python generators/generate_pd3.py --stones ~/securecomputing-data/pd0/patient_stones.csv --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv --output ~/securecomputing-data/pd3/lab_results.csv
python generators/generate_manifest.py --data-dir ~/securecomputing-data --output ~/securecomputing-data/manifest.json
```

## Status

✅ **All generators written and tested.** Full pipeline produces 896 MB of synthetic data (May 2026).

## Related

- Analysis environment: [`securecomputing`](https://github.com/robfatland/securecomputing)
- Upload path specification: `securecomputing/ARCHITECTURE.md` → "Raw PHI Upload Path Security"
- Project overview: `securecomputing/PROJECT_OVERVIEW.md`
- Synthetic data overview (from analysis side): `securecomputing/SYNTHETIC_DATA.md`

---

## Generating PDF Documentation

All markdown files can be consolidated into a single PDF using Pandoc.

### Prerequisites (WSL/Ubuntu)

**1. Pandoc and LaTeX**

```bash
sudo apt update
sudo apt install -y pandoc texlive-latex-recommended texlive-fonts-recommended \
  texlive-latex-extra texlive-xetex
```

**2. Unicode fonts**

```bash
sudo apt install -y fonts-dejavu
```

**3. Mermaid support (if diagrams are added later)**

```bash
npm install --global @mermaid-js/mermaid-cli mermaid-filter
```

**4. Chromium dependencies (for mermaid-filter)**

```bash
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 libasound2
```

### Generate PDF

```bash
cd ~/securecomputing-datagen
pandoc --toc --toc-depth=2 -V geometry:margin=1in \
  -V mainfont="DejaVu Sans" -V monofont="DejaVu Sans Mono" \
  --pdf-engine=xelatex \
  --lua-filter=strip-emoji.lua \
  README.md \
  BUILD.md \
  docs/DATA_DESIGN.md \
  -o SecureComputing_DataGen_Book.pdf
```

### Alternative: HTML output (no LaTeX needed)

```bash
pandoc --toc --toc-depth=2 --standalone \
  --lua-filter=strip-emoji.lua \
  README.md BUILD.md docs/DATA_DESIGN.md \
  -o SecureComputing_DataGen_Book.html
```
