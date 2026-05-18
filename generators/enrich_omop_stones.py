"""
Step 7: Enrich OMOP with Stone-Related Records
================================================
Reads patient_stones.csv and appends kidney stone clinical records
to the existing OMOP tables:

- condition_occurrence.csv: Nephrolithiasis diagnosis (SNOMED 95570007)
- procedure_occurrence.csv: Stone collection/removal + crystallography analysis
- measurement.csv: Stone composition results

Usage:
    python generators/enrich_omop_stones.py \
        --stones ~/securecomputing-data/pd0/patient_stones.csv \
        --omop-dir ~/securecomputing-data/pd0
"""

import argparse
import csv
import json
import pandas as pd
from pathlib import Path


# SNOMED codes for kidney stone conditions
NEPHROLITHIASIS_CODE = '95570007'  # Kidney stone (SNOMED)
CALCIUM_OXALATE_CODE = '36474008'  # Calcium oxalate nephrolithiasis
URIC_ACID_STONE_CODE = '444800001'  # Uric acid nephrolithiasis
CYSTINE_STONE_CODE = '197.2'  # Cystinuria

# Procedure codes
STONE_COLLECTION_CODE = '274025005'  # Removal of calculus of kidney (SNOMED)
CRYSTALLOGRAPHY_CODE = '104177005'  # Analysis of calculus (SNOMED)

# Map stone types to condition codes
STONE_TYPE_TO_CONDITION = {
    'pure_com': CALCIUM_OXALATE_CODE,
    'mixed_com_cod': CALCIUM_OXALATE_CODE,
    'pure_cod': CALCIUM_OXALATE_CODE,
    'com_calcium_phosphate': CALCIUM_OXALATE_CODE,
    'pure_uric_acid': URIC_ACID_STONE_CODE,
    'uric_acid_com': URIC_ACID_STONE_CODE,
    'struvite': NEPHROLITHIASIS_CODE,
    'brushite': NEPHROLITHIASIS_CODE,
    'cystine': CYSTINE_STONE_CODE,
    'mixed_other': NEPHROLITHIASIS_CODE,
}


def main():
    parser = argparse.ArgumentParser(description='Enrich OMOP tables with kidney stone records')
    parser.add_argument('--stones', required=True, help='Path to patient_stones.csv')
    parser.add_argument('--omop-dir', required=True, help='Directory containing OMOP CSV files')
    args = parser.parse_args()

    stones_path = Path(args.stones)
    omop_dir = Path(args.omop_dir)

    # Load existing OMOP tables to get current max IDs
    cond_df = pd.read_csv(omop_dir / 'condition_occurrence.csv')
    proc_df = pd.read_csv(omop_dir / 'procedure_occurrence.csv')
    meas_df = pd.read_csv(omop_dir / 'measurement.csv')

    cond_id = int(cond_df['condition_occurrence_id'].max()) + 1 if not cond_df.empty else 1
    proc_id = int(proc_df['procedure_occurrence_id'].max()) + 1 if not proc_df.empty else 1
    meas_id = int(meas_df['measurement_id'].max()) + 1 if not meas_df.empty else 1

    # Read stone assignments
    new_conditions = []
    new_procedures = []
    new_measurements = []

    with open(stones_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['stone_type'] == 'none':
                continue

            person_id = int(row['person_id'])
            episode_date = row['episode_date']
            stone_type = row['stone_type']
            composition = json.loads(row['composition'])

            # Add condition: nephrolithiasis diagnosis
            condition_code = STONE_TYPE_TO_CONDITION.get(stone_type, NEPHROLITHIASIS_CODE)
            new_conditions.append({
                'condition_occurrence_id': cond_id,
                'person_id': person_id,
                'condition_concept_id': 0,
                'condition_start_date': episode_date,
                'condition_start_datetime': episode_date,
                'condition_end_date': episode_date,
                'condition_type_concept_id': 32020,
                'condition_source_value': condition_code,
                'condition_source_concept_id': 0,
                'visit_occurrence_id': 0,
            })
            cond_id += 1

            # Add procedure: stone collection
            new_procedures.append({
                'procedure_occurrence_id': proc_id,
                'person_id': person_id,
                'procedure_concept_id': 0,
                'procedure_date': episode_date,
                'procedure_datetime': episode_date,
                'procedure_type_concept_id': 38000275,
                'procedure_source_value': STONE_COLLECTION_CODE,
                'procedure_source_concept_id': 0,
                'visit_occurrence_id': 0,
            })
            proc_id += 1

            # Add procedure: crystallography analysis
            new_procedures.append({
                'procedure_occurrence_id': proc_id,
                'person_id': person_id,
                'procedure_concept_id': 0,
                'procedure_date': episode_date,
                'procedure_datetime': episode_date,
                'procedure_type_concept_id': 38000275,
                'procedure_source_value': CRYSTALLOGRAPHY_CODE,
                'procedure_source_concept_id': 0,
                'visit_occurrence_id': 0,
            })
            proc_id += 1

            # Add measurements: composition percentages
            for mineral, pct in composition.items():
                new_measurements.append({
                    'measurement_id': meas_id,
                    'person_id': person_id,
                    'measurement_concept_id': 0,
                    'measurement_date': episode_date,
                    'measurement_datetime': episode_date,
                    'measurement_type_concept_id': 44818702,
                    'value_as_number': round(pct * 100, 1),
                    'value_source_value': f"{mineral}:{round(pct*100, 1)}%",
                    'unit_source_value': '%',
                    'measurement_source_value': f"stone_composition_{mineral}",
                    'measurement_source_concept_id': 0,
                    'visit_occurrence_id': 0,
                })
                meas_id += 1

    # Append to existing OMOP tables
    if new_conditions:
        new_cond_df = pd.DataFrame(new_conditions)
        combined_cond = pd.concat([cond_df, new_cond_df], ignore_index=True)
        combined_cond.to_csv(omop_dir / 'condition_occurrence.csv', index=False)
        print(f"  condition_occurrence: +{len(new_conditions)} stone diagnoses (total: {len(combined_cond)})")

    if new_procedures:
        new_proc_df = pd.DataFrame(new_procedures)
        combined_proc = pd.concat([proc_df, new_proc_df], ignore_index=True)
        combined_proc.to_csv(omop_dir / 'procedure_occurrence.csv', index=False)
        print(f"  procedure_occurrence: +{len(new_procedures)} stone procedures (total: {len(combined_proc)})")

    if new_measurements:
        new_meas_df = pd.DataFrame(new_measurements)
        combined_meas = pd.concat([meas_df, new_meas_df], ignore_index=True)
        combined_meas.to_csv(omop_dir / 'measurement.csv', index=False)
        print(f"  measurement: +{len(new_measurements)} composition results (total: {len(combined_meas)})")

    print(f"\nOMOP enrichment complete.")


if __name__ == '__main__':
    main()
