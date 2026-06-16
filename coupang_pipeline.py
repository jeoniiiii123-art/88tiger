"""
쿠팡 광고 데이터 파이프라인
raw/pa, raw/nca, raw/ba 에서 xlsx 파일을 읽어 output/data.csv 생성
"""

import pandas as pd
import re
import sys
from pathlib import Path
from datetime import timedelta

BASE_DIR     = Path(__file__).parent
RAW_PA_DIR   = BASE_DIR / "raw" / "pa"
RAW_NCA_DIR  = BASE_DIR / "raw" / "nca"
RAW_BA_DIR   = BASE_DIR / "raw" / "ba"
OUT_DIR      = BASE_DIR / "output"
OUT_FILE     = OUT_DIR / "data.csv"

OUTPUT_COLS = [
    "date", "week", "brand", "ad_type", "campaign",
    "display_name", "full_name", "option_id",
    "impressions", "clicks", "spend", "ctr", "cpc", "cpm",
    "orders_1d", "revenue_1d", "roas_1d",
    "orders_14d", "revenue_14d", "roas_14d",
    "new_customers", "cost_per_new_customer", "new_revenue", "new_roas",
    "video_cpm",
]
DEDUP_KEY = ["date", "brand", "ad_type", "option_id"]


# ─────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────

def get_week_label(d):
    """date → '6월 1주차'  (월요일 시작)
    월 첫날이 월요일이 아니면 → 첫 월요일 이전을 1주차, 첫 월요일부터 2주차
    월 첫날이 월요일이면    → 첫 월요일부터 1주차
    """
    first_day = d.replace(day=1)
    days_to_mon = (7 - first_day.weekday()) % 7
    first_mon = first_day + timedelta(days=days_to_mon)
    if first_mon == first_day:
        # 월 첫날이 월요일: 바로 1주차 시작
        week_num = (d - first_mon).days // 7 + 1
    elif d < first_mon:
        # 첫 월요일 이전(월 초 토막 기간) → 1주차
        week_num = 1
    else:
        # 첫 월요일부터 → 2주차 시작
        week_num = (d - first_mon).days // 7 + 2
    return f"{d.month}월 {week_num}주차"


def get_brand(product_name):
    s = str(product_name) if pd.notna(product_name) else ""
    if "타이거" in s:
        return "타이거모닝"
    if "팔팔" in s:
        return "팔팔호랑이"
    return "기타"


def get_display_name(full_name):
    s = str(full_name) if pd.notna(full_name) else ""
    return s.split(",")[0].strip()


def clean_num(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "").str.replace("%", "").str.strip(),
        errors="coerce",
    )


def date_from_filename(path: Path, position: int = 0) -> str:
    # 20YY로 시작하는 8자리만 날짜로 인식 (파일명 prefix 숫자 오인식 방지)
    dates = re.findall(r"(20\d{6})", path.stem)
    if len(dates) > position:
        d = dates[position]
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return None


def find_col(df, *keywords):
    """컬럼명에 키워드를 모두 포함하는 첫 번째 컬럼 반환"""
    for c in df.columns:
        if all(k in c for k in keywords):
            return c
    return None


def read_excel_safe(path: Path) -> pd.DataFrame:
    """파일이 잠겨있으면 임시 복사본으로 읽기"""
    try:
        return pd.read_excel(path)
    except PermissionError:
        import shutil, tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        shutil.copy2(path, tmp.name)
        df = pd.read_excel(tmp.name)
        import os; os.unlink(tmp.name)
        return df


def safe_series(df, col, length, default=""):
    if col and col in df.columns:
        return df[col]
    return pd.Series([default] * length, dtype=object)


# ─────────────────────────────────────────
# PA 로더
# ─────────────────────────────────────────

def load_pa(path: Path) -> pd.DataFrame:
    df = read_excel_safe(path)
    df.columns = df.columns.str.strip()

    date_col = find_col(df, "날짜")
    if date_col is None:
        print(f"  [PA 경고] 날짜 컬럼 없음: {path.name}")
        return pd.DataFrame()

    df["_date"] = pd.to_datetime(
        df[date_col].astype(str).str.strip().str[:8], format="%Y%m%d", errors="coerce"
    )
    df = df.dropna(subset=["_date"]).copy()

    # 컬럼 매핑
    col_map = {
        find_col(df, "캠페인명"):          "campaign",
        find_col(df, "광고집행 상품명"):    "full_name",
        find_col(df, "광고집행 옵션ID"):    "option_id",
        find_col(df, "노출수"):             "impressions",
        find_col(df, "클릭수"):             "clicks",
        find_col(df, "광고비"):             "spend",
        find_col(df, "총 주문수(1일)"):     "orders_1d",
        find_col(df, "총 전환매출액(1일)"): "revenue_1d",
        find_col(df, "총광고수익률(1일)"):  "roas_1d_raw",
        find_col(df, "총 주문수(14일)"):    "orders_14d",
        find_col(df, "총 전환매출액(14일)"):"revenue_14d",
        find_col(df, "총광고수익률(14일)"): "roas_14d_raw",
    }
    col_map = {k: v for k, v in col_map.items() if k is not None}
    df = df.rename(columns=col_map)

    n = len(df)
    out = pd.DataFrame()
    out["_date"]    = df["_date"]
    out["campaign"] = safe_series(df, "campaign", n)
    out["full_name"]= safe_series(df, "full_name", n)
    out["option_id"]= safe_series(df, "option_id", n).astype(str)

    for c in ["impressions","clicks","spend","orders_1d","revenue_1d","orders_14d","revenue_14d"]:
        out[c] = clean_num(df[c]) if c in df.columns else pd.NA

    # roas 원본 저장 (rate)
    out["roas_1d_raw"]  = clean_num(df["roas_1d_raw"])  if "roas_1d_raw"  in df.columns else pd.NA
    out["roas_14d_raw"] = clean_num(df["roas_14d_raw"]) if "roas_14d_raw" in df.columns else pd.NA

    # 키워드 단위 → 옵션 단위로 집계
    grp = out.groupby(["_date","campaign","full_name","option_id"], dropna=False)
    agg = grp.agg(
        impressions =("impressions","sum"),
        clicks      =("clicks","sum"),
        spend       =("spend","sum"),
        orders_1d   =("orders_1d","sum"),
        revenue_1d  =("revenue_1d","sum"),
        orders_14d  =("orders_14d","sum"),
        revenue_14d =("revenue_14d","sum"),
    ).reset_index()

    agg["brand"]        = agg["full_name"].apply(get_brand)
    agg["display_name"] = agg["full_name"].apply(get_display_name)
    agg["ad_type"]      = "PA"
    agg["date"]         = agg["_date"].dt.strftime("%Y-%m-%d")
    agg["ctr"]   = agg["clicks"] / agg["impressions"].replace(0, float("nan"))
    agg["cpc"]   = agg["spend"]  / agg["clicks"].replace(0, float("nan"))
    agg["cpm"]   = pd.NA
    agg["roas_1d"]  = agg["revenue_1d"]  / agg["spend"].replace(0, float("nan"))
    agg["roas_14d"] = agg["revenue_14d"] / agg["spend"].replace(0, float("nan"))
    agg["new_customers"] = pd.NA
    agg["cost_per_new_customer"] = pd.NA
    agg["new_revenue"] = pd.NA
    agg["new_roas"]    = pd.NA
    agg["video_cpm"]   = pd.NA

    # week 임시 추가 (run_pipeline에서 일괄 적용하지만 여기서도 추가)
    agg["week"] = agg["_date"].apply(lambda d: get_week_label(d.date()))

    return agg[OUTPUT_COLS]


# ─────────────────────────────────────────
# NCA 로더
# ─────────────────────────────────────────

def load_nca(path: Path) -> pd.DataFrame:
    df = read_excel_safe(path)
    df.columns = df.columns.str.strip()

    date_col = find_col(df, "날짜")
    if date_col is None:
        print(f"  [NCA 경고] 날짜 컬럼 없음: {path.name}")
        return pd.DataFrame()

    df["_date"] = pd.to_datetime(
        df[date_col].astype(str).str.strip().str[:8], format="%Y%m%d", errors="coerce"
    )
    df = df.dropna(subset=["_date"]).copy()

    camp_col = find_col(df, "캠페인")
    prod_col = find_col(df, "광고집행 상품명")
    ad_col   = find_col(df, "광고 이름") or find_col(df, "광고명")
    opt_col  = find_col(df, "옵션")

    col_map = {
        find_col(df, "노출수"):                         "impressions",
        find_col(df, "클릭수"):                         "clicks",
        find_col(df, "집행 광고비"):                    "spend",
        find_col(df, "신규 구매 고객 수"):               "new_customers",
        find_col(df, "신규 구매 고객당 비용"):           "cost_per_new_customer",
        find_col(df, "첫구매를 통한 광고 전환 매출"):   "new_revenue",
        find_col(df, "첫구매를 통한 광고수익률"):       "new_roas_raw",
    }
    col_map = {k: v for k, v in col_map.items() if k is not None}
    df = df.rename(columns=col_map)

    n = len(df)
    out = pd.DataFrame(index=range(n))
    out["_date"]     = df["_date"].values
    out["campaign"]  = safe_series(df, camp_col, n).values
    out["full_name"] = safe_series(df, prod_col, n).values
    out["option_id"] = safe_series(df, opt_col, n).astype(str).values

    for c in ["impressions","clicks","spend","new_customers","cost_per_new_customer","new_revenue"]:
        out[c] = clean_num(df[c]) if c in df.columns else pd.NA

    out["new_roas"] = clean_num(df["new_roas_raw"]) if "new_roas_raw" in df.columns else pd.NA

    # 상품명 → 광고명 순으로 브랜드 감지
    prod_s = safe_series(df, prod_col, n)
    ad_s   = safe_series(df, ad_col,   n)
    camp_s = safe_series(df, camp_col, n)
    def nca_brand(row):
        for s in [row["prod"], row["ad"], row["camp"]]:
            b = get_brand(s)
            if b != "기타":
                return b
        return "기타"
    brand_df = pd.DataFrame({"prod": prod_s.values, "ad": ad_s.values, "camp": camp_s.values})

    out["brand"]        = brand_df.apply(nca_brand, axis=1)
    out["display_name"] = out["full_name"].apply(get_display_name)
    out["ad_type"]      = "NCA"
    out["date"]         = pd.to_datetime(out["_date"]).dt.strftime("%Y-%m-%d")
    out["ctr"]          = out["clicks"] / out["impressions"].replace(0, float("nan"))
    out["cpc"]          = pd.NA
    out["cpm"]          = pd.NA
    out["orders_1d"]    = pd.NA
    out["revenue_1d"]   = pd.NA
    out["roas_1d"]      = pd.NA
    out["orders_14d"]   = pd.NA
    out["revenue_14d"]  = pd.NA
    out["roas_14d"]     = pd.NA
    out["video_cpm"]    = pd.NA
    out["week"]         = pd.to_datetime(out["_date"]).apply(lambda d: get_week_label(d.date()))

    return out[OUTPUT_COLS]


# ─────────────────────────────────────────
# BA 로더
# ─────────────────────────────────────────

def load_ba(path: Path) -> pd.DataFrame:
    df = read_excel_safe(path)
    df.columns = df.columns.str.strip()

    date_col = find_col(df, "날짜")
    if date_col is None:
        print(f"  [BA 경고] 날짜 컬럼 없음: {path.name}")
        return pd.DataFrame()

    df["_date"] = pd.to_datetime(
        df[date_col].astype(str).str.strip().str[:8], format="%Y%m%d", errors="coerce"
    )
    df = df.dropna(subset=["_date"]).copy()

    camp_col = find_col(df, "캠페인명")
    prod_col = find_col(df, "상품") or find_col(df, "광고집행 상품명")
    ad_col   = find_col(df, "광고명")
    opt_col  = find_col(df, "광고집행 옵션ID")

    col_map = {
        find_col(df, "노출수"):              "impressions",
        find_col(df, "클릭수"):              "clicks",
        find_col(df, "광고비"):              "spend",
        find_col(df, "총 전환매출액(1일)"):  "revenue_1d",
        find_col(df, "총광고수익률(1일)"):   "roas_1d_raw",
        find_col(df, "총 전환매출액(14일)"): "revenue_14d",
        find_col(df, "총광고수익률(14일)"):  "roas_14d_raw",
        find_col(df, "동영상 3초"):          "video_cpm",
    }
    col_map = {k: v for k, v in col_map.items() if k is not None}
    df = df.rename(columns=col_map)

    n = len(df)
    out = pd.DataFrame(index=range(n))
    out["_date"]     = df["_date"].values
    out["campaign"]  = safe_series(df, camp_col, n).values
    out["full_name"] = safe_series(df, prod_col, n).values
    out["option_id"] = safe_series(df, opt_col, n).astype(str).values

    for c in ["impressions","clicks","spend","revenue_1d","revenue_14d","video_cpm"]:
        out[c] = clean_num(df[c]) if c in df.columns else pd.NA

    out["roas_1d"]  = clean_num(df["roas_1d_raw"])  if "roas_1d_raw"  in df.columns else pd.NA
    out["roas_14d"] = clean_num(df["roas_14d_raw"]) if "roas_14d_raw" in df.columns else pd.NA

    # 상품 → 광고명 → 캠페인명 순으로 브랜드 감지
    prod_s = safe_series(df, prod_col, n)
    ad_s   = safe_series(df, ad_col,   n)
    camp_s = safe_series(df, camp_col, n)
    def ba_brand(row):
        for s in [row["prod"], row["ad"], row["camp"]]:
            b = get_brand(s)
            if b != "기타":
                return b
        return "기타"
    brand_df = pd.DataFrame({"prod": prod_s.values, "ad": ad_s.values, "camp": camp_s.values})
    out["brand"]        = brand_df.apply(ba_brand, axis=1)
    out["display_name"] = camp_s.values
    out["ad_type"]      = "BA"
    out["date"]         = pd.to_datetime(out["_date"]).dt.strftime("%Y-%m-%d")
    out["ctr"]          = out["clicks"] / out["impressions"].replace(0, float("nan"))
    out["cpc"]          = pd.NA
    out["cpm"]          = out["spend"] / out["impressions"].replace(0, float("nan")) * 1000
    out["orders_1d"]    = pd.NA
    out["orders_14d"]   = pd.NA
    out["new_customers"] = pd.NA
    out["cost_per_new_customer"] = pd.NA
    out["new_revenue"]  = pd.NA
    out["new_roas"]     = pd.NA
    out["week"]         = pd.to_datetime(out["_date"]).apply(lambda d: get_week_label(d.date()))

    return out[OUTPUT_COLS]


# ─────────────────────────────────────────
# 파이프라인 실행
# ─────────────────────────────────────────

def run_pipeline():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pa_files  = sorted(RAW_PA_DIR.glob("*.xlsx"))  if RAW_PA_DIR.exists()  else []
    nca_files = sorted(RAW_NCA_DIR.glob("*.xlsx")) if RAW_NCA_DIR.exists() else []
    ba_files  = sorted(RAW_BA_DIR.glob("*.xlsx"))  if RAW_BA_DIR.exists()  else []

    if not pa_files and not nca_files and not ba_files:
        print("❌ raw 파일이 없습니다. raw/pa, raw/nca, raw/ba 폴더를 확인하세요.")
        sys.exit(1)

    print(f"▶ 파일 감지: PA {len(pa_files)}개 / NCA {len(nca_files)}개 / BA {len(ba_files)}개\n")

    frames = []
    for tag, files, loader in [("PA", pa_files, load_pa), ("NCA", nca_files, load_nca), ("BA", ba_files, load_ba)]:
        for f in files:
            print(f"  [{tag}] {f.name}")
            try:
                df = loader(f)
                if not df.empty:
                    frames.append(df)
            except Exception as e:
                print(f"  [{tag} 오류] {f.name}: {e}")

    if not frames:
        print("❌ 유효한 데이터가 없습니다.")
        sys.exit(1)

    new_df = pd.concat(frames, ignore_index=True)

    # 빈 행 제거: date가 없는 행만 제거 (Excel 빈 행 대응)
    date_mask = new_df["date"].notna() & (~new_df["date"].astype(str).isin(["nan", "None", "NaT", ""]))
    new_df = new_df[date_mask].copy()

    # 기존 data.csv와 병합 (새 데이터로 덮어쓰기)
    if OUT_FILE.exists():
        existing = pd.read_csv(OUT_FILE, encoding="utf-8-sig", dtype=str)
        new_keys = set(
            zip(new_df["date"].astype(str), new_df["brand"].astype(str),
                new_df["ad_type"].astype(str), new_df["option_id"].astype(str))
        )
        mask = ~existing.apply(
            lambda r: (str(r["date"]), str(r["brand"]), str(r["ad_type"]), str(r["option_id"])) in new_keys,
            axis=1,
        )
        result = pd.concat([existing[mask], new_df.astype(str)], ignore_index=True)
    else:
        result = new_df.astype(str)

    result = result.sort_values(["date", "brand", "ad_type"]).reset_index(drop=True)

    # OUTPUT_COLS 순서 보장
    for c in OUTPUT_COLS:
        if c not in result.columns:
            result[c] = ""
    result = result[OUTPUT_COLS]

    result.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\n[완료] {OUT_FILE} 저장됨")
    print(f"  총 {len(result):,}행 / 날짜 {result['date'].nunique()}일")
    if "ad_type" in result.columns:
        print(f"  광고유형별: {result['ad_type'].value_counts().to_dict()}")
    if "brand" in result.columns:
        print(f"  브랜드별:   {result['brand'].value_counts().to_dict()}")


if __name__ == "__main__":
    run_pipeline()
