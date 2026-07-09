import sys; sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('pipeline', 'coupang_pipeline.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BRAND = "팔팔호랑이"

def xlsx_files(folder):
    return sorted(f for f in Path(folder).glob("*.xlsx") if not f.name.startswith("~$"))

def pipe_sum(df, col):
    try: return int(df[col].replace('', '0').fillna(0).astype(float).sum())
    except: return 0

csv = pd.read_csv('output/data.csv', encoding='utf-8-sig', dtype=str)

for month, prefix in [("5월","2026-05"), ("6월","2026-06")]:
    print(f"\n{'='*60}")
    print(f"{BRAND} {month} 검증")
    print(f"{'='*60}")

    m_csv = csv[(csv['date'].str.startswith(prefix)) & (csv['brand']==BRAND)]

    # PA
    pa_raw_all = []
    for f in xlsx_files('RAW/PA'):
        if f"2026{prefix[-2:]}" not in f.name.replace('-',''): continue
        df = mod.load_pa(f)
        df2 = df[df['brand']==BRAND]
        if len(df2) == 0: continue
        pa_raw_all.append((f.name, df2))
    print(f"\n[PA - RAW 파일별]")
    for fname, df2 in pa_raw_all:
        print(f"  {fname}")
        print(f"    날짜: {df2['date'].min()} ~ {df2['date'].max()} ({df2['date'].nunique()}일)")
        print(f"    광고비:{pipe_sum(df2,'spend'):,} / 노출:{pipe_sum(df2,'impressions'):,} / 클릭:{pipe_sum(df2,'clicks'):,} / 매출1일:{pipe_sum(df2,'revenue_1d'):,}")
    pa_csv = m_csv[m_csv['ad_type']=='PA']
    print(f"  [data.csv] 행수:{len(pa_csv)} / 광고비:{pipe_sum(pa_csv,'spend'):,} / 노출:{pipe_sum(pa_csv,'impressions'):,} / 클릭:{pipe_sum(pa_csv,'clicks'):,} / 매출1일:{pipe_sum(pa_csv,'revenue_1d'):,}")

    # NCA
    nca_raw_all = []
    for f in xlsx_files('RAW/NCA'):
        if f"2026{prefix[-2:]}" not in f.name.replace('-',''): continue
        df = mod.load_nca(f)
        df2 = df[df['brand']==BRAND]
        if len(df2) == 0: continue
        nca_raw_all.append((f.name, df2))
    print(f"\n[NCA - RAW 파일별]")
    for fname, df2 in nca_raw_all:
        print(f"  {fname}")
        print(f"    날짜: {df2['date'].min()} ~ {df2['date'].max()} ({df2['date'].nunique()}일)")
        print(f"    광고비:{pipe_sum(df2,'spend'):,} / 신규고객:{pipe_sum(df2,'new_customers'):,} / 첫구매:{pipe_sum(df2,'new_revenue'):,}")
    nca_csv = m_csv[m_csv['ad_type']=='NCA']
    print(f"  [data.csv] 행수:{len(nca_csv)} / 광고비:{pipe_sum(nca_csv,'spend'):,} / 신규고객:{pipe_sum(nca_csv,'new_customers'):,} / 첫구매:{pipe_sum(nca_csv,'new_revenue'):,}")

    # BA
    ba_raw_all = []
    for f in xlsx_files('RAW/BA'):
        if f"2026{prefix[-2:]}" not in f.name.replace('-',''): continue
        df = mod.load_ba(f)
        df2 = df[df['brand']==BRAND]
        if len(df2) == 0: continue
        ba_raw_all.append((f.name, df2))
    print(f"\n[BA - RAW 파일별]")
    if ba_raw_all:
        for fname, df2 in ba_raw_all:
            print(f"  {fname}")
            print(f"    날짜: {df2['date'].min()} ~ {df2['date'].max()} ({df2['date'].nunique()}일)")
            print(f"    광고비:{pipe_sum(df2,'spend'):,} / 노출:{pipe_sum(df2,'impressions'):,} / 클릭:{pipe_sum(df2,'clicks'):,}")
    else:
        print(f"  (팔팔호랑이 BA 데이터 없음)")
    ba_csv = m_csv[m_csv['ad_type']=='BA']
    print(f"  [data.csv] 행수:{len(ba_csv)} / 광고비:{pipe_sum(ba_csv,'spend'):,} / 노출:{pipe_sum(ba_csv,'impressions'):,}")

