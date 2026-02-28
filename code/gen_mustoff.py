#!/usr/bin/env python3
"""
Generate mustoff CSV files from maintenance schedule.

Usage:
    python gen_mustoff.py <year>
    python gen_mustoff.py 2022
    python gen_mustoff.py 2025

Input:  results/{year}/maintenance_schedule.csv
Output: results/{year}/mustoff/coal_mustoff.csv
        results/{year}/mustoff/lng_mustoff.csv
        results/{year}/mustoff/nuclear_mustoff.csv

Format: id,off_start_day,off_start_time,off_end_day,off_end_time
  - Day 1 = Jan 1 of the given year
  - start_time: max(hour, 1)
  - end_time: if minutes > 0 then hour+1, else (hour if hour > 0 else 24)
"""

import sys
import os
import csv
from datetime import date

# Add code/ to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mappings import FUEL_MAPPINGS

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_start_time(time_str):
    hour = int(time_str.strip().split(':')[0])
    return max(hour, 1)


def parse_end_time(time_str):
    parts = time_str.strip().split(':')
    hour = int(parts[0])
    minute = int(parts[1])
    if minute > 0:
        return hour + 1
    return hour if hour > 0 else 24


def generate_mustoff(year, fuel_type, mapping, records):
    base_date = date(int(year), 1, 1)
    rows = []
    unmapped = set()

    for r in records:
        if r['연료원'] != fuel_type:
            continue

        gen_name = r['발전기명'].strip()
        gen_id = mapping.get(gen_name)
        if gen_id is None:
            unmapped.add(gen_name)
            continue

        start_d = date.fromisoformat(r['시작일'].strip())
        end_d = date.fromisoformat(r['종료일'].strip())

        # Skip if entire period ends before the target year
        if end_d < base_date:
            continue

        # Convert to day numbers (clamp start to day 1 if before target year)
        if start_d < base_date:
            off_start_day = 1
            off_start_time = 1
        else:
            off_start_day = (start_d - base_date).days + 1
            off_start_time = parse_start_time(r['시작시간'])

        off_end_day = (end_d - base_date).days + 1
        off_end_time = parse_end_time(r['종료시간'])

        rows.append((gen_id, off_start_day, off_start_time, off_end_day, off_end_time))

    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows, unmapped


def write_csv(rows, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'off_start_day', 'off_start_time', 'off_end_day', 'off_end_time'])
        for row in rows:
            writer.writerow(row)


def main():
    if len(sys.argv) < 2:
        print("Usage: python gen_mustoff.py <year>")
        print("Example: python gen_mustoff.py 2022")
        sys.exit(1)

    year = sys.argv[1]
    input_path = os.path.join(REPO_ROOT, 'results', year, 'maintenance_schedule.csv')
    output_dir = os.path.join(REPO_ROOT, 'results', year, 'mustoff')
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isfile(input_path):
        print(f"Error: Input file not found: {input_path}")
        print(f"Run 'python parse_pdf.py {year}' first.")
        sys.exit(1)

    # Read maintenance schedule
    records = []
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    print(f"Loaded {len(records)} records from {input_path}")

    # Generate mustoff for each fuel type
    for fuel_type, mapping in FUEL_MAPPINGS.items():
        filename = f"{fuel_type.lower()}_mustoff.csv"
        output_path = os.path.join(output_dir, filename)

        rows, unmapped = generate_mustoff(year, fuel_type, mapping, records)
        write_csv(rows, output_path)

        unique_ids = sorted(set(r[0] for r in rows)) if rows else []
        print(f"\n{fuel_type}: {len(rows)} rows, {len(unique_ids)} unique gen_ids")
        print(f"  gen_ids: {unique_ids}")
        print(f"  Saved to: {output_path}")
        if unmapped:
            print(f"  Unmapped ({len(unmapped)}): {sorted(unmapped)}")

    print(f"\nAll mustoff files saved to: {output_dir}/")


if __name__ == '__main__':
    main()
