"""
Step 11: Generate PD3 — Lab Results
=====================================
Reads patient_stones.csv and generates longitudinal lab test results
correlated with stone type. Patients with stones show expected lab
abnormalities; patients without stones have normal values.

Output: single CSV with all patients, all visits, all panels.

Usage:
    python generators/generate_pd3.py \
        --stones ~/securecomputing-data/pd0/patient_stones.csv \
        --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv \
        --output ~/securecomputing-data/pd3/lab_results.csv
"""

import argparse
import csv
import json
import random
import numpy as np
from datetime import date, timedelta
from pathlib import Path


# Lab test definitions: (name, unit, normal_mean, normal_sd, loinc_code)
LAB_TESTS = {
    # Basic Metabolic Panel
    'glucose': ('Glucose', 'mg/dL', 95, 12, '2345-7'),
    'bun': ('BUN', 'mg/dL', 14, 4, '3094-0'),
    'creatinine': ('Creatinine', 'mg/dL', 1.0, 0.2, '2160-0'),
    'sodium': ('Sodium', 'mEq/L', 140, 3, '2951-2'),
    'potassium': ('Potassium', 'mEq/L', 4.2, 0.4, '2823-3'),
    'chloride': ('Chloride', 'mEq/L', 102, 3, '2075-0'),
    'co2': ('CO2', 'mmol/L', 24, 2, '2028-9'),
    'calcium': ('Calcium', 'mg/dL', 9.5, 0.5, '17861-6'),
    # Lipid Panel
    'cholesterol': ('Total Cholesterol', 'mg/dL', 195, 30, '2093-3'),
    'ldl': ('LDL', 'mg/dL', 115, 25, '2089-1'),
    'hdl': ('HDL', 'mg/dL', 55, 12, '2085-9'),
    'triglycerides': ('Triglycerides', 'mg/dL', 130, 40, '2571-8'),
    # CBC
    'wbc': ('WBC', 'cells/uL', 7000, 1500, '6690-2'),
    'rbc': ('RBC', 'M/uL', 4.8, 0.5, '789-8'),
    'hemoglobin': ('Hemoglobin', 'g/dL', 14.0, 1.5, '718-7'),
    'hematocrit': ('Hematocrit', '%', 42, 4, '4544-3'),
    'platelets': ('Platelets', 'K/uL', 250, 50, '777-3'),
    # Liver Function
    'alt': ('ALT', 'U/L', 25, 10, '1742-6'),
    'ast': ('AST', 'U/L', 25, 8, '1920-8'),
    'alp': ('ALP', 'U/L', 70, 20, '6768-6'),
    'bilirubin': ('Bilirubin', 'mg/dL', 0.8, 0.3, '1975-2'),
    'albumin': ('Albumin', 'g/dL', 4.0, 0.4, '1751-7'),
    # Diabetes
    'hba1c': ('HbA1c', '%', 5.4, 0.4, '4548-4'),
    # Stone-specific (urine tests)
    'urine_calcium': ('Urine Calcium 24hr', 'mg/day', 180, 50, '6874-2'),
    'urine_oxalate': ('Urine Oxalate 24hr', 'mg/day', 28, 8, '2701-1'),
    'urine_citrate': ('Urine Citrate 24hr', 'mg/day', 450, 100, '13358-5'),
    'urine_ph': ('Urine pH', '', 6.0, 0.5, '2756-5'),
    'uric_acid': ('Uric Acid', 'mg/dL', 5.5, 1.2, '3084-1'),
    'urine_cystine': ('Urine Cystine 24hr', 'mg/day', 40, 15, '2162-6'),
    'phosphorus': ('Phosphorus', 'mg/dL', 3.5, 0.5, '2777-1'),
    'pth': ('PTH', 'pg/mL', 40, 12, '2731-8'),
}

# Which tests are in each panel
PANELS = {
    'bmp': ['glucose', 'bun', 'creatinine', 'sodium', 'potassium', 'chloride', 'co2', 'calcium'],
    'lipid': ['cholesterol', 'ldl', 'hdl', 'triglycerides'],
    'cbc': ['wbc', 'rbc', 'hemoglobin', 'hematocrit', 'platelets'],
    'liver': ['alt', 'ast', 'alp', 'bilirubin', 'albumin'],
    'hba1c': ['hba1c'],
    'stone_panel': ['urine_calcium', 'urine_oxalate', 'urine_citrate', 'urine_ph',
                    'uric_acid', 'urine_cystine', 'phosphorus', 'pth'],
}

# Stone type → lab abnormalities (shift_mean, shift_sd for affected tests)
STONE_LAB_SHIFTS = {
    'pure_com': {'urine_calcium': (80, 30), 'urine_citrate': (-150, 50), 'calcium': (0.8, 0.3)},
    'mixed_com_cod': {'urine_calcium': (70, 25), 'urine_citrate': (-120, 40), 'calcium': (0.6, 0.3)},
    'pure_cod': {'urine_calcium': (60, 20), 'urine_citrate': (-100, 40)},
    'com_calcium_phosphate': {'urine_calcium': (90, 30), 'phosphorus': (0.8, 0.3), 'pth': (15, 5)},
    'pure_uric_acid': {'uric_acid': (2.5, 0.8), 'urine_ph': (-1.0, 0.3)},
    'uric_acid_com': {'uric_acid': (2.0, 0.7), 'urine_ph': (-0.8, 0.3), 'urine_calcium': (40, 20)},
    'struvite': {'wbc': (3000, 1000), 'urine_ph': (1.2, 0.3)},
    'brushite': {'urine_calcium': (60, 25), 'phosphorus': (0.6, 0.3), 'urine_ph': (0.5, 0.2)},
    'cystine': {'urine_cystine': (200, 60)},
    'mixed_other': {'urine_calcium': (40, 20)},
}


def generate_visit_dates(n_visits, start_year=2020, end_year=2025):
    """Generate random visit dates spread over the observation period."""
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    span = (end - start).days
    dates = sorted([start + timedelta(days=random.randint(0, span)) for _ in range(n_visits)])
    return [d.isoformat() for d in dates]


def generate_lab_value(test_key, stone_types):
    """Generate a single lab value, shifted if patient has relevant stones."""
    test_info = LAB_TESTS[test_key]
    mean = test_info[2]
    sd = test_info[3]

    # Apply shifts for stone patients
    total_shift_mean = 0
    for st in stone_types:
        shifts = STONE_LAB_SHIFTS.get(st, {})
        if test_key in shifts:
            shift_mean, shift_sd = shifts[test_key]
            total_shift_mean += np.random.normal(shift_mean, shift_sd)

    value = np.random.normal(mean + total_shift_mean, sd)

    # Clamp to reasonable ranges (no negative values for most tests)
    if test_key == 'urine_ph':
        value = np.clip(value, 4.0, 9.0)
    elif test_key in ('urine_citrate',):
        value = max(value, 50)  # Can be low but not zero
    else:
        value = max(value, 0.1)

    return round(value, 1)


def main():
    parser = argparse.ArgumentParser(description='Generate PD3 lab results')
    parser.add_argument('--stones', required=True, help='Path to patient_stones.csv')
    parser.add_argument('--phi-mapping', required=True, help='Path to phi_mapping.csv')
    parser.add_argument('--output', required=True, help='Output path for lab_results.csv')
    parser.add_argument('--seed', type=int, default=44, help='Random seed')
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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

    # Load all patient MRNs
    all_patients = []
    with open(args.phi_mapping, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_patients.append({'person_id': row['person_id'], 'mrn': row['mrn']})

    # Generate lab results
    rows_written = 0
    with open(output_path, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow([
            'person_id', 'mrn', 'visit_date', 'panel', 'test_name',
            'test_code', 'value', 'unit', 'loinc_code'
        ])

        for i, patient in enumerate(all_patients):
            mrn = patient['mrn']
            person_id = patient['person_id']
            stone_types = patient_stones.get(mrn, [])

            # Number of lab visits (3-12 per patient)
            n_visits = random.randint(3, 12)
            visit_dates = generate_visit_dates(n_visits)

            for visit_date in visit_dates:
                # Each visit gets 2-4 panels
                n_panels = random.randint(2, 4)
                visit_panels = random.sample(list(PANELS.keys()), min(n_panels, len(PANELS)))

                # Stone patients always get stone_panel on at least one visit
                if stone_types and 'stone_panel' not in visit_panels and random.random() < 0.6:
                    visit_panels.append('stone_panel')

                for panel_name in visit_panels:
                    tests = PANELS[panel_name]
                    for test_key in tests:
                        test_info = LAB_TESTS[test_key]
                        value = generate_lab_value(test_key, stone_types)
                        writer.writerow([
                            person_id, mrn, visit_date, panel_name,
                            test_info[0], test_key, value, test_info[1], test_info[4]
                        ])
                        rows_written += 1

            if (i + 1) % 1000 == 0:
                print(f"  {i + 1} patients processed...")

    print(f"\nPD3 generation complete: {rows_written} lab results → {output_path}")


if __name__ == '__main__':
    main()
