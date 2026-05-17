"""
Step 6: Assign Stone Episodes and Types
========================================
Reads phi_mapping.csv (for patient list) and assigns kidney stone episodes
based on the project's probability distributions:

Episode distribution:
    - 20% of patients: 0 episodes
    - 40% of patients: 1 episode
    - 30% of patients: 2 episodes
    - 10% of patients: 3 episodes

Stone type distribution (per episode):
    - 35% Pure COM (100% whewellite)
    - 25% Mixed COM/COD (60-90% whewellite + 10-40% weddellite)
    - 5%  Pure COD (100% weddellite)
    - 10% COM + calcium phosphate (50-80% whewellite + 20-50% hydroxyapatite)
    - 8%  Pure uric acid (100% uric acid)
    - 4%  Uric acid + COM (40-70% uric acid + 30-60% whewellite)
    - 5%  Struvite (70-100% struvite + 0-30% hydroxyapatite)
    - 3%  Brushite (80-100% brushite + 0-20% hydroxyapatite)
    - 1%  Cystine (100% cystine)
    - 4%  Mixed other

Usage:
    python generators/assign_stones.py \
        --phi-mapping ~/securecomputing-data/pd0/phi_mapping.csv \
        --output ~/securecomputing-data/pd0/patient_stones.csv
"""

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path


# Episode count distribution
EPISODE_DISTRIBUTION = {
    0: 0.20,
    1: 0.40,
    2: 0.30,
    3: 0.10,
}

# Stone type distribution with composition ranges
STONE_TYPES = [
    {
        'name': 'pure_com',
        'frequency': 0.35,
        'composition': lambda: {'whewellite': 1.0},
    },
    {
        'name': 'mixed_com_cod',
        'frequency': 0.25,
        'composition': lambda: _mixed('whewellite', 'weddellite', 0.60, 0.90),
    },
    {
        'name': 'pure_cod',
        'frequency': 0.05,
        'composition': lambda: {'weddellite': 1.0},
    },
    {
        'name': 'com_calcium_phosphate',
        'frequency': 0.10,
        'composition': lambda: _mixed('whewellite', 'hydroxyapatite', 0.50, 0.80),
    },
    {
        'name': 'pure_uric_acid',
        'frequency': 0.08,
        'composition': lambda: {'uric_acid': 1.0},
    },
    {
        'name': 'uric_acid_com',
        'frequency': 0.04,
        'composition': lambda: _mixed('uric_acid', 'whewellite', 0.40, 0.70),
    },
    {
        'name': 'struvite',
        'frequency': 0.05,
        'composition': lambda: _mixed('struvite', 'hydroxyapatite', 0.70, 1.00),
    },
    {
        'name': 'brushite',
        'frequency': 0.03,
        'composition': lambda: _mixed('brushite', 'hydroxyapatite', 0.80, 1.00),
    },
    {
        'name': 'cystine',
        'frequency': 0.01,
        'composition': lambda: {'cystine': 1.0},
    },
    {
        'name': 'mixed_other',
        'frequency': 0.04,
        'composition': lambda: _random_mix(),
    },
]


def _mixed(primary, secondary, primary_min, primary_max):
    """Generate a two-phase composition with primary in [min, max]."""
    primary_pct = round(random.uniform(primary_min, primary_max), 3)
    secondary_pct = round(1.0 - primary_pct, 3)
    return {primary: primary_pct, secondary: secondary_pct}


def _random_mix():
    """Generate a random multi-phase composition for 'mixed other' category."""
    minerals = ['whewellite', 'weddellite', 'hydroxyapatite', 'uric_acid', 'struvite']
    n_phases = random.randint(2, 3)
    selected = random.sample(minerals, n_phases)
    # Generate random proportions that sum to 1
    raw = [random.random() for _ in range(n_phases)]
    total = sum(raw)
    return {mineral: round(val / total, 3) for mineral, val in zip(selected, raw)}


def draw_episode_count():
    """Draw number of stone episodes from the distribution."""
    r = random.random()
    cumulative = 0.0
    for count, prob in EPISODE_DISTRIBUTION.items():
        cumulative += prob
        if r <= cumulative:
            return count
    return 0  # fallback


def draw_stone_type():
    """Draw a stone type from the frequency distribution."""
    r = random.random()
    cumulative = 0.0
    for stone in STONE_TYPES:
        cumulative += stone['frequency']
        if r <= cumulative:
            return stone['name'], stone['composition']()
    # Fallback
    return 'pure_com', {'whewellite': 1.0}


def generate_episode_date(birth_date_str, episode_num):
    """Generate a plausible episode date (adults, spaced apart)."""
    try:
        birth = date.fromisoformat(birth_date_str)
    except (ValueError, TypeError):
        birth = date(1970, 1, 1)

    # Stones typically occur in adults (age 20-80)
    min_age = 20 + (episode_num * 2)  # Space episodes apart
    max_age = min(80, min_age + 20)

    age_days = random.randint(min_age * 365, max_age * 365)
    episode_date = birth + timedelta(days=age_days)

    # Cap at a reasonable "present" date
    cap = date(2025, 12, 31)
    if episode_date > cap:
        episode_date = cap - timedelta(days=random.randint(30, 365 * 5))

    return episode_date.isoformat()


def main():
    parser = argparse.ArgumentParser(description='Assign kidney stone episodes to patients')
    parser.add_argument('--phi-mapping', required=True, help='Path to phi_mapping.csv')
    parser.add_argument('--output', required=True, help='Output path for patient_stones.csv')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    args = parser.parse_args()

    random.seed(args.seed)

    input_path = Path(args.phi_mapping)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read patient list
    patients = []
    with open(input_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            patients.append(row)

    # Assign episodes
    total_episodes = 0
    stone_patients = 0

    with open(output_path, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow([
            'person_id', 'mrn', 'episode_number', 'stone_type',
            'composition', 'episode_date'
        ])

        for patient in patients:
            person_id = patient['person_id']
            mrn = patient['mrn']
            dob = patient['date_of_birth']
            n_episodes = draw_episode_count()

            if n_episodes == 0:
                # Record that this patient has no stones
                writer.writerow([person_id, mrn, 0, 'none', '{}', ''])
            else:
                stone_patients += 1
                for ep in range(1, n_episodes + 1):
                    stone_type, composition = draw_stone_type()
                    ep_date = generate_episode_date(dob, ep)
                    writer.writerow([
                        person_id, mrn, ep, stone_type,
                        json.dumps(composition), ep_date
                    ])
                    total_episodes += 1

    total_patients = len(patients)
    print(f"Stone assignments generated: {total_patients} patients → {output_path}")
    print(f"  Patients with stones: {stone_patients} ({stone_patients/total_patients*100:.1f}%)")
    print(f"  Patients without stones: {total_patients - stone_patients} ({(total_patients-stone_patients)/total_patients*100:.1f}%)")
    print(f"  Total stone episodes: {total_episodes}")
    print(f"  Expected CIF files to generate (PD1): {total_episodes}")


if __name__ == '__main__':
    main()
