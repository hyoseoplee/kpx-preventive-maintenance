# KPX 발전기 예방정비 데이터 처리

## 프로젝트 개요
KPX(한국전력거래소) 주간 예방정비계획 PDF를 파싱하여 KPG193 전력계통 모델용 mustoff CSV 파일을 생성하는 파이프라인.

## 디렉토리 구조
```
├── data/
│   ├── HOME_발전설비_발전기별_발전기현황-*.xlsx   # 발전기 마스터 (위치/용량)
│   └── kpx-data/
│       ├── 2022/   # 49 PDFs (2021년 12월 5주차 포함)
│       └── 2025/   # 53 PDFs (2024년 12월 4주차 포함)
├── code/
│   ├── parse_pdf.py      # Step 1: PDF → maintenance_schedule.csv
│   ├── gen_mustoff.py    # Step 2: CSV → mustoff files
│   └── mappings.py       # 물리발전기 → 모델 gen_id 매핑
├── docs/
│   └── manual.md         # 상세 매뉴얼 (매핑 테이블, 변환 규칙, 트러블슈팅)
└── results/
    └── {year}/
        ├── maintenance_schedule.csv
        └── mustoff/
            ├── coal_mustoff.csv
            ├── lng_mustoff.csv
            └── nuclear_mustoff.csv
```

## 실행 방법
```bash
pip install pdfplumber openpyxl

# Step 1: PDF 파싱 → CSV (연도 인자 필수)
python code/parse_pdf.py 2025

# Step 2: CSV → mustoff 생성
python code/gen_mustoff.py 2025
```

## 핵심 컨셉

### PDF 파싱 (parse_pdf.py)
- pdfplumber로 주간 정비계획 PDF 테이블 추출
- PDF 컬럼: 회원사, 연료원, 발전기명, 설비용량, 시작일, 시작시간, 종료일, 종료시간
- 연료원 매핑: 유연탄/무연탄→Coal, 유류→Oil, 원자력→Nuclear, 그 외 원본 유지
- 동일 (회원사, 연료원, 발전기명, 설비용량, 일시) 행 중복 제거
- 동일 발전기의 겹치는 정비 기간 병합
- Excel 마스터 데이터(HOME_발전설비_*.xlsx)에서 광역지역/세부지역 자동 매칭
- 회원사명 정규화: 한국남동발전(주)→남동, 한국남부발전(주)→남부 등

### mustoff 생성 (gen_mustoff.py)
- Day 1 = 해당 연도 1월 1일
- start_time: max(hour, 1)
- end_time: minutes > 0이면 hour+1, 아니면 hour (hour=0이면 24)
- 해당 연도 이전에 끝나는 정비는 제외 (end_d < base_date → skip)
- 해당 연도 이전에 시작하여 해당 연도까지 이어지는 정비는 start를 day=1, time=1로 클램프
- mustoff 대상 연료: Coal, Nuclear, LNG만 (양수, 수력 등은 N/A)

### 매핑 (mappings.py)
- gen_id = mpc.gen (KPG193_ver1_5.m)의 1-based 행 인덱스
- Coal: 36개 물리발전기 → 36 gen_ids (10개 bus), 500~1,050 MW
- Nuclear: 17개 물리발전기 → 12 gen_ids (4개 bus), 650~1,400 MW
- LNG: 87+개 물리발전기 → 43 gen_ids (CC 블록 단위 매핑), 115~2,606 MW (블록 합산)
- LNG CC 블록: GT(가스터빈) + ST(증기터빈) → 동일 gen_id
- 상세 매핑 테이블 (발전기별 용량 포함): [docs/manual.md](docs/manual.md) 참조

### 용량 불일치로 제외된 발전기
- Coal: 고성#2 (1040MW vs gen59 Pmax=200MW), 동해#1/#2 (200MW vs gen65 Pmax=730MW)
- LNG: 인천공항GT#1/#2/ST#1 (127MW total vs gen19 Pmax=880MW)

### KPG193에 미포함된 주요 발전기 (unmapped)
- Nuclear: 고리#3, 고리#4, 새울#1, 새울#2, 신한울#1, 신한울#2, 한울#2, 한울#4, 한빛#5, 월성#4
- LNG: 제주복합, 한림복합, 남제주복합 (제주 계통 별도), 김포, 동탄, 양주, 송도, 양산, 청주 등 소규모
- Coal: 강릉안인#1/#2, 호남#1/#2

## 현재 결과

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

## 연도 간 정비 처리
전년도 말 PDF에 해당 연도까지 이어지는 정비가 포함될 수 있음.
해당 PDF를 대상 연도 폴더에 함께 배치하면 자동 처리됨.

| 대상 연도 | 추가 PDF | 이어지는 정비 건수 |
|-----------|---------|----------------|
| 2022 | 2021년 12월 5주차 | Coal +1, LNG +2 |
| 2025 | 2024년 12월 4주차 | Coal 8, LNG 2, Nuclear 1 |

## 새 연도 데이터 추가 시
1. `data/kpx-data/{year}/`에 PDF 파일 배치
   - 전년도 말 PDF 중 해당 연도까지 이어지는 정비가 포함된 파일도 함께 배치
2. `python code/parse_pdf.py {year}` 실행
3. `python code/gen_mustoff.py {year}` 실행
4. `results/{year}/mustoff/` 확인
5. Unmapped 발전기 확인 → 필요시 `mappings.py`에 매핑 추가

## 문서
- [docs/manual.md](docs/manual.md) - 상세 매뉴얼 (매핑 테이블, 변환 규칙, 트러블슈팅 등)
