#!/usr/bin/env python3
"""
Generate nuclear_mustoff.csv from maintenance_schedule.csv.

Output format: id,off_start_day,off_start_time,off_end_day,off_end_time
- Day 1 = Jan 1, 2022. Days can exceed 365 for dates in 2023+.
- start_time: max(hour, 1)
- end_time: if minutes > 0 then hour+1; else hour if hour > 0 else 24
- Dates before 2022 are clamped to day 1, time 1.
- id is the 1-based gen row index from mpc.gen.
"""

import csv
from datetime import date

# Physical generator name → model gen_id mapping
NAME_TO_GENID = {
    # 한울원전 (bus 82)
    "한울#1": 72,
    "한울#3": 68,
    "한울#5": 70,
    "한울#6": 71,
    # 한빛원전 (bus 124)
    "한빛#1": 87,
    "한빛#2": 88,
    "한빛#3": 83,
    "한빛#4": 85,
    "한빛#6": 84,
    # 월성/신월성 (bus 166)
    "월성#2": 100,
    "월성#3": 101,
    "신월성#1": 99,
    "신월성#2": 98,
    # 고리/신고리 (bus 175)
    "고리#2": 112,
    "신고리#1": 108,
    "신고리#2": 109,
    "신고리#4": 97,
}

BASE_DATE = date(2022, 1, 1)


def date_to_day(d):
    """Convert a date to day number where Jan 1 2022 = day 1."""
    return (d - BASE_DATE).days + 1


def convert_start_time(time_str):
    """start_time: max(hour, 1)"""
    hour = int(time_str.split(":")[0])
    return max(hour, 1)


def convert_end_time(time_str):
    """end_time: if minutes > 0 then hour+1; else hour if hour > 0 else 24"""
    parts = time_str.split(":")
    hour = int(parts[0])
    minutes = int(parts[1])
    if minutes > 0:
        return hour + 1
    else:
        return hour if hour > 0 else 24


def main():
    input_path = "/Users/hslee/workspace/maintain-sch/maintenance_schedule.csv"
    output_path = "/Users/hslee/workspace/maintain-sch/nuclear_mustoff.csv"

    rows = []

    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["연료원"] != "Nuclear":
                continue

            gen_name = row["발전기명"]
            if gen_name not in NAME_TO_GENID:
                print(f"WARNING: Unknown nuclear generator '{gen_name}', skipping.")
                continue

            gen_id = NAME_TO_GENID[gen_name]

            # Parse start date/time
            start_date = date.fromisoformat(row["시작일"])
            start_time_str = row["시작시간"]

            # Parse end date/time
            end_date = date.fromisoformat(row["종료일"])
            end_time_str = row["종료시간"]

            # Convert start
            if start_date < BASE_DATE:
                off_start_day = 1
                off_start_time = 1
            else:
                off_start_day = date_to_day(start_date)
                off_start_time = convert_start_time(start_time_str)

            # Convert end
            if end_date < BASE_DATE:
                off_end_day = 1
                off_end_time = 1
            else:
                off_end_day = date_to_day(end_date)
                off_end_time = convert_end_time(end_time_str)

            rows.append((gen_id, off_start_day, off_start_time, off_end_day, off_end_time))

    # Sort by id, then off_start_day
    rows.sort(key=lambda r: (r[0], r[1]))

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "off_start_day", "off_start_time", "off_end_day", "off_end_time"])
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
