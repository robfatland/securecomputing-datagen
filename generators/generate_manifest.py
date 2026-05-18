"""
Step 12: Generate Manifest
============================
Produces a manifest.json file with SHA-256 checksums for all generated data files.
This manifest is used by the upload validation Lambda in the analysis environment
to verify data integrity after transfer.

Usage:
    python generators/generate_manifest.py \
        --data-dir ~/securecomputing-data \
        --output ~/securecomputing-data/manifest.json
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime


def sha256_file(filepath):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Generate SHA-256 manifest for all data files')
    parser.add_argument('--data-dir', required=True, help='Root data directory')
    parser.add_argument('--output', required=True, help='Output path for manifest.json')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_path = Path(args.output)

    # Directories to include (skip synthea_raw and vocabulary — those are inputs, not outputs)
    include_dirs = ['pd0', 'pd1', 'pd2', 'pd3']

    manifest = {
        'generated': datetime.now().isoformat(),
        'generator': 'securecomputing-datagen',
        'data_root': str(data_dir),
        'files': [],
        'summary': {},
    }

    total_files = 0
    total_bytes = 0

    for subdir in include_dirs:
        dir_path = data_dir / subdir
        if not dir_path.exists():
            print(f"  WARNING: {subdir}/ not found, skipping")
            continue

        dir_files = 0
        dir_bytes = 0
        print(f"  Scanning {subdir}/...")

        for filepath in sorted(dir_path.rglob('*')):
            if filepath.is_file() and filepath.name != '.gitkeep':
                rel_path = str(filepath.relative_to(data_dir))
                file_size = filepath.stat().st_size
                checksum = sha256_file(filepath)

                manifest['files'].append({
                    'path': rel_path,
                    'size_bytes': file_size,
                    'sha256': checksum,
                })

                dir_files += 1
                dir_bytes += file_size

        manifest['summary'][subdir] = {
            'file_count': dir_files,
            'total_bytes': dir_bytes,
        }
        total_files += dir_files
        total_bytes += dir_bytes
        print(f"    {dir_files} files, {dir_bytes / 1024 / 1024:.1f} MB")

    manifest['summary']['total'] = {
        'file_count': total_files,
        'total_bytes': total_bytes,
        'total_mb': round(total_bytes / 1024 / 1024, 1),
    }

    # Write manifest
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest generated: {total_files} files, {total_bytes / 1024 / 1024:.1f} MB total")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
