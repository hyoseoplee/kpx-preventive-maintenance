import pandas as pd
import re
from datetime import date

REF_DATE = date(2022, 1, 1)  # day 1 = Jan 1, 2022

# Coal gen_ids from mpc.gen: (gen_id, bus_id, Pmax)
MODEL_COAL_GENS = [
    (28, 40, 1100), (29, 40, 1000), (30, 40, 1000), (31, 40, 1000), (32, 40, 900),
    (37, 49, 700), (38, 49, 700),
    (42, 53, 1000), (43, 53, 1000), (44, 53, 1000), (45, 53, 1000), (46, 53, 1000), (47, 53, 900),
    (52, 59, 1100), (53, 59, 1000), (54, 59, 1000), (55, 59, 1000), (56, 59, 1000), (57, 59, 900),
    (59, 65, 200),
    (60, 68, 1200), (61, 68, 1000),
    (63, 71, 800), (64, 71, 800), (65, 71, 730),
    (74, 100, 1100), (75, 100, 1000), (76, 100, 1000), (77, 100, 1000), (78, 100, 900),
    (81, 106, 900),
    (90, 133, 500),
    (94, 137, 700),
    (115, 190, 1200), (116, 190, 1000), (117, 190, 1000), (118, 190, 900),
    (119, 193, 1000), (120, 193, 1000), (121, 193, 1000), (122, 193, 900),
]

# Physical-to-model mapping: physical generators sorted by capacity desc then name,
# assigned to model gens sorted by Pmax desc then gen_id
PHYSICAL_TO_MODEL = {
    # Bus 40 (영흥): 6 physical → 5 model
    40: {
        '영흥#5': 28, '영흥#6': 29, '영흥#3': 30, '영흥#4': 31,
        '영흥#1': 32, '영흥#2': 32,  # #1 and #2 (800MW each) share the smallest model gen
    },
    # Bus 53 (당진): 10 physical → 6 model
    # #9,#10 (1020MW) → largest model gens; #1-#8 (500MW) paired into remaining
    53: {
        '당진#9': 42, '당진#10': 43,
        '당진#1': 44, '당진#2': 44,
        '당진#3': 45, '당진#4': 45,
        '당진#5': 46, '당진#6': 46,
        '당진#7': 47, '당진#8': 47,
    },
    # Bus 59 (태안): 10 physical → 6 model
    59: {
        '태안#9': 52, '태안#10': 53,
        '태안#1': 54, '태안#2': 54,
        '태안#3': 55, '태안#4': 55,
        '태안#5': 56, '태안#6': 56,
        '태안#7': 57, '태안#8': 57,
    },
    # Bus 65 (고성): REMOVED - 고성#2 (1040MW) vs gen59 Pmax=200MW mismatch
    # Bus 68 (삼척그린): 1:1
    68: {'삼척그린#1': 60, '삼척그린#2': 61},
    # Bus 71 (북평): REMOVED 동해#1/#2 (200MW each) vs gen65 Pmax=730MW mismatch
    71: {
        '북평#1': 63, '북평#2': 64,
    },
    # Bus 100 (보령+신보령): 8 physical → 5 model
    100: {
        '신보령#1': 74, '신보령#2': 75,
        '보령#3': 76, '보령#4': 76,
        '보령#5': 77, '보령#6': 77,
        '보령#7': 78, '보령#8': 78,
    },
    # Bus 106 (신서천): 1:1
    106: {'신서천#1': 81},
    # Bus 137 (여수): 2 physical → 1 model
    137: {'여수#1': 94, '여수#2': 94},
    # Bus 190 (삼천포): 4 physical → 4 model
    190: {
        '삼천포#3': 115, '삼천포#4': 116,
        '삼천포#5': 117, '삼천포#6': 118,
    },
    # Bus 193 (하동): 8 physical → 4 model
    193: {
        '하동#1': 119, '하동#2': 119,
        '하동#3': 120, '하동#4': 120,
        '하동#5': 121, '하동#6': 121,
        '하동#7': 122, '하동#8': 122,
    },
}

# Flatten to gen_name → gen_id
PHYS_TO_GEN_ID = {}
for bus, mapping in PHYSICAL_TO_MODEL.items():
    PHYS_TO_GEN_ID.update(mapping)


def date_to_day(date_str):
    """Convert YYYY-MM-DD to day number (day 1 = Jan 1, 2022)."""
    d = date.fromisoformat(date_str)
    return (d - REF_DATE).days + 1


def time_to_hour(time_str, is_start=True):
    """Convert H:MM or HH:MM to hour (1-24 format)."""
    parts = time_str.strip().split(':')
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    if is_start:
        return max(h, 1)
    else:
        if m > 0:
            return h + 1
        return h if h > 0 else 24


def main():
    df = pd.read_csv('/Users/hslee/workspace/maintain-sch/maintenance_schedule.csv')
    coal = df[df['연료원'] == 'Coal'].copy()

    rows = []
    unmapped = set()

    for _, r in coal.iterrows():
        gen_name = r['발전기명']
        gen_id = PHYS_TO_GEN_ID.get(gen_name)
        if gen_id is None:
            unmapped.add(gen_name)
            continue

        start_day = date_to_day(r['시작일'])
        end_day = date_to_day(r['종료일'])
        start_time = time_to_hour(str(r['시작시간']), is_start=True)
        end_time = time_to_hour(str(r['종료시간']), is_start=False)

        # Skip maintenance periods entirely before 2022
        if end_day < 1:
            continue
        # Clamp start to day 1 if before 2022
        if start_day < 1:
            start_day = 1
            start_time = 1

        rows.append({
            'id': gen_id,
            'off_start_day': start_day,
            'off_start_time': start_time,
            'off_end_day': end_day,
            'off_end_time': end_time,
        })

    if unmapped:
        print(f"WARNING: Unmapped generators: {sorted(unmapped)}")

    out = pd.DataFrame(rows)
    out = out.sort_values(['id', 'off_start_day', 'off_start_time']).reset_index(drop=True)

    output_path = '/Users/hslee/workspace/maintain-sch/coal_mustoff.csv'
    out.to_csv(output_path, index=False)
    print(f"Saved to: {output_path}")
    print(f"Total rows: {len(out)}")
    print(f"\nUnique gen_ids: {sorted(out['id'].unique())}")
    print(f"\nPreview:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
