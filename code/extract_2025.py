#!/usr/bin/env python3
"""
Extract 2025 maintenance schedules from PDFs and generate mustoff CSVs.
Reuses the same physical-to-model gen_id mappings from the 2022 work,
with capacity-mismatched generators excluded.
Day 1 = Jan 1, 2025.
"""

import pdfplumber
import csv
import glob
import re
import os
from datetime import datetime, date
from collections import defaultdict

PDF_DIR = os.path.expanduser("~/Downloads/maintain-sch/2025")
OUTPUT_DIR = os.path.expanduser("~/workspace/maintain-sch")
BASE_DATE = date(2025, 1, 1)  # Day 1

# ── Fuel type mapping ──────────────────────────────────────────────────────
FUEL_MAP = {
    '유연탄': 'Coal', '무연탄': 'Coal',
    '유류': 'Oil', '원자력': 'Nuclear',
}

# ── Physical-to-model gen_id mappings (capacity-mismatch excluded) ─────────

COAL_PHYS_TO_GENID = {
    # Bus 40 (영흥)
    '영흥#5': 28, '영흥#6': 29, '영흥#3': 30, '영흥#4': 31,
    '영흥#1': 32, '영흥#2': 32,
    # Bus 53 (당진)
    '당진#9': 42, '당진#10': 43,
    '당진#1': 44, '당진#2': 44,
    '당진#3': 45, '당진#4': 45,
    '당진#5': 46, '당진#6': 46,
    '당진#7': 47, '당진#8': 47,
    # Bus 59 (태안)
    '태안#9': 52, '태안#10': 53,
    '태안#1': 54, '태안#2': 54,
    '태안#3': 55, '태안#4': 55,
    '태안#5': 56, '태안#6': 56,
    '태안#7': 57, '태안#8': 57,
    # Bus 65 (고성): REMOVED - capacity mismatch
    # Bus 68 (삼척그린)
    '삼척그린#1': 60, '삼척그린#2': 61,
    # Bus 71 (북평): 동해 REMOVED - capacity mismatch
    '북평#1': 63, '북평#2': 64,
    # Bus 100 (보령+신보령)
    '신보령#1': 74, '신보령#2': 75,
    '보령#3': 76, '보령#4': 76,
    '보령#5': 77, '보령#6': 77,
    '보령#7': 78, '보령#8': 78,
    # Bus 106 (신서천)
    '신서천#1': 81,
    # Bus 137 (여수)
    '여수#1': 94, '여수#2': 94,
    # Bus 190 (삼천포)
    '삼천포#3': 115, '삼천포#4': 116,
    '삼천포#5': 117, '삼천포#6': 118,
    # Bus 193 (하동)
    '하동#1': 119, '하동#2': 119,
    '하동#3': 120, '하동#4': 120,
    '하동#5': 121, '하동#6': 121,
    '하동#7': 122, '하동#8': 122,
}

NUCLEAR_PHYS_TO_GENID = {
    '한울#1': 72, '한울#3': 68, '한울#5': 70, '한울#6': 71,
    '한빛#1': 87, '한빛#2': 88, '한빛#3': 83, '한빛#4': 85, '한빛#6': 84,
    '월성#2': 100, '월성#3': 101, '신월성#1': 99, '신월성#2': 98,
    '고리#2': 112, '신고리#1': 108, '신고리#2': 109, '신고리#4': 97,
}

LNG_PHYS_TO_GENID = {
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
    # Bus 37 (남인천)
    '신인천GT#1': 24, '신인천GT#2': 24, '신인천ST#1': 24,
    '신인천GT#3': 24, '신인천GT#4': 24, '신인천ST#2': 24,
    '신인천GT#5': 25, '신인천GT#6': 25, '신인천ST#3': 25,
    '신인천GT#7': 25, '신인천GT#8': 25, '신인천ST#4': 25,
    '인천GT#1': 24, '인천GT#2': 24, '인천ST#1': 24,
    '인천GT#3': 25, '인천GT#4': 25, '인천ST#2': 25,
    '인천GT#5': 25, '인천GT#6': 25, '인천ST#3': 25,
    # Bus 26 (부천)
    '부천GT#1': 18, '부천GT#2': 18, '부천GT#3': 18, '부천ST#1': 18,
    # Bus 27 (영종): REMOVED - capacity mismatch (인천공항)
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
    # Bus 53 (당진 LNG)
    'GS당진GT#1': 48, 'GS당진GT#2': 48, 'GS당진ST#1': 48,
    'GS당진GT#3': 48, 'GS당진GT#4': 48, 'GS당진ST#2': 48,
    'GS당진GT#5': 49, 'GS당진GT#6': 49, 'GS당진ST#3': 49,
    'GS당진GT#7': 49, 'GS당진ST#4': 49,
    # Bus 64 (세종)
    '세종GT#1': 58, '세종GT#2': 58, '세종ST#1': 58,
    # Bus 79 (영월)
    '영월GT#1': 66, '영월GT#2': 66, '영월GT#3': 66, '영월ST#1': 66,
    # Bus 100 (보령 LNG)
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
    # Bus 181 (부산)
    '부산GT#1': 113, '부산GT#2': 113, '부산ST#1': 113,
    '부산GT#3': 113, '부산GT#4': 113, '부산ST#2': 113,
    '부산GT#5': 114, '부산GT#6': 114, '부산ST#3': 114,
    '부산GT#7': 114, '부산GT#8': 114, '부산ST#4': 114,
}


# ── PDF extraction ─────────────────────────────────────────────────────────

def parse_datetime(date_str, time_str):
    date_str = date_str.strip()
    time_str = time_str.strip()
    if re.match(r'^\d:', time_str):
        time_str = '0' + time_str
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def extract_table_from_pdf(pdf_path):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row is None or len(row) < 8:
                        continue
                    if row[0] and ('회원사' in str(row[0]) or '시작일' in str(row[0])):
                        continue
                    if row[0] and ('주 간' in str(row[0]) or '대상기간' in str(row[0]) or '수급계획' in str(row[0])):
                        continue
                    try:
                        fuel_type = str(row[1]).strip() if row[1] else None
                        generator = str(row[2]).strip() if row[2] else None
                        capacity_str = str(row[3]).strip().replace(',', '') if row[3] else None
                        start_date = str(row[4]).strip() if row[4] else None
                        start_time = str(row[5]).strip() if row[5] else None
                        end_date = str(row[6]).strip() if row[6] else None
                        end_time = str(row[7]).strip() if row[7] else None

                        if not generator or not start_date or not end_date:
                            continue
                        if not re.match(r'\d{4}-\d{2}-\d{2}', start_date):
                            continue
                        if not re.match(r'\d{4}-\d{2}-\d{2}', end_date):
                            continue

                        capacity = float(capacity_str)
                        start_dt = parse_datetime(start_date, start_time)
                        end_dt = parse_datetime(end_date, end_time)

                        fuel_mapped = FUEL_MAP.get(fuel_type, fuel_type)

                        rows.append({
                            '연료원': fuel_mapped,
                            '발전기명': generator,
                            '설비용량': capacity,
                            '시작일': start_date,
                            '시작시간': start_time,
                            '종료일': end_date,
                            '종료시간': end_time,
                            '_start_dt': start_dt,
                            '_end_dt': end_dt,
                        })
                    except (ValueError, TypeError, IndexError):
                        continue
    return rows


def merge_overlapping_periods(records):
    groups = defaultdict(list)
    for r in records:
        key = (r['연료원'], r['발전기명'], r['설비용량'])
        groups[key].append(r)

    merged = []
    for (fuel, gen, cap), entries in groups.items():
        entries.sort(key=lambda x: x['_start_dt'])
        merged_intervals = []
        for e in entries:
            if merged_intervals and e['_start_dt'] <= merged_intervals[-1]['_end_dt']:
                if e['_end_dt'] > merged_intervals[-1]['_end_dt']:
                    merged_intervals[-1]['_end_dt'] = e['_end_dt']
                    merged_intervals[-1]['종료일'] = e['종료일']
                    merged_intervals[-1]['종료시간'] = e['종료시간']
            else:
                merged_intervals.append(dict(e))
        merged.extend(merged_intervals)
    return merged


# ── Time/day conversion ────────────────────────────────────────────────────

def date_to_day(d):
    """Day 1 = Jan 1, 2025."""
    return (d - BASE_DATE).days + 1


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


# ── Mustoff row generation ─────────────────────────────────────────────────

def make_mustoff_rows(records, fuel_type, phys_to_genid):
    rows = []
    unmapped = set()

    for r in records:
        if r['연료원'] != fuel_type:
            continue

        gen_name = r['발전기명']
        gen_id = phys_to_genid.get(gen_name)
        if gen_id is None:
            unmapped.add(gen_name)
            continue

        start_date = date.fromisoformat(r['시작일'])
        end_date = date.fromisoformat(r['종료일'])

        if start_date < BASE_DATE:
            off_start_day = 1
            off_start_time = 1
        else:
            off_start_day = date_to_day(start_date)
            off_start_time = parse_start_time(r['시작시간'])

        if end_date < BASE_DATE:
            off_end_day = 1
            off_end_time = 1
        else:
            off_end_day = date_to_day(end_date)
            off_end_time = parse_end_time(r['종료시간'])

        # Skip if entire period is before 2025
        if off_end_day < 1:
            continue

        rows.append((gen_id, off_start_day, off_start_time, off_end_day, off_end_time))

    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows, unmapped


def write_mustoff_csv(rows, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'off_start_day', 'off_start_time', 'off_end_day', 'off_end_time'])
        for row in rows:
            writer.writerow(row)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    # Step 1: Extract from PDFs
    pdf_files = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    print(f"Found {len(pdf_files)} PDF files in {PDF_DIR}")

    all_rows = []
    for i, pdf_path in enumerate(pdf_files):
        fname = os.path.basename(pdf_path)
        rows = extract_table_from_pdf(pdf_path)
        print(f"  [{i+1}/{len(pdf_files)}] {fname}: {len(rows)} rows")
        all_rows.extend(rows)

    print(f"\nTotal raw rows: {len(all_rows)}")

    # Deduplicate
    seen = set()
    unique_rows = []
    for r in all_rows:
        key = (r['연료원'], r['발전기명'], r['설비용량'], r['시작일'], r['시작시간'], r['종료일'], r['종료시간'])
        if key not in seen:
            seen.add(key)
            unique_rows.append(r)
    print(f"After dedup: {len(unique_rows)} rows")

    # Merge overlapping periods
    merged = merge_overlapping_periods(unique_rows)
    print(f"After merging: {len(merged)} rows")

    # Save full schedule
    schedule_path = os.path.join(OUTPUT_DIR, "maintenance_schedule_2025.csv")
    with open(schedule_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['연료원', '발전기명', '설비용량', '시작일', '시작시간', '종료일', '종료시간'])
        writer.writeheader()
        sorted_merged = sorted(merged, key=lambda x: (x['발전기명'], x['시작일']))
        for r in sorted_merged:
            writer.writerow({k: r[k] for k in ['연료원', '발전기명', '설비용량', '시작일', '시작시간', '종료일', '종료시간']})
    print(f"\nSaved schedule to: {schedule_path}")

    # Fuel type counts
    fuel_counts = defaultdict(int)
    for r in merged:
        fuel_counts[r['연료원']] += 1
    print(f"Fuel type distribution: {dict(sorted(fuel_counts.items(), key=lambda x: -x[1]))}")

    # Step 2: Generate mustoff CSVs
    mustoff_dir = os.path.join(OUTPUT_DIR, "2025_mustoff")
    os.makedirs(mustoff_dir, exist_ok=True)

    for fuel_type, mapping, filename in [
        ('Coal', COAL_PHYS_TO_GENID, 'coal_mustoff.csv'),
        ('Nuclear', NUCLEAR_PHYS_TO_GENID, 'nuclear_mustoff.csv'),
        ('LNG', LNG_PHYS_TO_GENID, 'lng_mustoff.csv'),
    ]:
        rows, unmapped = make_mustoff_rows(merged, fuel_type, mapping)
        output_path = os.path.join(mustoff_dir, filename)
        write_mustoff_csv(rows, output_path)

        unique_ids = sorted(set(r[0] for r in rows))
        print(f"\n{fuel_type}: {len(rows)} rows, {len(unique_ids)} unique gen_ids")
        print(f"  gen_ids: {unique_ids}")
        print(f"  Saved to: {output_path}")
        if unmapped:
            print(f"  Unmapped ({len(unmapped)}): {sorted(unmapped)}")

    print(f"\nAll mustoff files saved to: {mustoff_dir}/")


if __name__ == "__main__":
    main()
