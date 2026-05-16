# Synthetic Data Design

## Overview

This project generates four categories of synthetic data (PD0–PD3) for 10,000 patients. All datasets are linked by a common synthetic MRN, enabling cross-dataset analysis that mimics real multi-modal clinical research.

| Dataset | Description | Records | Link to Patient |
|---------|-------------|---------|-----------------|
| **PD0** | Patient EHR in OMOP CDM format | 10,000 patients (multiple rows per patient across OMOP tables) | MRN in PERSON table |
| **PD1** | X-ray crystallography data | 0–3 per patient (0–30,000 files) | MRN in metadata |
| **PD2** | Gene sequence data | 1 per patient (10,000 files) | MRN in metadata |
| **PD3** | Lab test results (blood protein levels, etc.) | Multiple per patient over time | MRN links to MEASUREMENT in PD0 |

---

## PD0: Synthetic Patient EHR (OMOP CDM)

### Does OMOP make sense?

Yes — OMOP (Observational Medical Outcomes Partnership) Common Data Model is the standard for this use case:

- **Purpose-built** for observational health research on EHR data
- **Widely adopted** — used by OHDSI network (hundreds of institutions, billions of patient records)
- **Standardized vocabularies** — ICD-10, SNOMED-CT, RxNorm, LOINC mapped to common concept IDs
- **Tooling exists** — Synthea generates synthetic patients; OHDSI provides an ETL to convert Synthea output to OMOP format
- **Research-ready** — designed for exactly the kind of cohort analysis this project does

### OMOP CDM Structure (relevant tables)

The OMOP CDM (v5.4) organizes patient data into standardized tables. Key tables for this project:

| OMOP Table | Contains | PHI Elements | Relevance to PD1–PD3 |
|------------|----------|--------------|---------------------|
| **PERSON** | Demographics: birth year, gender, race, ethnicity, location | Name*, MRN*, DOB, address, race | Central identity; MRN links to all other datasets |
| **OBSERVATION_PERIOD** | Time spans during which patient has records | Dates | Defines when patient data is "active" |
| **VISIT_OCCURRENCE** | Healthcare encounters (inpatient, outpatient, ER) | Dates, facility | Context for when PD1/PD3 data was collected |
| **CONDITION_OCCURRENCE** | Diagnoses (ICD-10 → SNOMED concepts) | Dates, diagnosis codes | Patient history relevant to PD1–PD3 interpretation |
| **DRUG_EXPOSURE** | Medications prescribed/administered | Dates, drug codes | May affect PD3 lab values |
| **PROCEDURE_OCCURRENCE** | Procedures performed | Dates, procedure codes | Includes imaging orders (links to PD1) |
| **MEASUREMENT** | Lab results, vital signs, test values | Dates, values, units | **PD3 lab results map directly here** |
| **OBSERVATION** | Other clinical observations | Dates, values | Catch-all for data not fitting other tables |
| **NOTE** | Clinical notes (free text) | Dates, text content | Optional; high PHI density |
| **SPECIMEN** | Biological samples collected | Dates, specimen type | Links to PD2 (gene sequencing from specimen) |

*Note: Standard OMOP doesn't include names or MRNs (it uses numeric person_id). For this project, we extend with a mapping table that adds synthetic names, MRNs, and addresses to simulate full PHI.*

### Generation Pipeline for PD0

```
Step 1: Synthea                    Step 2: ETL-Synthea              Step 3: PHI Extension
─────────────────                  ─────────────────                ─────────────────────
Generate 10,000                    Convert Synthea CSV              Add synthetic PHI:
synthetic patients                 to OMOP CDM v5.4                - Names (Faker)
(demographics,                     tables (using OHDSI             - MRNs (format: [A-Z]\d{8})
conditions, meds,                  ETL-Synthea package)            - Addresses
labs, procedures)                                                  - Phone numbers
                                                                   - SSNs (fake)
Output: Synthea CSV                Output: OMOP tables             Output: PHI mapping table
                                   (person, condition_             (person_id → name, MRN,
                                    occurrence, measurement,        address, phone, SSN)
                                    drug_exposure, etc.)
```

**Tools:**
- [Synthea](https://github.com/synthetichealth/synthea) — open-source synthetic patient generator (Java)
- [ETL-Synthea](https://github.com/OHDSI/ETL-Synthea) — OHDSI's official Synthea-to-OMOP converter (R package, also available in Python: [ETL-Synthea-Python](https://github.com/science-automation/ETL-Synthea-Python))
- [Faker](https://github.com/joke2k/faker) — Python library for generating realistic fake names, addresses, phone numbers, etc.

### OMOP Tables We Generate

| Table | Rows (approx) | Key Fields |
|-------|---------------|------------|
| PERSON | 10,000 | person_id, gender_concept_id, year_of_birth, race_concept_id, location_id |
| OBSERVATION_PERIOD | 10,000 | person_id, observation_period_start_date, observation_period_end_date |
| VISIT_OCCURRENCE | ~50,000 | person_id, visit_start_date, visit_concept_id, visit_type_concept_id |
| CONDITION_OCCURRENCE | ~100,000 | person_id, condition_concept_id, condition_start_date |
| DRUG_EXPOSURE | ~150,000 | person_id, drug_concept_id, drug_exposure_start_date |
| PROCEDURE_OCCURRENCE | ~30,000 | person_id, procedure_concept_id, procedure_date |
| MEASUREMENT | ~200,000 | person_id, measurement_concept_id, value_as_number, unit_concept_id |
| SPECIMEN | ~10,000 | person_id, specimen_concept_id, specimen_date |
| PHI_MAPPING (custom) | 10,000 | person_id, mrn, full_name, address, phone, ssn, email |

### Patient History Relevant to PD1–PD3

Each synthetic patient's OMOP record will include condition/procedure history that contextualizes the other datasets:

- **For PD1 (crystallography):** Patients with crystallography data will have relevant procedure orders (e.g., "imaging study ordered") and conditions that justify the imaging
- **For PD2 (gene sequencing):** Patients will have specimen collection records and conditions suggesting genetic testing was indicated
- **For PD3 (lab results):** Lab results in PD3 will also appear in the MEASUREMENT table, linked by date and concept ID — PD3 is essentially a detailed export of a subset of MEASUREMENT data

---

## PD1: Synthetic X-ray Crystallography Data (Kidney Stone Composition)

### Overview

| Attribute | Value |
|-----------|-------|
| **Clinical context** | Kidney stone composition analysis. Patient passes or has stone surgically removed; specimen sent to lab for crystallographic analysis to determine mineral composition. Results inform treatment (e.g., dietary modification, medication). |
| **Records** | 0–3 per patient (not all patients have kidney stones; some have recurrent stones). Estimated ~5,000–8,000 total files. |
| **Format** | CIF (Crystallographic Information File) — plain-text, human-readable, IUCr standard |
| **Size per file** | ~1–5 KB (crystallography of known minerals is compact) |
| **Link to patient** | Metadata file maps filename → MRN; filename contains MRN |
| **OMOP integration** | PROCEDURE_OCCURRENCE (stone collection/removal), SPECIMEN (kidney stone), CONDITION_OCCURRENCE (nephrolithiasis), MEASUREMENT (composition percentages) |

### Clinical Pathway in OMOP

```
PERSON (patient)
  └── CONDITION_OCCURRENCE: Nephrolithiasis (SNOMED 95570007)
  └── PROCEDURE_OCCURRENCE: Lithotripsy or surgical stone removal
  └── SPECIMEN: Kidney stone specimen collected
  └── CIF file: Crystallographic analysis of specimen
  └── MEASUREMENT: Stone composition (e.g., 80% calcium oxalate monohydrate, 20% calcium phosphate)
```

### Common Kidney Stone Compositions (for synthetic generation)

| Mineral | Chemical Formula | Frequency in Real Stones | CIF Cell Parameters (approx) |
|---------|-----------------|-------------------------|------------------------------|
| **Whewellite** (calcium oxalate monohydrate) | CaC₂O₄·H₂O | ~70% of stones | a=6.29, b=14.58, c=10.11, β=109.5° |
| **Weddellite** (calcium oxalate dihydrate) | CaC₂O₄·2H₂O | ~10% | a=12.37, b=12.37, c=7.36 (tetragonal) |
| **Uric acid** | C₅H₄N₄O₃ | ~10% | a=14.46, b=7.40, c=6.21, β=65.1° |
| **Struvite** (magnesium ammonium phosphate) | MgNH₄PO₄·6H₂O | ~5% | a=6.94, b=6.14, c=11.20 (orthorhombic) |
| **Brushite** (calcium hydrogen phosphate) | CaHPO₄·2H₂O | ~3% | a=5.81, b=15.18, c=6.24, β=116.4° |
| **Cystine** | C₆H₁₂N₂O₄S₂ | ~1% | a=5.42, b=7.34, c=10.91 (hexagonal) |

### Generation Approach

Each synthetic CIF file represents a kidney stone with:
- One or two mineral phases (mixed composition stones are common)
- Randomized proportions (e.g., 75% whewellite + 25% weddellite)
- Cell parameters drawn from known values with small random perturbation (simulating measurement noise)
- Atom coordinates from published crystal structures of each mineral
- Metadata header including synthetic patient MRN, specimen date, and analysis date

```
data_stone_B48291037_001
_audit_creation_date    2024-03-15
_chemical_name_mineral  'Whewellite'
_chemical_formula_sum   'Ca C2 O4 H2 O'
_cell_length_a          6.290(3)
_cell_length_b          14.583(7)
_cell_length_c          10.112(5)
_cell_angle_alpha       90.00
_cell_angle_beta        109.46(2)
_cell_angle_gamma       90.00
_symmetry_space_group_name_H-M 'P 2_1/c'
_pd_phase_block_id      phase_1_of_2
_pd_phase_mass_%        78.3

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Ca1 Ca 0.2500 0.0833 0.4167
C1  C  0.1250 0.2500 0.3750
O1  O  0.0833 0.1667 0.2917
O2  O  0.1667 0.3333 0.4583
...
```

> 🔄 **Details TBD:** Exact atom coordinate sets will be drawn from published crystal structure databases (e.g., COD — Crystallography Open Database) for each mineral. The generation script will assemble multi-phase CIF files with randomized proportions and realistic measurement uncertainties.

---

## PD2: Synthetic Gene Sequence Data

### Overview

| Attribute | Value |
|-----------|-------|
| **Records** | 1 per patient (10,000 files) |
| **Suggested format** | FASTQ (raw sequence reads) or VCF (variant calls) |
| **Size per file** | FASTQ: ~1–10 MB compressed per sample (for a targeted panel); VCF: ~1–5 MB |
| **Link to patient** | Filename contains MRN; metadata maps to OMOP person_id |
| **OMOP integration** | SPECIMEN record (sample collected) + PROCEDURE_OCCURRENCE (sequencing performed) |

### Format Recommendation: VCF (Variant Call Format)

VCF is recommended over FASTQ for this project because:
- Smaller files (more practical for 10,000 patients)
- Structured format (chromosome, position, reference, alternate, quality)
- Directly interpretable (variants, not raw reads)
- Standard in clinical genomics pipelines
- Easy to generate synthetically (random variants at plausible genomic positions)

**VCF structure (simplified):**
```
##fileformat=VCFv4.3
##source=securecomputing-datagen
#CHROM  POS     ID      REF  ALT  QUAL  FILTER  INFO
chr1    12345   .       A    G    30    PASS    DP=50
chr2    67890   .       C    T    25    PASS    DP=42
...
```

### Generation Approach (TBD)

- Generate synthetic VCF files with randomized variants
- Use realistic chromosome positions and allele frequencies
- Vary number of variants per patient (100–10,000 variants per file)
- Include header metadata linking to patient MRN

> 🔄 **Details TBD.** Scientific validity of variant calls is not required — the data must be structurally correct (valid VCF format) and linked to patients.

---

## PD3: Synthetic Lab Test Results

### Overview

| Attribute | Value |
|-----------|-------|
| **Records** | Multiple per patient over time (longitudinal) |
| **Format** | CSV/Parquet — tabular data |
| **Content** | Blood protein levels, metabolic panels, CBC, etc. |
| **Link to patient** | MRN column; maps to OMOP MEASUREMENT table |
| **OMOP integration** | PD3 is a detailed export of MEASUREMENT data — same concept IDs, same dates |

### Relationship to OMOP MEASUREMENT Table

PD3 and the OMOP MEASUREMENT table overlap intentionally:
- MEASUREMENT contains all lab results in OMOP's standardized format (concept IDs, standard units)
- PD3 provides the same data in a "raw lab export" format (as it might arrive from a clinical lab system before OMOP transformation)
- This simulates the real-world scenario: lab data arrives in a source format and is ETL'd into OMOP

### Suggested Lab Panels

| Panel | Tests | Units | Normal Range |
|-------|-------|-------|--------------|
| **Basic Metabolic Panel (BMP)** | Glucose, BUN, Creatinine, Sodium, Potassium, Chloride, CO2, Calcium | mg/dL, mEq/L, mmol/L | Standard clinical ranges |
| **Complete Blood Count (CBC)** | WBC, RBC, Hemoglobin, Hematocrit, Platelets, MCV, MCH | cells/μL, g/dL, % | Standard clinical ranges |
| **Lipid Panel** | Total cholesterol, LDL, HDL, Triglycerides | mg/dL | Standard clinical ranges |
| **Liver Function** | ALT, AST, ALP, Bilirubin, Albumin | U/L, mg/dL, g/dL | Standard clinical ranges |
| **HbA1c** | Hemoglobin A1c | % | <5.7 normal, 5.7–6.4 prediabetes, ≥6.5 diabetes |

### Generation Approach (TBD)

- Generate time-series lab values per patient (3–20 lab visits over observation period)
- Values drawn from distributions matching normal/abnormal ranges
- Correlate with OMOP conditions (diabetic patients have elevated HbA1c; liver disease patients have elevated ALT/AST)
- Include realistic noise and occasional missing values

> 🔄 **Details TBD.** Key requirement: structurally valid lab data, linked to patients, with clinically plausible (not random) value distributions.

---

## Cross-Dataset Linkage

All datasets link through the synthetic MRN:

```
PHI_MAPPING table (PD0)
├── person_id: 1001
├── mrn: "B48291037"
├── name: "Jane Martinez"
├── dob: "1967-04-12"
│
├──► PD0 (OMOP): PERSON.person_id = 1001
│    ├── CONDITION_OCCURRENCE (diabetes, hypertension)
│    ├── MEASUREMENT (HbA1c = 7.2, glucose = 145)
│    ├── PROCEDURE_OCCURRENCE (crystallography study, gene panel)
│    └── SPECIMEN (blood draw 2024-03-15)
│
├──► PD1 (Crystallography): metadata.mrn = "B48291037"
│    ├── study_001.cif (2024-01-20)
│    └── study_002.cif (2024-06-15)
│
├──► PD2 (Genomics): patient_B48291037.vcf
│    └── 3,247 variants called
│
└──► PD3 (Lab results): lab_results.csv WHERE mrn = "B48291037"
     ├── 2024-01-15: BMP, CBC, HbA1c
     ├── 2024-04-20: BMP, Lipid Panel
     └── 2024-07-10: BMP, CBC, HbA1c, Liver Function
```

### MRN Format

| Attribute | Value |
|-----------|-------|
| **Format** | One uppercase letter + 8 digits (e.g., `B48291037`) |
| **Uniqueness** | Guaranteed unique across all 10,000 patients |
| **Generation** | Random; no encoding of patient information in the MRN itself |
| **Purpose** | Links all four datasets; exercises PHI detection (gatekeeper should recognize this pattern) |

---

## Output Structure

```
output/
├── pd0_omop/
│   ├── person.csv
│   ├── observation_period.csv
│   ├── visit_occurrence.csv
│   ├── condition_occurrence.csv
│   ├── drug_exposure.csv
│   ├── procedure_occurrence.csv
│   ├── measurement.csv
│   ├── specimen.csv
│   ├── phi_mapping.csv          ← The PHI extension (names, MRNs, addresses)
│   └── vocabulary/              ← OMOP standard vocabulary files
├── pd1_crystallography/
│   ├── metadata.csv             ← Maps filename → MRN → dates
│   └── files/
│       ├── study_B48291037_001.cif
│       ├── study_B48291037_002.cif
│       └── ...
├── pd2_genomics/
│   ├── metadata.csv             ← Maps filename → MRN → specimen date
│   └── files/
│       ├── patient_B48291037.vcf
│       ├── patient_C19374625.vcf
│       └── ...
├── pd3_lab_results/
│   └── lab_results.csv          ← All patients, all visits, all panels
└── manifest.json                ← File inventory + SHA-256 checksums (for upload validation)
```

---

## Generation Dependencies

| Tool | Purpose | Language |
|------|---------|----------|
| **Synthea** | Generate base synthetic patients (demographics, conditions, meds, procedures) | Java (CLI) |
| **ETL-Synthea-Python** | Convert Synthea output to OMOP CDM tables | Python |
| **Faker** | Generate realistic names, addresses, phone numbers, SSNs | Python |
| **Custom generators** | PD1 (crystallography), PD2 (VCF), PD3 (lab values) | Python |
| **pandas** | Data manipulation and output formatting | Python |
| **numpy** | Statistical distributions for lab values and variant generation | Python |

---

## Relationship to Upload Path

Generated data is delivered to the analysis environment (`securecomputing`) via the standard upload path documented in `ARCHITECTURE.md`:

1. Generation runs in the datagen environment (local or separate CI)
2. Output files written to `output/`
3. `manifest.json` generated (file list + SHA-256 checksums)
4. Upload to S3 landing zone via AWS CLI (assuming the upload IAM role)
5. Validation Lambda verifies manifest and checksums
6. Data moves to validated zone → ready for research use

This dogfoods the entire upload security pipeline with synthetic data before real PHI ever touches the system.
