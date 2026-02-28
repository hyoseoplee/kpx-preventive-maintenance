# KPX 발전기 예방정비 데이터 처리 매뉴얼

## 1. 개요

KPX(한국전력거래소)에서 매주 발행하는 **발전기별 예방정비계획 PDF**를 파싱하여,
KPG193 전력계통 모델에서 사용하는 **mustoff CSV 파일**을 생성하는 파이프라인입니다.

### 처리 흐름

```
PDF 파일 (주간 정비계획)
    │
    ▼
[parse_pdf.py]  ──▶  maintenance_schedule.csv
    │                     (중간 결과)
    │
    ▼
[gen_mustoff.py] ──▶  coal_mustoff.csv
                      lng_mustoff.csv
                      nuclear_mustoff.csv
```

## 2. 환경 설정

### 필수 패키지

```bash
pip install pdfplumber openpyxl
```

- **pdfplumber**: PDF 테이블 추출
- **openpyxl**: Excel 마스터 데이터 읽기

### 디렉토리 구조

```
kpx-preventive-maintenance/
├── data/
│   ├── HOME_발전설비_발전기별_발전기현황-*.xlsx   # 발전기 마스터
│   └── kpx-data/
│       ├── 2022/   # 2021년 12월 5주차 포함
│       └── 2025/   # 2024년 12월 4주차 포함
├── code/
│   ├── parse_pdf.py      # Step 1: PDF → CSV
│   ├── gen_mustoff.py    # Step 2: CSV → mustoff
│   └── mappings.py       # 물리발전기 → gen_id 매핑
├── docs/
│   └── manual.md         # 본 매뉴얼
└── results/
    └── {year}/
        ├── maintenance_schedule.csv
        └── mustoff/
            ├── coal_mustoff.csv
            ├── lng_mustoff.csv
            └── nuclear_mustoff.csv
```

## 3. 입력 데이터

### 3.1 PDF 파일 (주간 정비계획)

- **출처**: KPX 주간 수급계획 내 발전기별 예방정비계획
- **파일명 형식**: `{year}년 {month}월 {week}주차 발전기별 예방정비계획.pdf`
- **배치 위치**: `data/kpx-data/{year}/`
- **PDF 테이블 컬럼**: 회원사, 연료원, 발전기명, 설비용량(MW), 시작일, 시작시간, 종료일, 종료시간

#### 연도 간 이어지는 정비 처리

전년도 말 PDF에 해당 연도까지 이어지는 정비가 포함될 수 있습니다.
이 경우 해당 PDF를 대상 연도 폴더에 함께 배치합니다.

| 대상 연도 | 추가 PDF | 설명 |
|-----------|---------|------|
| 2022 | 2021년 12월 5주차 | 2021→2022 이어지는 정비 포함 |
| 2025 | 2024년 12월 4주차 | 2024→2025 이어지는 정비 포함 |

### 3.2 발전기 마스터 데이터 (Excel)

- **파일**: `data/HOME_발전설비_발전기별_발전기현황-{date}.xlsx`
- **출처**: 전력거래소 전력통계정보시스템 (EPSIS)
- **주요 컬럼**: 회사명, 발전기명, 설비용량, 발전원, 광역지역, 세부지역
- **용도**: PDF 발전기명과 매칭하여 위치 정보(광역지역, 세부지역) 부여

### 3.3 발전기 매핑 (mappings.py)

물리 발전기명을 KPG193 모델의 gen_id로 매핑합니다.

- **gen_id**: `mpc.gen` (KPG193_ver1_5.m)의 1-based 행 인덱스
- Coal: 36개 물리발전기 → 36 gen_ids (10개 bus)
- Nuclear: 17개 물리발전기 → 12 gen_ids (4개 bus)
- LNG: 87+개 물리발전기 → 43 gen_ids (CC 블록 단위)

#### LNG CC 블록 매핑

LNG 발전기는 Combined Cycle (CC) 단위로 운영됩니다.
하나의 CC 블록 내 GT(가스터빈) + ST(증기터빈)이 동일 gen_id에 매핑됩니다.

```
예: 서인천GT#7, 서인천GT#8, 서인천ST#7, 서인천ST#8 → gen_id 17
```

#### 용량 불일치로 제외된 발전기

물리 발전기의 설비용량과 모델 Pmax가 크게 다른 경우 매핑에서 제외합니다.

| 연료 | 발전기 | 물리 용량 | 모델 Pmax | 비율 |
|------|--------|----------|----------|------|
| Coal | 고성#2 | 1,040 MW | 200 MW | 5.20 |
| Coal | 동해#1, #2 | 200 MW | 730 MW | 0.27 |
| LNG | 인천공항GT#1/#2/ST#1 | 127 MW | 880 MW | 0.14 |

## 4. Step 1: PDF 파싱 (parse_pdf.py)

### 실행

```bash
python code/parse_pdf.py <year>

# 예시
python code/parse_pdf.py 2022
python code/parse_pdf.py 2025
```

### 처리 과정

1. **PDF 테이블 추출**: pdfplumber로 각 PDF에서 정비 스케줄 테이블 추출
2. **연료원 매핑**: 한글 연료원을 영문으로 변환
   | PDF 연료원 | 변환 후 |
   |-----------|---------|
   | 유연탄 | Coal |
   | 무연탄 | Coal |
   | 유류 | Oil |
   | 원자력 | Nuclear |
   | 그 외 | 원본 유지 (LNG, 수력, 양수 등) |
3. **중복 제거**: 동일 (회원사, 연료원, 발전기명, 설비용량, 시작일시, 종료일시) 행 제거
4. **기간 병합**: 동일 발전기의 겹치는 정비 기간을 하나로 병합
5. **위치 매칭**: Excel 마스터 데이터에서 광역지역/세부지역 자동 매칭

### 출력

`results/{year}/maintenance_schedule.csv`

| 컬럼 | 설명 | 예시 |
|------|------|------|
| 회원사 | 발전 회사명 | 한국남동발전(주) |
| 연료원 | 연료 종류 | Coal |
| 발전기명 | 발전기 이름 | 영흥#3 |
| 설비용량 | MW 단위 용량 | 870.0 |
| 시작일 | 정비 시작일 | 2025-03-15 |
| 시작시간 | 정비 시작 시각 | 1:00 |
| 종료일 | 정비 종료일 | 2025-04-20 |
| 종료시간 | 정비 종료 시각 | 24:00 |
| 광역지역 | 광역 지역명 | 인천 |
| 세부지역 | 세부 지역명 | 옹진 |

### 회원사-마스터 매칭

PDF의 회원사명(정식명칭)을 Excel의 약칭으로 변환하여 매칭합니다.

| PDF 회원사 | Excel 약칭 |
|-----------|-----------|
| 한국남동발전(주) | 남동 |
| 한국남부발전(주) | 남부 |
| 한국동서발전(주) | 동서 |
| 한국서부발전(주) | 서부 |
| 한국중부발전(주) | 중부 |
| 한국수력원자력(주) | 한수원 |

발전기명 매칭은 기본명 추출 후 단계적으로 시도합니다:
1. (회원사, 기본명) 정확 매칭
2. 다른 회원사의 동일 기본명 매칭
3. 기본명만으로 매칭
4. 접두사(신, GS) 제거 후 매칭
5. 부분 매칭

## 5. Step 2: mustoff 생성 (gen_mustoff.py)

### 실행

```bash
python code/gen_mustoff.py <year>

# 예시
python code/gen_mustoff.py 2022
python code/gen_mustoff.py 2025
```

### 날짜/시간 변환 규칙

#### Day 번호

- **Day 1** = 해당 연도 1월 1일
- **Day 365** = 해당 연도 12월 31일 (평년)
- **Day 366+** = 다음 연도

#### 시작 시간 (off_start_time)

```
start_time = max(hour, 1)
```

- 0시 → 1
- 9시 → 9

#### 종료 시간 (off_end_time)

```
if minutes > 0:
    end_time = hour + 1
else:
    end_time = hour if hour > 0 else 24
```

- 24:00 → 24
- 18:00 → 18
- 0:00 → 24
- 13:30 → 14

#### 연도 간 이어지는 정비

- 해당 연도 **이전에 끝나는** 정비: **제외** (mustoff에 포함하지 않음)
- 해당 연도 **이전에 시작**하여 해당 연도까지 이어지는 정비: start를 **day=1, time=1**로 클램프

```
예: 2024-09-19 ~ 2025-02-13 정비 (2025년 기준)
    → off_start_day=1, off_start_time=1, off_end_day=44, off_end_time=24
```

### 출력

`results/{year}/mustoff/{fuel}_mustoff.csv`

| 컬럼 | 설명 | 예시 |
|------|------|------|
| id | KPG193 gen_id | 30 |
| off_start_day | 정비 시작일 (day number) | 1 |
| off_start_time | 정비 시작 시각 | 1 |
| off_end_day | 정비 종료일 (day number) | 44 |
| off_end_time | 정비 종료 시각 | 24 |

## 6. 새 연도 데이터 추가

### 절차

```bash
# 1. PDF 파일 배치
#    - 해당 연도 주간 정비계획 PDF를 data/kpx-data/{year}/에 복사
#    - 전년도 말 PDF 중 해당 연도까지 이어지는 정비가 있는 파일도 포함

# 2. PDF 파싱
python code/parse_pdf.py {year}

# 3. mustoff 생성
python code/gen_mustoff.py {year}

# 4. 결과 확인
ls results/{year}/mustoff/
```

### 새 발전기 추가 시

`mappings.py`에 물리발전기명 → gen_id 매핑을 추가합니다.

1. KPG193 모델의 `mpc.gen`에서 해당 발전기의 gen_id(1-based 행 번호) 확인
2. 물리 발전기의 설비용량과 모델 Pmax 비교 (0.3 ~ 3.0 범위 확인)
3. `mappings.py`의 해당 연료 딕셔너리에 매핑 추가

```python
# mappings.py 예시
COAL_PHYS_TO_GENID = {
    ...
    '새발전기#1': 새gen_id,
}
```

## 7. 현재 결과 요약

### 2022년 (49 PDFs)

| 연료 | 행 수 | gen_id 수 |
|------|-------|----------|
| Coal | 203 | 36 |
| Nuclear | 19 | 17 |
| LNG | 1,226 | 43 |

### 2025년 (53 PDFs)

| 연료 | 행 수 | gen_id 수 |
|------|-------|----------|
| Coal | 191 | 36 |
| Nuclear | 12 | 12 |
| LNG | 1,018 | 42 |

## 8. 트러블슈팅

### PDF 파싱 실패 (0 rows)

일부 PDF가 스캔 이미지로 되어 있거나 테이블 구조가 다를 수 있습니다.
pdfplumber는 텍스트 기반 PDF만 처리 가능합니다.

### Unmapped 발전기

`gen_mustoff.py` 실행 시 Unmapped 목록이 출력됩니다.
이는 `mappings.py`에 매핑이 없는 발전기입니다.

- **의도적 제외**: 용량 불일치 발전기 (고성#2, 동해#1/#2, 인천공항)
- **KPG193 모델에 없는 발전기**: 소규모 열병합, 제주 발전기 등
- **새로 추가된 발전기**: `mappings.py`에 매핑 추가 필요

### Excel 마스터 파일 없음

Excel 파일이 없으면 위치 정보(광역지역, 세부지역)가 비어 있지만,
mustoff 생성에는 영향 없습니다.
