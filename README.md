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

## Output Specification

The project generates four synthetic datasets:

| Dataset | Description | Format | Volume |
|---------|-------------|--------|--------|
| **PD0** | Patient EHR (OMOP CDM v5.4) | CSV (OMOP tables) | 10,000 patients, ~500K+ rows across tables |
| **PD1** | X-ray crystallography | CIF or structured files | 0–3 per patient (~15K files) |
| **PD2** | Gene sequence data | VCF (Variant Call Format) | 1 per patient (10K files) |
| **PD3** | Lab test results | CSV (tabular) | Multiple per patient over time |

All datasets linked by synthetic MRN. See `docs/DATA_DESIGN.md` for full specification.

## Repository Structure

```
securecomputing-datagen/
├── README.md                 # This file
├── LICENSE
├── config/                   # Generator configuration
│   └── README.md
├── generators/               # Data generation scripts
│   └── README.md
├── schemas/                  # Output schema definitions
│   └── README.md
├── output/                   # Generated data (gitignored — large files)
│   └── .gitkeep
└── docs/                     # Documentation specific to data generation
    └── README.md
```

## Status

🔄 **Specifications complete. Generator code not yet written.** See `BUILD.md` for the full step-by-step pipeline and code status.

## Related

- Analysis environment: [`securecomputing`](https://github.com/[owner]/securecomputing)
- Upload path specification: `securecomputing/ARCHITECTURE.md` → "Raw PHI Upload Path Security"
- Project overview: `securecomputing/PROJECT_OVERVIEW.md`
