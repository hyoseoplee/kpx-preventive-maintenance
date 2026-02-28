# KPX 발전기 예방정비 데이터 처리

## 프로젝트 개요
KPX(한국전력거래소) 주간 예방정비계획 PDF를 파싱하여 KPG193 전력계통 모델용 mustoff CSV 파일을 생성하는 파이프라인.

## 디렉토리 구조
```
├── data/
│   ├── HOME_발전설비_발전기별_발전기현황-*.xlsx   # 발전기 마스터 (위치/용량)
│   └── kpx-data/
│       ├── 2022/   # 2021년 12월 5주차 포함 (2022년으로 이어지는 정비)
│       └── 2025/   # 2024년 12월 4주차 포함 (2025년으로 이어지는 정비)
├── code/
│   ├── parse_pdf.py      # Step 1: PDF → maintenance_schedule.csv
│   ├── gen_mustoff.py    # Step 2: CSV → mustoff files
│   └── mappings.py       # 물리발전기 → 모델 gen_id 매핑
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
- 연료원 매핑: 유연탄/무연탄→Coal, 유류→Oil, 원자력→Nuclear
- 동일 발전기의 중복 제거 및 겹치는 정비 기간 병합
- Excel 마스터 데이터에서 광역지역/세부지역 자동 매칭

### mustoff 생성 (gen_mustoff.py)
- Day 1 = 해당 연도 1월 1일
- start_time: max(hour, 1)
- end_time: minutes > 0이면 hour+1, 아니면 hour (hour=0이면 24)
- 해당 연도 이전에 끝나는 정비는 제외
- 해당 연도 이전에 시작하여 해당 연도까지 이어지는 정비는 start를 day=1, time=1로 클램프

### 매핑 (mappings.py)
- gen_id = mpc.gen (KPG193_ver1_5.m)의 1-based 행 인덱스
- Coal: 36개 물리발전기 → 36 gen_ids (10개 bus)
- Nuclear: 17개 물리발전기 → 12 gen_ids (4개 bus)
- LNG: 87+개 물리발전기 → 43 gen_ids (CC 블록 단위 매핑)
- 상세 매핑 테이블: [docs/manual.md](docs/manual.md#coal-매핑-36개-물리발전기--36-gen_ids) 참조

### 용량 불일치로 제외된 발전기
- Coal: 고성#2 (1040MW vs gen59 Pmax=200MW), 동해#1/#2 (200MW vs gen65 Pmax=730MW)
- LNG: 인천공항GT#1/#2/ST#1 (127MW total vs gen19 Pmax=880MW)

## 문서
- [docs/manual.md](docs/manual.md) - 상세 매뉴얼 (매핑 테이블, 변환 규칙, 트러블슈팅 등)

## 새 연도 데이터 추가 시
1. `data/kpx-data/{year}/`에 PDF 파일 배치
   - 전년도 말 PDF 중 해당 연도까지 이어지는 정비가 포함된 파일도 함께 배치
2. `python code/parse_pdf.py {year}` 실행
3. `python code/gen_mustoff.py {year}` 실행
4. `results/{year}/mustoff/` 확인
