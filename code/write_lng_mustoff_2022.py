#!/usr/bin/env python3
"""
Generate lng_mustoff.csv from maintenance_schedule.csv.

Output format: id,off_start_day,off_start_time,off_end_day,off_end_time
- Day 1 = Jan 1, 2022
- start_time: max(hour, 1)
- end_time: if minutes > 0 then hour+1, else (hour if hour > 0 else 24)
- Dates before 2022 are clamped to day 1, time 1.
"""

import csv
from datetime import date

# ── Physical generator name → model gen_id mapping ──────────────────────────
PHYS_TO_GEN_ID = {
    # Bus 3 (포천)
    '포천천연GT#1': 1, '포천천연GT#2': 1, '포천천연ST#1': 1,
    '포천GT#1': 2, '포천GT#2': 2, '포천ST#1': 2,
    '포천GT#3': 3, '포천GT#4': 3, '포천ST#2': 3,
    # Bus 4 (동두천)
    '동두천GT#1': 4, '동두천GT#2': 4, '동두천ST#1': 4,
    '동두천GT#3': 5, '동두천GT#4': 5, '동두천ST#2': 5,
    # Bus 8 (파주)
    '파주문산GT#1': 7, '파주문산GT#2': 7, '파주문산ST#1': 7,
    '파주문산GT#3': 8, '파주문산GT#4': 8, '파주문산ST#2': 8,
    '파주GT#1': 10, '파주GT#2': 10, '파주ST#1': 10,
    # Bus 10 (고양)
    '일산GT#1': 11, '일산GT#2': 11, '일산GT#3': 11,
    '일산GT#4': 11, '일산GT#5': 11, '일산GT#6': 11, '일산ST#1': 11,
    # Bus 19 (마포용산)
    '서울GT#1': 12, '서울GT#2': 12, '서울ST#1': 12, '서울ST#2': 12,
    # Bus 20 (하남)
    '위례GT#1': 13, '위례ST#1': 13, '하남GT#1': 13, '하남ST#1': 13,
    # Bus 21 (서인천)
    '서인천GT#1': 14, '서인천GT#2': 14, '서인천ST#1': 14,
    '서인천GT#3': 15, '서인천GT#4': 15, '서인천ST#3': 15,
    '서인천GT#5': 16, '서인천GT#6': 16, '서인천ST#5': 16,
    '서인천GT#7': 17, '서인천GT#8': 17, '서인천ST#7': 17,
    '서인천ST#2': 14, '서인천ST#4': 15, '서인천ST#6': 16, '서인천ST#8': 17,
    # Bus 37 (남인천) - 신인천 + 인천
    '신인천GT#1': 24, '신인천GT#2': 24, '신인천ST#1': 24,
    '신인천GT#3': 24, '신인천GT#4': 24, '신인천ST#2': 24,
    '신인천GT#5': 25, '신인천GT#6': 25, '신인천ST#3': 25,
    '신인천GT#7': 25, '신인천GT#8': 25, '신인천ST#4': 25,
    '인천GT#1': 24, '인천GT#2': 24, '인천ST#1': 24,
    '인천GT#3': 25, '인천GT#4': 25, '인천ST#2': 25,
    '인천GT#5': 25, '인천GT#6': 25, '인천ST#3': 25,
    # Bus 26 (부천)
    '부천GT#1': 18, '부천GT#2': 18, '부천GT#3': 18, '부천ST#1': 18,
    # Bus 27 (영종): REMOVED - 인천공항 (127MW total) vs gen19 Pmax=880MW mismatch
    # Bus 36 (성남)
    '분당GT#1': 23, '분당GT#2': 23, '분당GT#3': 23, '분당GT#4': 23,
    '분당GT#5': 23, '분당GT#6': 23, '분당GT#7': 23, '분당GT#8': 23,
    '분당ST#1': 23, '분당ST#2': 23,
    '판교GT#1': 23, '판교ST#1': 23,
    # Bus 39 (안양)
    '안양2-1GT#1': 26, '안양2-1ST#1': 26,
    '안양열병합2-2CC GT': 26, '안양열병합2-2CC ST': 26,
    # Bus 40 (안산)
    '안산GT#1': 33, '안산GT#2': 33, '안산ST#1': 33,
    # Bus 48 (오산)
    '오성GT#1': 34, '오성GT#2': 34, '오성GT#3': 34, '오성ST#1': 34,
    '명품오산GT#1': 35, '명품오산ST#1': 35,
    # Bus 49 (서평택)
    '평택#1': 36, '평택#2': 36, '평택#3': 36, '평택#4': 36,
    '평택GT#5': 39, '평택GT#6': 39, '평택ST#2': 39,
    '신평택GT#1': 41, '신평택GT#2': 41, '신평택ST#1': 41,
    # Bus 53 (당진) LNG
    'GS당진GT#1': 48, 'GS당진GT#2': 48, 'GS당진ST#1': 48,
    'GS당진GT#3': 48, 'GS당진GT#4': 48, 'GS당진ST#2': 48,
    'GS당진GT#5': 49, 'GS당진GT#6': 49, 'GS당진ST#3': 49,
    'GS당진GT#7': 49, 'GS당진ST#4': 49,
    # Bus 64 (세종)
    '세종GT#1': 58, '세종GT#2': 58, '세종ST#1': 58,
    # Bus 79 (영월)
    '영월GT#1': 66, '영월GT#2': 66, '영월GT#3': 66, '영월ST#1': 66,
    # Bus 100 (보령) LNG
    '보령GT#1': 79, '보령GT#2': 79, '보령ST#1': 79,
    '보령GT#3': 79, '보령GT#4': 79, '보령ST#2': 79,
    '보령GT#5': 80, '보령GT#6': 80, '보령ST#3': 80,
    # Bus 108 (군산)
    '군산GT#1': 82, '군산GT#2': 82, '군산ST#1': 82,
    # Bus 128 (광산)
    '수완GT#1': 89, '수완GT#2': 89, '수완ST#1': 89,
    # Bus 134 (광양)
    '광양GT#1': 91, '광양GT#2': 91, '광양ST#1': 91,
    '광양GT#3': 91, '광양GT#4': 91, '광양ST#2': 91,
    '율촌GT#1': 92, '율촌GT#2': 92, '율촌ST#1': 92,
    '율촌GT#3': 93, '율촌GT#4': 93, '율촌ST#2': 93,
    '포스코GT#7': 91, '포스코GT#8': 91, '포스코GT#9': 91, '포스코ST#3': 91,
    '포스코GT#10': 92, '포스코GT#11': 92, '포스코GT#12': 92, '포스코ST#4': 92,
    '포스코GT#13': 92, '포스코GT#14': 92, '포스코ST#5': 92,
    '포스코GT#15': 93, '포스코GT#16': 93, '포스코ST#6': 93,
    '포스코GT#17': 93, '포스코GT#18': 93, '포스코GT#19': 93,
    '포스코ST#7': 93, '포스코ST#8': 93, '포스코ST#9': 93,
    # Bus 156 (대구)
    '대구그린GT#1': 95, '대구그린ST#1': 95,
    # Bus 167 (울산)
    '울산GT#1': 104, '울산GT#2': 104, '울산ST#1': 104,
    '울산GT#3': 104, '울산GT#4': 104, '울산ST#2': 104,
    '울산GT#5': 105, '울산GT#6': 105, '울산ST#3': 105,
    '울산GT#7': 107, '울산GT#8': 107, '울산ST#4': 107,
    '영남파워GT#1': 105, '영남파워ST#1': 105,
    # Bus 181 (진주/부산)
    '부산GT#1': 113, '부산GT#2': 113, '부산ST#1': 113,
    '부산GT#3': 113, '부산GT#4': 113, '부산ST#2': 113,
    '부산GT#5': 114, '부산GT#6': 114, '부산ST#3': 114,
    '부산GT#7': 114, '부산GT#8': 114, '부산ST#4': 114,
}

# ── Reference date ──────────────────────────────────────────────────────────
BASE_DATE = date(2022, 1, 1)  # Day 1


def date_to_day(d: date) -> int:
    """Convert a date to day number (Day 1 = Jan 1, 2022)."""
    return (d - BASE_DATE).days + 1


def parse_start_time(time_str: str) -> int:
    """start_time: max(hour, 1)."""
    hour = int(time_str.split(':')[0])
    return max(hour, 1)


def parse_end_time(time_str: str) -> int:
    """end_time: if minutes > 0 then hour+1, else (hour if hour > 0 else 24)."""
    parts = time_str.split(':')
    hour = int(parts[0])
    minute = int(parts[1])
    if minute > 0:
        return hour + 1
    else:
        return hour if hour > 0 else 24


def main():
    input_path = '/Users/hslee/workspace/maintain-sch/maintenance_schedule.csv'
    output_path = '/Users/hslee/workspace/maintain-sch/lng_mustoff.csv'

    rows = []
    unmapped = set()

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['연료원'] != 'LNG':
                continue

            gen_name = row['발전기명'].strip()
            gen_id = PHYS_TO_GEN_ID.get(gen_name)

            if gen_id is None:
                unmapped.add(gen_name)
                continue

            # Parse start date/time
            start_date = date.fromisoformat(row['시작일'].strip())
            start_time_str = row['시작시간'].strip()
            end_date = date.fromisoformat(row['종료일'].strip())
            end_time_str = row['종료시간'].strip()

            # Clamp dates before 2022 to day 1, time 1
            if start_date < BASE_DATE:
                off_start_day = 1
                off_start_time = 1
            else:
                off_start_day = date_to_day(start_date)
                off_start_time = parse_start_time(start_time_str)

            if end_date < BASE_DATE:
                off_end_day = 1
                off_end_time = 1
            else:
                off_end_day = date_to_day(end_date)
                off_end_time = parse_end_time(end_time_str)

            rows.append((gen_id, off_start_day, off_start_time, off_end_day, off_end_time))

    # Sort by id, then off_start_day, then off_start_time
    rows.sort(key=lambda r: (r[0], r[1], r[2]))

    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'off_start_day', 'off_start_time', 'off_end_day', 'off_end_time'])
        for row in rows:
            writer.writerow(row)

    # Summary
    unique_ids = sorted(set(r[0] for r in rows))
    print(f"Total rows written: {len(rows)}")
    print(f"Unique gen_ids ({len(unique_ids)}): {unique_ids}")

    if unmapped:
        print(f"\nUnmapped LNG generators ({len(unmapped)}):")
        for name in sorted(unmapped):
            print(f"  - {name}")
    else:
        print("\nNo unmapped LNG generators.")

    print(f"\nOutput written to: {output_path}")


if __name__ == '__main__':
    main()
