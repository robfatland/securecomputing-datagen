# BUILD: Generating Synthetic PHI Data

Step-by-step instructions for generating the full synthetic dataset (PD0–PD3).

> **Prerequisites:** Ubuntu/WSL, Java 17 JDK, Python 3.10+ with pandas/numpy, ~10 GB free disk space.
> **Output location:** `~/securecomputing-data/` (not in this repo — data stays out of git).
> **Design specifications:** See `docs/DATA_DESIGN.md` for distributions, schemas, and coherence rules.

---

## Synthea: Role in This Project

[Synthea](https://github.com/synthetichealth/synthea) is an open-source synthetic patient generator. It produced the base population of 11,272 patients with full medical histories — demographics, encounters, conditions, medications, procedures, lab results, and vitals (~7 GB of CSV data).

**What Synthea provides:** The raw patient data foundation (PD0 starting point).

**What this project's code adds on top of Synthea output:**

| Script | Purpose |
|--------|---------|
| `synthea_to_omop.py` | Custom ETL: converts Synthea CSV format → OMOP CDM v5.4 tables |
| `generate_phi.py` | Adds MRNs (project format) and consolidates PHI identifiers |
| `assign_stones.py` | Overlays kidney stone episodes onto Synthea patients (80% get stones) |
| `enrich_omop_stones.py` | Adds stone diagnoses, procedures, and composition measurements to OMOP |
| `generate_pd1.py` | Generates CIF files (PXRD + FTIR) from stone composition assignments |
| `generate_pd2.py` | Generates VCF files with stone-correlated genetic variants |
| `generate_pd3.py` | Generates longitudinal lab results correlated with stone type |
| `generate_manifest.py` | SHA-256 checksums for upload validation |

**After data generation is complete:** The `~/synthea` folder can be deleted (~500 MB) — the output is preserved in `~/securecomputing-data/synthea_raw/`. Synthea is only needed again if regenerating patients (different count, geography, etc.).

---

## Step 1: Install Synthea

> ⚠️ **Build note:** The Synthea project (github.com/synthetichealth/synthea) was built for the purpose of generating synthetic EHR data, but deployment and execution was found to be problematical in this prototype build. Issues encountered included: git clone failures on WSL, Java toolchain detection failures with Gradle 9.x, and undocumented default export format (FHIR JSON rather than CSV). Eventually a successful procedure was produced (May 2026) by the `kiro` AI Coding Assistant as described below. No official Docker container exists from the Synthea team; community images exist but are FHIR-focused. A project-specific Dockerfile is a future to-do item.

Synthea is an open-source synthetic patient generator written in Java. It produces realistic (but fabricated) patient records including demographics, conditions, medications, procedures, encounters, and lab results.

**Source:** https://github.com/synthetichealth/synthea

### 1.1 Prerequisites

```bash
# Java 17 JDK required (Synthea source compatibility = Java 17)
sudo apt update
sudo apt install openjdk-17-jdk

# Verify
javac -version   # Should show 17.x.x

# Set JAVA_HOME (add to ~/.bashrc for persistence)
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
```

### 1.2 Download and Build Synthea

```bash
cd ~
wget https://github.com/synthetichealth/synthea/archive/refs/heads/master.zip -O synthea.zip
unzip synthea.zip
mv synthea-master synthea
rm synthea.zip

cd ~/synthea
chmod +x gradlew
./gradlew build -x test
```

> **Note:** `git clone` may fail on WSL due to large pack file issues. The zip download is reliable.

Build takes ~2–3 minutes. You should see `BUILD SUCCESSFUL`.

---

## Step 2: Configure Synthea for CSV Export

Synthea defaults to FHIR JSON export. You must enable CSV export:

```bash
cd ~/synthea
sed -i 's/exporter.csv.export = false/exporter.csv.export = true/' src/main/resources/synthea.properties
sed -i 's/exporter.fhir.export = true/exporter.fhir.export = false/' src/main/resources/synthea.properties
```

Verify:
```bash
grep "exporter.csv.export" src/main/resources/synthea.properties
# Should show: exporter.csv.export = true
grep "exporter.fhir.export" src/main/resources/synthea.properties
# Should show: exporter.fhir.export = false
```

---

## Step 3: Run Synthea

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd ~/synthea
./run_synthea -p 10000 Washington
```

**Expected runtime:** ~30 minutes.

**Verify and copy output:**
```bash
wc -l output/csv/patients.csv
# Should be ~10,001–11,300 (Synthea slightly overshoots)

mkdir -p ~/securecomputing-data/synthea_raw
cp output/csv/*.csv ~/securecomputing-data/synthea_raw/
du -sh ~/securecomputing-data/synthea_raw/
# Expected: ~7 GB
```

---

## Step 4: ETL to OMOP CDM

> ⚠️ **Build note:** The community ETL-Synthea-Python tool (github.com/science-automation/ETL-Synthea-Python) is incompatible with modern pandas (uses removed `.append()` method) and current Synthea column names (expects `DATE` instead of `START`). A custom ETL script was written for this project.

Convert Synthea CSVs to OMOP CDM v5.4 format using the project's custom ETL:

```bash
cd ~/securecomputing-datagen
python generators/synthea_to_omop.py \
  --synthea-dir ~/securecomputing-data/synthea_raw \
  --output-dir ~/securecomputing-data/pd0
```

**Expected output:**
```
person.csv: ~11,272 rows
observation_period.csv: ~11,272 rows
visit_occurrence.csv: ~628,000 rows
condition_occurrence.csv: ~385,000 rows
drug_exposure.csv: ~499,000 rows
procedure_occurrence.csv: ~1,718,000 rows
measurement.csv: ~2,961,000 rows
observation.csv: ~1,105,000 rows
```

> **Note:** concept_id columns are set to 0 (source codes preserved in `*_source_value` columns). Full OMOP vocabulary mapping is a refinement step. The OMOP vocabulary files from Athena (downloaded to `~/securecomputing-data/vocabulary/`) are available for future concept_id resolution.

---

## Step 5: Generate PHI Extension

Assign MRNs and consolidate PHI identifiers:

```bash
cd ~/securecomputing-datagen
python generators/generate_phi.py \
  --synthea-patients ~/securecomputing-data/synthea_raw/patients.csv \
  --output ~/securecomputing-data/pd0/phi_mapping.csv
```

**Output:** `phi_mapping.csv` — maps each patient to MRN (format: `[A-Z]\d{8}`), name, DOB, address, phone, SSN, email.

---

## Step 6: Assign Stone Episodes and Types

Create the master assignment file that drives PD1, PD2, and PD3:

```bash
python generators/assign_stones.py \
  --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv \
  --output ~/securecomputing-data/pd0/patient_stones.csv
```

**Expected output:**
```
Patients with stones: ~80%
Patients without stones: ~20%
Total stone episodes: ~14,600
```

**Distributions applied:**
- Episode count: 20% zero, 40% one, 30% two, 10% three
- Stone type per episode: drawn from mineral composition distribution (see DATA_DESIGN.md)

---

## Step 7: Enrich OMOP with Stone-Related Records

Append kidney stone diagnoses, procedures, and composition measurements to OMOP tables:

```bash
python generators/enrich_omop_stones.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --omop-dir ~/securecomputing-data/pd0
```

**What this adds:**
- `condition_occurrence.csv`: +14,638 nephrolithiasis diagnoses
- `procedure_occurrence.csv`: +29,276 procedures (stone collection + crystallography per episode)
- `measurement.csv`: +22,287 composition results

---

## Step 9: Generate PD1 (Kidney Stone CIF Files)

```bash
python generators/generate_pd1.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --output-dir ~/securecomputing-data/pd1
```

Produces ~14,638 CIF files with synthetic PXRD + FTIR data. Each file's spectral pattern is determined by the mineral composition assigned in Step 6.

**Expected:** ~58 MB total.

---

## Step 10: Generate PD2 (Genomics VCF Files)

```bash
python generators/generate_pd2.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv \
  --output-dir ~/securecomputing-data/pd2
```

Produces 11,272 VCF files. Stone patients have pathogenic variants in stone-associated genes (10 genes); non-stone patients have only background variants.

**Expected:** ~143 MB total.

---

## Step 11: Generate PD3 (Lab Results)

```bash
python generators/generate_pd3.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv \
  --output ~/securecomputing-data/pd3/lab_results.csv
```

Produces longitudinal lab values (3–12 visits per patient, multiple panels per visit). Values are correlated with stone type per the clinically coherent design.

**Expected:** ~1.5M rows, ~99 MB.

---

## Step 12: Generate Manifest

```bash
python generators/generate_manifest.py \
  --data-dir ~/securecomputing-data \
  --output ~/securecomputing-data/manifest.json
```

Produces SHA-256 checksums for all generated files. Used by the upload validation Lambda in the analysis environment to verify data integrity after transfer.

**Expected:** ~25,900 files, ~896 MB total.

---

## Full Pipeline Summary

```bash
cd ~/securecomputing-datagen

# Step 4: ETL
python generators/synthea_to_omop.py --synthea-dir ~/securecomputing-data/synthea_raw --output-dir ~/securecomputing-data/pd0

# Step 5: PHI
python generators/generate_phi.py --synthea-patients ~/securecomputing-data/synthea_raw/patients.csv --output ~/securecomputing-data/pd0/phi_mapping.csv

# Step 6: Stone assignments
python generators/assign_stones.py --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv --output ~/securecomputing-data/pd0/patient_stones.csv

# Step 7: Enrich OMOP
python generators/enrich_omop_stones.py --stones ~/securecomputing-data/pd0/patient_stones.csv --omop-dir ~/securecomputing-data/pd0

# Step 9: PD1
python generators/generate_pd1.py --stones ~/securecomputing-data/pd0/patient_stones.csv --output-dir ~/securecomputing-data/pd1

# Step 10: PD2
python generators/generate_pd2.py --stones ~/securecomputing-data/pd0/patient_stones.csv --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv --output-dir ~/securecomputing-data/pd2

# Step 11: PD3
python generators/generate_pd3.py --stones ~/securecomputing-data/pd0/patient_stones.csv --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv --output ~/securecomputing-data/pd3/lab_results.csv

# Step 12: Manifest
python generators/generate_manifest.py --data-dir ~/securecomputing-data --output ~/securecomputing-data/manifest.json
```

Steps 1–3 (Synthea install, configure, run) are one-time setup performed manually.

---

## Code Status Summary

| Script | Status | Step |
|--------|--------|------|
| `generators/synthea_to_omop.py` | ✅ Working | 4 |
| `generators/generate_phi.py` | ✅ Working | 5 |
| `generators/assign_stones.py` | ✅ Working | 6 |
| `generators/enrich_omop_stones.py` | ✅ Working | 7 |
| `generators/generate_pd1.py` | ✅ Working | 9 |
| `generators/generate_pd2.py` | ✅ Working | 10 |
| `generators/generate_pd3.py` | ✅ Working | 11 |
| `generators/generate_manifest.py` | ✅ Working | 12 |
| `run_all.py` | ❌ Not written | Full pipeline orchestrator |

---

## Actual Results (May 2026 run)

| Dataset | Files | Rows | Size |
|---------|-------|------|------|
| PD0 (OMOP) | 8 CSVs | ~7.3M total rows | ~595 MB |
| PD1 (CIF) | 14,638 | — | 58 MB |
| PD2 (VCF) | 11,272 | — | 143 MB |
| PD3 (CSV) | 1 | 1,468,728 | 99 MB |
| **Total** | **25,928** | — | **896 MB** |
