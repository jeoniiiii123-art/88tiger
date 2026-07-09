import sys; sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('pipeline', 'coupang_pipeline.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def xlsx_files(folder):
    return sorted(f for f in Path(folder).glob("*.xlsx") if not f.name.startswith("~$"))

def pipe_sum(df, col):
    try: return int(df[col].replace('', '0').fillna(0).astype(float).sum())
    except: return 0

# ─── 1. data.csv 6월 중복 행 확인 ────────────────────
print("=" * 60)
print("1. data.csv 6월 날짜별 행수 (중복 체크)")
print("=" * 60)
csv = pd.read_csv('output/data.csv', encoding='utf-8-sig', dtype=str)
jun = csv[csv['date'].str.startswith('2026-06')]
print(f"6월 전체 행수: {len(jun)}")
print(f"6월 고유 날짜: {jun['date'].nunique()}일")

# 광고유형별
for at in ['PA', 'NCA', 'BA']:
    sub = jun[jun['ad_type'] == at]
    print(f"\n  [{at}] 날짜별 행수 (중복 있으면 같은 날 여러 번 나타남)")
    daily = sub.groupby('date').size()
    print(f"    날짜 수: {len(daily)}, 총 행수: {len(sub)}")
    # 날짜+brand+option_id 기준 중복 체크
    dupes = sub[sub.duplicated(['date','brand','ad_type','option_id'], keep=False)]
    print(f"    중복 행수 (date+brand+ad_type+option_id): {len(dupes)}")

# ─── 2. 6월 PA 파일별 비교 ────────────────────────────
print("\n" + "=" * 60)
print("2. PA 6월 파일별 수치 비교")
print("=" * 60)
for f in xlsx_files('RAW/PA'):
    if '202606' not in f.name: continue
    pipe = mod.load_pa(f)
    print(f"\n[{f.name}]")
    print(f"  날짜 범위: {pipe['date'].min()} ~ {pipe['date'].max()}")
    print(f"  고유 날짜: {pipe['date'].nunique()}일 / 행수: {len(pipe)}")
    for brand in pipe['brand'].unique():
        sub = pipe[pipe['brand']==brand]
        print(f"  [{brand}] 광고비:{pipe_sum(sub,'spend'):,} / 노출:{pipe_sum(sub,'impressions'):,} / 클릭:{pipe_sum(sub,'clicks'):,}")

# ─── 3. 6월 NCA 파일별 비교 ──────────────────────────
print("\n" + "=" * 60)
print("3. NCA 6월 파일별 수치 비교")
print("=" * 60)
for f in xlsx_files('RAW/NCA'):
    if '202606' not in f.name: continue
    pipe = mod.load_nca(f)
    print(f"\n[{f.name}]")
    print(f"  날짜 범위: {pipe['date'].min()} ~ {pipe['date'].max()}")
    print(f"  고유 날짜: {pipe['date'].nunique()}일 / 행수: {len(pipe)}")
    for brand in sorted(pipe['brand'].unique()):
        sub = pipe[pipe['brand']==brand]
        print(f"  [{brand}] 광고비:{pipe_sum(sub,'spend'):,} / 신규고객:{pipe_sum(sub,'new_customers'):,} / 첫구매:{pipe_sum(sub,'new_revenue'):,}")

# ─── 4. 6월 BA 파일별 비교 ───────────────────────────
print("\n" + "=" * 60)
print("4. BA 6월 파일별 수치 비교")
print("=" * 60)
for f in xlsx_files('RAW/BA'):
    if '202606' not in f.name: continue
    pipe = mod.load_ba(f)
    print(f"\n[{f.name}]")
    print(f"  날짜 범위: {pipe['date'].min()} ~ {pipe['date'].max()}")
    print(f"  고유 날짜: {pipe['date'].nunique()}일 / 행수: {len(pipe)}")
    for brand in sorted(pipe['brand'].unique()):
        sub = pipe[pipe['brand']==brand]
        print(f"  [{brand}] 광고비:{pipe_sum(sub,'spend'):,} / 노출:{pipe_sum(sub,'impressions'):,}")

# ─── 5. 현재 data.csv 6월 브랜드/광고유형별 합계 ────────
print("\n" + "=" * 60)
print("5. data.csv 6월 최종 집계")
print("=" * 60)
for at in ['PA','NCA','BA']:
    print(f"\n  [{at}]")
    for brand in ['타이거모닝','팔팔호랑이','기타']:
        sub = jun[(jun['ad_type']==at) & (jun['brand']==brand)]
        if len(sub) == 0: continue
        if at == 'PA':
            print(f"    {brand}: 광고비 {pipe_sum(sub,'spend'):,} / 노출 {pipe_sum(sub,'impressions'):,} / 매출1일 {pipe_sum(sub,'revenue_1d'):,}")
        elif at == 'NCA':
            print(f"    {brand}: 광고비 {pipe_sum(sub,'spend'):,} / 신규고객 {pipe_sum(sub,'new_customers'):,} / 첫구매매출 {pipe_sum(sub,'new_revenue'):,}")
        elif at == 'BA':
            print(f"    {brand}: 광고비 {pipe_sum(sub,'spend'):,} / 노출 {pipe_sum(sub,'impressions'):,}")
