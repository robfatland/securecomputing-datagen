# BUILD: Generating Synthetic PHI Data

Step-by-step instructions for generating the full synthetic dataset (PD0–PD3).

> **Prerequisites:** Ubuntu/WSL, Java 11+, Python 3.10+, ~10 GB free disk space.
> **Output location:** `~/securecomputing-data/` (not in this repo — data stays out of git).
> **Design specifications:** See `docs/DATA_DESIGN.md` for distributions, schemas, and coherence rules.

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

### 1.3 Verify Installation

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd ~/synthea
./run_synthea -p 10 Washington
ls output/csv/
# Should see: patients.csv, conditions.csv, encounters.csv, etc.
rm -rf output/
```

---

## Step 2: Configure Synthea

Synthea's command-line flags handle the key settings. No configuration file edits are needed for this project:

- `-p 10000` sets the population size
- `Washington` sets the geography
- CSV export is enabled by default

> 📋 **NOTE:** Synthea's default modules may not generate kidney stones at the frequency we want (the design calls for 80% of patients having stones). We handle this in Step 6 by *assigning* stone episodes independently of what Synthea generates. Synthea provides patient demographics, encounters, and general medical history; we overlay the kidney stone study data on top.

---

## Step 3: Run Synthea

### 3.1 Generate 10,000 Patients

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd ~/synthea
./run_synthea -p 10000 Washington
```

**Expected runtime:** 10–30 minutes depending on hardware.

**Expected output:** `output/csv/` containing:

| File | Content | Approximate Size |
|------|---------|-----------------|
| `patients.csv` | Demographics (name, DOB, address, SSN, etc.) | ~5 MB |
| `encounters.csv` | Healthcare visits | ~20 MB |
| `conditions.csv` | Diagnoses (SNOMED codes) | ~10 MB |
| `medications.csv` | Prescriptions (RxNorm codes) | ~15 MB |
| `procedures.csv` | Procedures performed | ~5 MB |
| `observations.csv` | Lab results, vitals (LOINC codes) | ~50 MB |
| `allergies.csv` | Patient allergies | ~2 MB |
| `careplans.csv` | Care plans | ~5 MB |
| `immunizations.csv` | Vaccination records | ~5 MB |
| `organizations.csv` | Healthcare facilities | <1 MB |
| `providers.csv` | Healthcare providers | <1 MB |
| `payers.csv` | Insurance information | <1 MB |

**Total:** ~100–150 MB of CSV data.

### 3.2 Verify Output

```bash
# Check patient count
wc -l output/csv/patients.csv
# Should be ~10,001 (header + 10,000 rows)

# Spot check a patient
head -2 output/csv/patients.csv
```

### 3.3 Copy to Working Location

```bash
mkdir -p ~/securecomputing-data/synthea_raw
cp output/csv/*.csv ~/securecomputing-data/synthea_raw/
```

---

## Step 4: ETL to OMOP CDM

Convert Synthea's native CSV format to OMOP Common Data Model v5.4.

### 4.1 Install ETL-Synthea-Python

```bash
cd ~/securecomputing-datagen
pip install pandas numpy

# Clone the ETL tool
git clone https://github.com/science-automation/ETL-Synthea-Python.git
cd ETL-Synthea-Python
```

> 📋 **ALTERNATIVE:** OHDSI's official R package (`ETL-Synthea`) is more mature but requires R. The Python version is adequate for this project and keeps the toolchain in one language.

### 4.2 Download OMOP Vocabularies

OMOP requires standardized vocabulary files (concept IDs for SNOMED, ICD-10, LOINC, RxNorm).

1. Create a free account at https://athena.ohdsi.org/
2. Download vocabularies: select SNOMED, ICD-10, LOINC, RxNorm, and "Gender", "Race", "Ethnicity"
3. Download produces a ~2 GB zip file
4. Extract to `~/securecomputing-data/vocabulary/`

```bash
mkdir -p ~/securecomputing-data/vocabulary
# Extract downloaded zip here
unzip vocabularies_download.zip -d ~/securecomputing-data/vocabulary/
```

### 4.3 Run the ETL

```bash
cd ~/securecomputing-datagen/ETL-Synthea-Python

python etl.py \
  --synthea-input ~/securecomputing-data/synthea_raw/ \
  --vocabulary ~/securecomputing-data/vocabulary/ \
  --output ~/securecomputing-data/pd0/
```

> 🔄 **NOTE:** The exact command-line interface depends on the ETL tool version. Consult the ETL-Synthea-Python README for current usage. The above is conceptual.

**Expected output in `~/securecomputing-data/pd0/`:**

| File | OMOP Table |
|------|-----------|
| `person.csv` | PERSON |
| `observation_period.csv` | OBSERVATION_PERIOD |
| `visit_occurrence.csv` | VISIT_OCCURRENCE |
| `condition_occurrence.csv` | CONDITION_OCCURRENCE |
| `drug_exposure.csv` | DRUG_EXPOSURE |
| `procedure_occurrence.csv` | PROCEDURE_OCCURRENCE |
| `measurement.csv` | MEASUREMENT |
| `observation.csv` | OBSERVATION |

### 4.4 Verify OMOP Output

```bash
# Check patient count matches
wc -l ~/securecomputing-data/pd0/person.csv
# Should be ~10,001

# Check a few tables have data
wc -l ~/securecomputing-data/pd0/condition_occurrence.csv
wc -l ~/securecomputing-data/pd0/measurement.csv
```

---

## Step 5: Generate PHI Extension

Synthea already generates names and addresses, but we need to:
- Assign MRNs in our project format (`[A-Z]\d{8}`)
- Ensure all 18 HIPAA identifiers are represented
- Create the `phi_mapping.csv` that links OMOP `person_id` to PHI

### 5.1 Run PHI Generator

```bash
cd ~/securecomputing-datagen
python generators/generate_phi.py \
  --person-file ~/securecomputing-data/pd0/person.csv \
  --synthea-patients ~/securecomputing-data/synthea_raw/patients.csv \
  --output ~/securecomputing-data/pd0/phi_mapping.csv
```

**Output:** `phi_mapping.csv` with columns:

| Column | Source | Example |
|--------|--------|---------|
| person_id | OMOP PERSON table | 1001 |
| mrn | Generated (format: [A-Z]\d{8}) | B48291037 |
| full_name | Synthea or Faker | Jane Martinez |
| date_of_birth | Synthea | 1967-04-12 |
| address | Synthea or Faker | 123 Pine St, Seattle WA 98195 |
| phone | Faker | 206-555-0147 |
| ssn | Faker | 539-48-1234 |
| email | Faker | jmartinez@example.com |

> 🔄 **CODE STATUS:** `generators/generate_phi.py` — not yet written.

---

## Step 6: Assign Stone Episodes and Types

This step creates the master assignment file that drives PD1, PD2, and PD3 generation.

### 6.1 Run Stone Assignment

```bash
python generators/assign_stones.py \
  --person-file ~/securecomputing-data/pd0/person.csv \
  --output ~/securecomputing-data/pd0/patient_stones.csv
```

**Distributions applied:**
- Episode count: 20% zero, 40% one, 30% two, 10% three
- Stone type per episode: drawn from mineral composition distribution (see DATA_DESIGN.md)

**Output:** `patient_stones.csv`

| Column | Example |
|--------|---------|
| person_id | 1001 |
| mrn | B48291037 |
| episode_number | 1 |
| stone_type | mixed_com_cod |
| composition | {"whewellite": 0.73, "weddellite": 0.27} |
| episode_date | 2024-01-20 |

Patients with 0 episodes have one row with `episode_number=0` and `stone_type=none`.

> 🔄 **CODE STATUS:** `generators/assign_stones.py` — not yet written.

---

## Step 7: Enrich OMOP with Stone-Related Records

Add kidney stone clinical records to the OMOP tables for patients who have stones.

### 7.1 Run OMOP Enrichment

```bash
python generators/enrich_omop_stones.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --omop-dir ~/securecomputing-data/pd0/ \
  --output-dir ~/securecomputing-data/pd0/
```

**What this adds:**
- `condition_occurrence.csv`: Nephrolithiasis diagnosis (SNOMED 95570007) for stone patients
- `procedure_occurrence.csv`: Stone collection/removal procedures
- `specimen.csv`: Kidney stone specimen records
- `measurement.csv`: Stone composition results (links to PD1 CIF analysis)

> 🔄 **CODE STATUS:** `generators/enrich_omop_stones.py` — not yet written.

---

## Step 8: Write Final PD0 Output

```bash
# Verify all files present
ls ~/securecomputing-data/pd0/

# Generate manifest
python generators/generate_manifest.py \
  --data-dir ~/securecomputing-data/ \
  --output ~/securecomputing-data/manifest.json
```

**PD0 is complete.** The `patient_stones.csv` file now drives PD1, PD2, and PD3 generation.

---

## Steps 9–11: Generate PD1, PD2, PD3

These steps read `patient_stones.csv` and generate the remaining datasets.

### Step 9: Generate PD1 (Kidney Stone CIF Files)

```bash
python generators/generate_pd1.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --output-dir ~/securecomputing-data/pd1/
```

Produces ~13,000 CIF files with PXRD + FTIR data based on mineral composition.

> 🔄 **CODE STATUS:** `generators/generate_pd1.py` — not yet written.

### Step 10: Generate PD2 (Genomics VCF Files)

```bash
python generators/generate_pd2.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --output-dir ~/securecomputing-data/pd2/
```

Produces 10,000 VCF files with variants in stone-associated genes correlated with stone type.

> 🔄 **CODE STATUS:** `generators/generate_pd2.py` — not yet written.

### Step 11: Generate PD3 (Lab Results)

```bash
python generators/generate_pd3.py \
  --stones ~/securecomputing-data/pd0/patient_stones.csv \
  --person-file ~/securecomputing-data/pd0/person.csv \
  --output ~/securecomputing-data/pd3/lab_results.csv
```

Produces longitudinal lab values correlated with stone type.

> 🔄 **CODE STATUS:** `generators/generate_pd3.py` — not yet written.

---

## Step 12: Generate Final Manifest

```bash
python generators/generate_manifest.py \
  --data-dir ~/securecomputing-data/ \
  --output ~/securecomputing-data/manifest.json
```

Produces SHA-256 checksums for all files — used by the upload validation Lambda in the analysis environment.

---

## Full Pipeline (Single Command)

Once all generators are written:

```bash
cd ~/securecomputing-datagen
python run_all.py --output ~/securecomputing-data/
```

This orchestrates Steps 3–12 in sequence. Step 1–2 (Synthea install/config) are one-time setup.

---

## Code Status Summary

| Script | Status | Step |
|--------|--------|------|
| `generators/generate_phi.py` | ❌ Not written | 5 |
| `generators/assign_stones.py` | ❌ Not written | 6 |
| `generators/enrich_omop_stones.py` | ❌ Not written | 7 |
| `generators/generate_pd1.py` | ❌ Not written | 9 |
| `generators/generate_pd2.py` | ❌ Not written | 10 |
| `generators/generate_pd3.py` | ❌ Not written | 11 |
| `generators/generate_manifest.py` | ❌ Not written | 12 |
| `run_all.py` | ❌ Not written | Full pipeline |
