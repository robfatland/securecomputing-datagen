"""
Step 5: Generate PHI Mapping
============================
Reads Synthea patients.csv and produces phi_mapping.csv with:
- person_id (sequential integer for OMOP)
- mrn (project format: [A-Z] followed by 8 digits)
- full_name (from Synthea)
- date_of_birth (from Synthea)
- address, city, state, zip (from Synthea)
- phone (generated)
- ssn (from Synthea)
- email (generated)

Usage:
    python generators/generate_phi.py \
        --synthea-patients ~/securecomputing-data/synthea_raw/patients.csv \
        --output ~/securecomputing-data/pd0/phi_mapping.csv
"""

import argparse
import csv
import random
import string
from pathlib import Path


def generate_mrn():
    """Generate MRN in project format: one uppercase letter + 8 digits."""
    letter = random.choice(string.ascii_uppercase)
    digits = ''.join(random.choices(string.digits, k=8))
    return f"{letter}{digits}"


def generate_phone():
    """Generate a realistic US phone number (206/253/360/425 area codes for WA)."""
    area = random.choice(['206', '253', '360', '425', '509'])
    prefix = f"{random.randint(200, 999)}"
    line = f"{random.randint(1000, 9999)}"
    return f"{area}-{prefix}-{line}"


def generate_email(first, last):
    """Generate a plausible email from name."""
    domains = ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com', 'comcast.net', 'uw.edu']
    separators = ['.', '_', '']
    sep = random.choice(separators)
    domain = random.choice(domains)
    # Variations: first.last, firstlast, first_last, f.last, first.l
    patterns = [
        f"{first.lower()}{sep}{last.lower()}",
        f"{first[0].lower()}{sep}{last.lower()}",
        f"{first.lower()}{sep}{last[0].lower()}",
        f"{first.lower()}{random.randint(1, 99)}",
    ]
    username = random.choice(patterns)
    return f"{username}@{domain}"


def main():
    parser = argparse.ArgumentParser(description='Generate PHI mapping from Synthea patients')
    parser.add_argument('--synthea-patients', required=True, help='Path to Synthea patients.csv')
    parser.add_argument('--output', required=True, help='Output path for phi_mapping.csv')
    args = parser.parse_args()

    input_path = Path(args.synthea_patients)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Track MRNs to ensure uniqueness
    used_mrns = set()

    rows_written = 0
    with open(input_path, 'r') as infile, open(output_path, 'w', newline='') as outfile:
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)
        writer.writerow([
            'person_id', 'synthea_id', 'mrn', 'full_name', 'date_of_birth',
            'address', 'city', 'state', 'zip', 'phone', 'ssn', 'email'
        ])

        for person_id, row in enumerate(reader, start=1):
            # Generate unique MRN
            mrn = generate_mrn()
            while mrn in used_mrns:
                mrn = generate_mrn()
            used_mrns.add(mrn)

            # Extract name from Synthea
            first = row.get('FIRST', 'Unknown')
            last = row.get('LAST', 'Unknown')
            prefix = row.get('PREFIX', '').strip()
            full_name = f"{prefix} {first} {last}".strip() if prefix else f"{first} {last}"

            # Extract other fields from Synthea
            dob = row.get('BIRTHDATE', '')
            address = row.get('ADDRESS', '')
            city = row.get('CITY', '')
            state = row.get('STATE', '')
            zip_code = row.get('ZIP', '')
            ssn = row.get('SSN', '')

            # Generate additional PHI
            phone = generate_phone()
            email = generate_email(first, last)

            writer.writerow([
                person_id, row.get('Id', ''), mrn, full_name, dob,
                address, city, state, zip_code, phone, ssn, email
            ])
            rows_written += 1

    print(f"PHI mapping generated: {rows_written} patients → {output_path}")
    print(f"MRN format: [A-Z]\\d{{8}} (e.g., {list(used_mrns)[0]})")


if __name__ == '__main__':
    main()
