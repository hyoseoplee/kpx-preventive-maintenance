import pdfplumber
import pandas as pd
import glob
import re
import os
from datetime import datetime

PDF_DIR = os.path.expanduser("~/Downloads/maintain-sch")

def parse_datetime(date_str, time_str):
    """Parse date and time strings into a datetime object."""
    date_str = date_str.strip()
    time_str = time_str.strip()
    # Handle times like "0:00" -> "00:00"
    if re.match(r'^\d:', time_str):
        time_str = '0' + time_str
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def extract_table_from_pdf(pdf_path):
    """Extract maintenance schedule rows from a single PDF."""
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row is None or len(row) < 8:
                        continue
                    # Skip header rows
                    if row[0] and ('회원사' in str(row[0]) or '시작일' in str(row[0])):
                        continue
                    # Skip rows that look like title/metadata
                    if row[0] and ('주 간' in str(row[0]) or '대상기간' in str(row[0]) or '수급계획' in str(row[0])):
                        continue

                    try:
                        # Columns: 회원사, 연료원, 발전기명, 설비용량, 시작일, 시작시간, 종료일, 종료시간, 일수, [비고]
                        fuel_type = str(row[1]).strip() if row[1] else None
                        generator = str(row[2]).strip() if row[2] else None
                        capacity_str = str(row[3]).strip().replace(',', '') if row[3] else None
                        start_date = str(row[4]).strip() if row[4] else None
                        start_time = str(row[5]).strip() if row[5] else None
                        end_date = str(row[6]).strip() if row[6] else None
                        end_time = str(row[7]).strip() if row[7] else None

                        if not generator or not start_date or not end_date:
                            continue

                        # Validate date format
                        if not re.match(r'\d{4}-\d{2}-\d{2}', start_date):
                            continue
                        if not re.match(r'\d{4}-\d{2}-\d{2}', end_date):
                            continue

                        capacity = float(capacity_str)
                        start_dt = parse_datetime(start_date, start_time)
                        end_dt = parse_datetime(end_date, end_time)

                        # Map fuel types
                        fuel_map = {
                            '유연탄': 'Coal',
                            '무연탄': 'Coal',
                            '유류': 'Oil',
                            '원자력': 'Nuclear',
                        }
                        fuel_mapped = fuel_map.get(fuel_type, fuel_type)

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
    """
    For each generator, merge periods that overlap.
    Two periods overlap if one starts before the other ends.
    """
    # Group by (연료원, 발전기명, 설비용량)
    from collections import defaultdict
    groups = defaultdict(list)
    for r in records:
        key = (r['연료원'], r['발전기명'], r['설비용량'])
        groups[key].append(r)

    merged = []
    for (fuel, gen, cap), entries in groups.items():
        # Sort by start datetime
        entries.sort(key=lambda x: x['_start_dt'])

        # Merge overlapping intervals
        merged_intervals = []
        for e in entries:
            if merged_intervals and e['_start_dt'] <= merged_intervals[-1]['_end_dt']:
                # Overlapping or contiguous — extend end if needed
                if e['_end_dt'] > merged_intervals[-1]['_end_dt']:
                    merged_intervals[-1]['_end_dt'] = e['_end_dt']
                    merged_intervals[-1]['종료일'] = e['종료일']
                    merged_intervals[-1]['종료시간'] = e['종료시간']
            else:
                merged_intervals.append(dict(e))

        merged.extend(merged_intervals)

    return merged


def main():
    pdf_files = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    print(f"Found {len(pdf_files)} PDF files")

    all_rows = []
    for i, pdf_path in enumerate(pdf_files):
        fname = os.path.basename(pdf_path)
        rows = extract_table_from_pdf(pdf_path)
        print(f"  [{i+1}/{len(pdf_files)}] {fname}: {len(rows)} rows")
        all_rows.extend(rows)

    print(f"\nTotal raw rows: {len(all_rows)}")

    # Deduplicate exact same records before merging
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
    print(f"After merging overlapping periods: {len(merged)} rows")

    # Create output DataFrame
    df = pd.DataFrame(merged)[['연료원', '발전기명', '설비용량', '시작일', '시작시간', '종료일', '종료시간']]
    df = df.sort_values(['발전기명', '시작일', '시작시간']).reset_index(drop=True)

    # Add bus_id for Coal generators based on mpc.gen Coal bus mapping
    coal_gen_to_bus = {
        '당진': 53,
        '태안': 59,
        '보령': 100,
        '신보령': 100,
        '신서천': 106,
        '여수': 137,
        '삼천포': 190,
        '영흥': 40,
        '하동': 193,
        '고성': 65,
        '동해': 71,
        '북평': 71,
        '삼척그린': 68,
    }

    def get_bus_id(row):
        if row['연료원'] != 'Coal':
            return None
        base_name = re.sub(r'#\d+$', '', row['발전기명'])
        return coal_gen_to_bus.get(base_name)

    df['bus_id'] = df.apply(get_bus_id, axis=1)

    # Save to CSV
    output_path = os.path.join(os.path.expanduser("~/workspace/maintain-sch"), "maintenance_schedule.csv")
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\nSaved to: {output_path}")
    print(f"Final row count: {len(df)}")
    print(f"\nCoal rows with bus_id:")
    coal_df = df[df['연료원']=='Coal']
    print(coal_df[['발전기명', '설비용량', 'bus_id', '시작일', '종료일']].drop_duplicates('발전기명').to_string(index=False))


if __name__ == "__main__":
    main()
