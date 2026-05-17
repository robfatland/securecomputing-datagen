"""
Step 4: Custom Synthea-to-OMOP ETL
===================================
Converts Synthea CSV files to OMOP CDM v5.4 formatted CSVs.

This is a lightweight, purpose-built ETL that maps Synthea columns directly
to OMOP table structures. It does NOT perform full vocabulary concept_id
mapping (that can be refined later) — it passes through Synthea's SNOMED/LOINC/
RxNorm codes and assigns sequential IDs.

Replaces the abandoned ETL-Synthea-Python tool which is incompatible with
modern pandas and current Synthea column names.

Usage:
    python generators/synthea_to_omop.py \
        --synthea-dir ~/securecomputing-data/synthea_raw \
        --output-dir ~/securecomputing-data/pd0

Output OMOP tables (as CSVs):
    - person.csv
    - observation_period.csv
    - visit_occurrence.csv
    - condition_occurrence.csv
    - drug_exposure.csv
    - procedure_occurrence.csv
    - measurement.csv
    - observation.csv
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


# Gender mapping (Synthea → OMOP concept_id)
GENDER_MAP = {'M': 8507, 'F': 8532}

# Race mapping (Synthea → OMOP concept_id)
RACE_MAP = {
    'white': 8527,
    'black': 8516,
    'asian': 8515,
    'native': 8657,
    'hawaiian': 8557,
    'other': 8522,
}

# Ethnicity mapping
ETHNICITY_MAP = {
    'hispanic': 38003563,
    'nonhispanic': 38003564,
}

# Visit type mapping (Synthea ENCOUNTERCLASS → OMOP concept_id)
VISIT_MAP = {
    'ambulatory': 9202,
    'outpatient': 9202,
    'inpatient': 9201,
    'emergency': 9203,
    'urgentcare': 9203,
    'wellness': 9202,
    'snf': 8717,
    'hospice': 8546,
    'home': 8536,
    'virtual': 9202,
}


def load_synthea(synthea_dir, filename):
    """Load a Synthea CSV, return DataFrame or empty DataFrame if file missing."""
    path = Path(synthea_dir) / filename
    if not path.exists():
        print(f"  WARNING: {filename} not found, skipping")
        return pd.DataFrame()
    print(f"  Loading {filename}...")
    return pd.read_csv(path, low_memory=False)


def convert_persons(patients_df):
    """Convert Synthea patients.csv → OMOP person.csv"""
    person = pd.DataFrame()
    person['person_id'] = range(1, len(patients_df) + 1)
    person['gender_concept_id'] = patients_df['GENDER'].map(GENDER_MAP).fillna(0).astype(int)
    person['year_of_birth'] = pd.to_datetime(patients_df['BIRTHDATE']).dt.year
    person['month_of_birth'] = pd.to_datetime(patients_df['BIRTHDATE']).dt.month
    person['day_of_birth'] = pd.to_datetime(patients_df['BIRTHDATE']).dt.day
    person['birth_datetime'] = patients_df['BIRTHDATE']
    person['death_datetime'] = patients_df['DEATHDATE']
    person['race_concept_id'] = patients_df['RACE'].map(RACE_MAP).fillna(0).astype(int)
    person['ethnicity_concept_id'] = patients_df['ETHNICITY'].map(ETHNICITY_MAP).fillna(0).astype(int)
    person['location_id'] = person['person_id']  # 1:1 with person for simplicity
    person['provider_id'] = 0
    person['care_site_id'] = 0
    person['person_source_value'] = patients_df['Id'].values
    person['gender_source_value'] = patients_df['GENDER'].values
    person['race_source_value'] = patients_df['RACE'].values
    person['ethnicity_source_value'] = patients_df['ETHNICITY'].values
    return person


def build_patient_map(patients_df):
    """Create mapping from Synthea patient ID → OMOP person_id."""
    return dict(zip(patients_df['Id'], range(1, len(patients_df) + 1)))


def convert_observation_periods(patients_df, patient_map, encounters_df):
    """Convert to OMOP observation_period.csv based on encounter date ranges."""
    obs_periods = []
    
    if encounters_df.empty:
        # Fallback: use birthdate to today
        for _, row in patients_df.iterrows():
            person_id = patient_map.get(row['Id'], 0)
            obs_periods.append({
                'observation_period_id': person_id,
                'person_id': person_id,
                'observation_period_start_date': row['BIRTHDATE'],
                'observation_period_end_date': row.get('DEATHDATE', '2025-12-31') or '2025-12-31',
                'period_type_concept_id': 44814724,
            })
    else:
        # Group encounters by patient, get min/max dates
        enc_grouped = encounters_df.groupby('PATIENT').agg(
            start=('START', 'min'),
            end=('STOP', 'max')
        ).reset_index()
        
        for _, row in enc_grouped.iterrows():
            person_id = patient_map.get(row['PATIENT'], 0)
            if person_id == 0:
                continue
            obs_periods.append({
                'observation_period_id': person_id,
                'person_id': person_id,
                'observation_period_start_date': str(row['start'])[:10],
                'observation_period_end_date': str(row['end'])[:10],
                'period_type_concept_id': 44814724,
            })
    
    return pd.DataFrame(obs_periods)


def convert_visits(encounters_df, patient_map):
    """Convert Synthea encounters.csv → OMOP visit_occurrence.csv"""
    if encounters_df.empty:
        return pd.DataFrame(), {}
    
    visit = pd.DataFrame()
    visit['visit_occurrence_id'] = range(1, len(encounters_df) + 1)
    visit['person_id'] = encounters_df['PATIENT'].map(patient_map).fillna(0).astype(int)
    visit['visit_concept_id'] = encounters_df['ENCOUNTERCLASS'].map(VISIT_MAP).fillna(9202).astype(int)
    visit['visit_start_date'] = encounters_df['START'].str[:10]
    visit['visit_start_datetime'] = encounters_df['START']
    visit['visit_end_date'] = encounters_df['STOP'].str[:10]
    visit['visit_end_datetime'] = encounters_df['STOP']
    visit['visit_type_concept_id'] = 44818517  # EHR
    visit['provider_id'] = 0
    visit['care_site_id'] = 0
    visit['visit_source_value'] = encounters_df['ENCOUNTERCLASS'].values
    visit['visit_source_concept_id'] = 0
    
    # Filter out unmapped persons
    visit = visit[visit['person_id'] > 0]
    
    # Build encounter → visit_occurrence_id map
    encounter_map = dict(zip(encounters_df['Id'], range(1, len(encounters_df) + 1)))
    
    return visit, encounter_map


def convert_conditions(conditions_df, patient_map, encounter_map):
    """Convert Synthea conditions.csv → OMOP condition_occurrence.csv"""
    if conditions_df.empty:
        return pd.DataFrame()
    
    cond = pd.DataFrame()
    cond['condition_occurrence_id'] = range(1, len(conditions_df) + 1)
    cond['person_id'] = conditions_df['PATIENT'].map(patient_map).fillna(0).astype(int)
    cond['condition_concept_id'] = 0  # Would need vocabulary lookup for proper mapping
    cond['condition_start_date'] = conditions_df['START'].str[:10]
    cond['condition_start_datetime'] = conditions_df['START']
    cond['condition_end_date'] = conditions_df['STOP'].str[:10] if 'STOP' in conditions_df.columns else ''
    cond['condition_type_concept_id'] = 32020  # EHR encounter diagnosis
    cond['condition_source_value'] = conditions_df['CODE'].values
    cond['condition_source_concept_id'] = 0
    cond['visit_occurrence_id'] = conditions_df['ENCOUNTER'].map(encounter_map).fillna(0).astype(int)
    
    return cond[cond['person_id'] > 0]


def convert_medications(medications_df, patient_map, encounter_map):
    """Convert Synthea medications.csv → OMOP drug_exposure.csv"""
    if medications_df.empty:
        return pd.DataFrame()
    
    drug = pd.DataFrame()
    drug['drug_exposure_id'] = range(1, len(medications_df) + 1)
    drug['person_id'] = medications_df['PATIENT'].map(patient_map).fillna(0).astype(int)
    drug['drug_concept_id'] = 0  # Would need RxNorm vocabulary lookup
    drug['drug_exposure_start_date'] = medications_df['START'].str[:10]
    drug['drug_exposure_start_datetime'] = medications_df['START']
    drug['drug_exposure_end_date'] = medications_df['STOP'].str[:10] if 'STOP' in medications_df.columns else ''
    drug['drug_type_concept_id'] = 38000177  # Prescription written
    drug['drug_source_value'] = medications_df['CODE'].values
    drug['drug_source_concept_id'] = 0
    drug['visit_occurrence_id'] = medications_df['ENCOUNTER'].map(encounter_map).fillna(0).astype(int)
    
    return drug[drug['person_id'] > 0]


def convert_procedures(procedures_df, patient_map, encounter_map):
    """Convert Synthea procedures.csv → OMOP procedure_occurrence.csv"""
    if procedures_df.empty:
        return pd.DataFrame()
    
    proc = pd.DataFrame()
    proc['procedure_occurrence_id'] = range(1, len(procedures_df) + 1)
    proc['person_id'] = procedures_df['PATIENT'].map(patient_map).fillna(0).astype(int)
    proc['procedure_concept_id'] = 0  # Would need SNOMED vocabulary lookup
    proc['procedure_date'] = procedures_df['START'].str[:10]
    proc['procedure_datetime'] = procedures_df['START']
    proc['procedure_type_concept_id'] = 38000275  # EHR order list entry
    proc['procedure_source_value'] = procedures_df['CODE'].values
    proc['procedure_source_concept_id'] = 0
    proc['visit_occurrence_id'] = procedures_df['ENCOUNTER'].map(encounter_map).fillna(0).astype(int)
    
    return proc[proc['person_id'] > 0]


def convert_observations(observations_df, patient_map, encounter_map):
    """Convert Synthea observations.csv → OMOP measurement.csv + observation.csv
    
    Splits based on category: vital-signs and laboratory → measurement; others → observation.
    """
    if observations_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Split into measurements (labs, vitals) and observations (other)
    meas_categories = ['vital-signs', 'laboratory']
    is_measurement = observations_df['CATEGORY'].isin(meas_categories)
    
    meas_df = observations_df[is_measurement].copy()
    obs_df = observations_df[~is_measurement].copy()
    
    # Convert measurements
    measurement = pd.DataFrame()
    if not meas_df.empty:
        measurement['measurement_id'] = range(1, len(meas_df) + 1)
        measurement['person_id'] = meas_df['PATIENT'].map(patient_map).fillna(0).astype(int)
        measurement['measurement_concept_id'] = 0  # Would need LOINC vocabulary lookup
        measurement['measurement_date'] = meas_df['DATE'].str[:10]
        measurement['measurement_datetime'] = meas_df['DATE']
        measurement['measurement_type_concept_id'] = 44818702  # Lab result
        measurement['value_as_number'] = pd.to_numeric(meas_df['VALUE'], errors='coerce')
        measurement['value_source_value'] = meas_df['VALUE'].values
        measurement['unit_source_value'] = meas_df['UNITS'].values
        measurement['measurement_source_value'] = meas_df['CODE'].values
        measurement['measurement_source_concept_id'] = 0
        measurement['visit_occurrence_id'] = meas_df['ENCOUNTER'].map(encounter_map).fillna(0).astype(int)
        measurement = measurement[measurement['person_id'] > 0]
    
    # Convert observations
    observation = pd.DataFrame()
    if not obs_df.empty:
        observation['observation_id'] = range(1, len(obs_df) + 1)
        observation['person_id'] = obs_df['PATIENT'].map(patient_map).fillna(0).astype(int)
        observation['observation_concept_id'] = 0
        observation['observation_date'] = obs_df['DATE'].str[:10]
        observation['observation_datetime'] = obs_df['DATE']
        observation['observation_type_concept_id'] = 38000280  # Observation recorded from EHR
        observation['value_as_string'] = obs_df['VALUE'].values
        observation['observation_source_value'] = obs_df['CODE'].values
        observation['visit_occurrence_id'] = obs_df['ENCOUNTER'].map(encounter_map).fillna(0).astype(int)
        observation = observation[observation['person_id'] > 0]
    
    return measurement, observation


def main():
    parser = argparse.ArgumentParser(description='Convert Synthea CSVs to OMOP CDM v5.4 CSVs')
    parser.add_argument('--synthea-dir', required=True, help='Directory containing Synthea CSV files')
    parser.add_argument('--output-dir', required=True, help='Output directory for OMOP CSV files')
    args = parser.parse_args()

    synthea_dir = Path(args.synthea_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Synthea input: {synthea_dir}")
    print(f"OMOP output:   {output_dir}")
    print()

    # Load Synthea data
    print("Loading Synthea CSVs...")
    patients = load_synthea(synthea_dir, 'patients.csv')
    encounters = load_synthea(synthea_dir, 'encounters.csv')
    conditions = load_synthea(synthea_dir, 'conditions.csv')
    medications = load_synthea(synthea_dir, 'medications.csv')
    procedures = load_synthea(synthea_dir, 'procedures.csv')
    observations = load_synthea(synthea_dir, 'observations.csv')

    if patients.empty:
        print("ERROR: patients.csv is required")
        return

    # Build mappings
    print("\nBuilding patient mapping...")
    patient_map = build_patient_map(patients)
    print(f"  {len(patient_map)} patients mapped")

    # Convert tables
    print("\nConverting to OMOP...")
    
    print("  → person")
    person = convert_persons(patients)
    
    print("  → observation_period")
    obs_period = convert_observation_periods(patients, patient_map, encounters)
    
    print("  → visit_occurrence")
    visit, encounter_map = convert_visits(encounters, patient_map)
    print(f"    {len(encounter_map)} encounters mapped")
    
    print("  → condition_occurrence")
    condition = convert_conditions(conditions, patient_map, encounter_map)
    
    print("  → drug_exposure")
    drug = convert_medications(medications, patient_map, encounter_map)
    
    print("  → procedure_occurrence")
    procedure = convert_procedures(procedures, patient_map, encounter_map)
    
    print("  → measurement + observation")
    measurement, observation = convert_observations(observations, patient_map, encounter_map)

    # Write output
    print("\nWriting OMOP CSVs...")
    tables = {
        'person': person,
        'observation_period': obs_period,
        'visit_occurrence': visit,
        'condition_occurrence': condition,
        'drug_exposure': drug,
        'procedure_occurrence': procedure,
        'measurement': measurement,
        'observation': observation,
    }

    for name, df in tables.items():
        outpath = output_dir / f"{name}.csv"
        df.to_csv(outpath, index=False)
        print(f"  {name}.csv: {len(df)} rows")

    print(f"\nDone. OMOP files written to {output_dir}")
    print(f"\nNote: concept_id columns are set to 0 (source codes preserved in")
    print(f"*_source_value columns). Full vocabulary mapping is a refinement step.")


if __name__ == '__main__':
    main()
