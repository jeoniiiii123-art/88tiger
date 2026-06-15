"""
쿠팡 광고 보고서 자동 다운로드
PA / NCA / BA 보고서를 이번 달 1일 ~ 어제로 다운로드하여 raw 폴더에 저장

사용법:
  python coupang_download.py                        # 이번 달 1일 ~ 어제
  python coupang_download.py 2026-06-11             # 이번 달 1일 ~ 지정일
  python coupang_download.py 2026-06-01 2026-06-11  # 기간 직접 지정
"""
import os, sys, shutil, time
# Windows CP949 터미널에서 한글/이모지 깨짐 방지
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

COUPANG_ID  = os.getenv("COUPANG_ID")
COUPANG_PW  = os.getenv("COUPANG_PW")
ADVERTISER  = "A01194848"
TEAM_ID     = "89"
BASE_URL    = "https://advertising.coupang.com"

DOWNLOAD_TMP = BASE_DIR / "raw" / "_tmp"
RAW_DIRS = {
    "PA":  BASE_DIR / "raw" / "pa",
    "NCA": BASE_DIR / "raw" / "nca",
    "BA":  BASE_DIR / "raw" / "ba",
}

REPORT_CONFIG = {
    "PA": {
        "url":       f"{BASE_URL}/marketing-reporting/billboard/reports/pa",
        "structure": "캠페인 > 광고그룹 > 상품",
    },
    "NCA": {
        "url":       f"{BASE_URL}/marketing-reporting/billboard/reports/nca",
        "structure": "캠페인 > 광고",
    },
    "BA": {
        "url":       f"{BASE_URL}/marketing-reporting/billboard/reports/bpa",
        "structure": "캠페인 > 광고그룹 > 광고 > 키워드/카테고리 > 소재",
    },
}


class CoupangDownloader:
    def __init__(self, start_date: date, end_date: date, headless: bool = False):
        self.start_date = start_date
        self.end_date   = end_date
        self.start_str  = start_date.strftime("%Y-%m-%d")
        self.end_str    = end_date.strftime("%Y-%m-%d")
        self.today_str  = date.today().strftime("%Y-%m-%d")
        self.driver     = self._init_driver(headless)

    # ── 드라이버 초기화 ───────────────────────────────────────────
    def _init_driver(self, headless: bool) -> webdriver.Chrome:
        DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
        for f in DOWNLOAD_TMP.glob("*"):
            f.unlink(missing_ok=True)

        opt = Options()
        if headless:
            opt.add_argument("--headless=new")
        opt.add_argument("--window-size=1440,900")
        opt.add_argument("--no-sandbox")
        opt.add_argument("--disable-dev-shm-usage")
        opt.add_argument("--disable-blink-features=AutomationControlled")
        opt.add_experimental_option("excludeSwitches", ["enable-automation"])
        opt.add_experimental_option("prefs", {
            "download.default_directory": str(DOWNLOAD_TMP),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        })
        svc = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=svc, options=opt)
        driver.execute_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        return driver

    # ── 공통 헬퍼 ────────────────────────────────────────────────
    def _click(self, by, selector, timeout=25):
        el = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.2)
        el.click()
        return el

    def _find(self, by, selector, timeout=25):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )

    def _try_click(self, by, selector, timeout=4) -> bool:
        try:
            self._click(by, selector, timeout)
            return True
        except Exception:
            return False

    def _react_set(self, el, value: str):
        """React controlled input에 값 주입 후 change 이벤트 발생"""
        self.driver.execute_script("""
            var setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(arguments[0], arguments[1]);
            arguments[0].dispatchEvent(new Event('input',  {bubbles:true}));
            arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
            arguments[0].dispatchEvent(new Event('blur',   {bubbles:true}));
        """, el, value)

    # ── 로그인 ──────────────────────────────────────────────────
    def login(self):
        print("▶ 로그인...")
        self.driver.get(
            f"{BASE_URL}/user/login"
            "?_cap_client=AGENCY&returnUrl=%2Fagency%2Fhome"
        )
        time.sleep(2)

        # "광고 대행사 또는 분석가로 로그인하기" 버튼 — 없으면 이미 Agency 폼 표시
        clicked = self._try_click(By.XPATH,
            "//button[contains(.,'대행사')]"
            " | //a[contains(.,'대행사')]"
            " | //*[contains(@class,'btn')][contains(.,'대행사')]"
            " | //*[contains(.,'대행사')][not(.//*[contains(.,'대행사')])]",
            timeout=6)
        if clicked:
            print("  → 대행사 버튼 클릭")
            time.sleep(1)
        else:
            print("  → Agency 폼 직접 표시됨 (버튼 없음)")

        # 이메일 입력 (비밀번호/hidden/submit 제외한 첫 번째 input)
        id_el = self._find(By.XPATH,
            "(//input[not(@type='password') and not(@type='hidden')"
            " and not(@type='submit') and not(@type='button')])[1]")
        id_el.clear()
        id_el.send_keys(COUPANG_ID)

        pw_el = self._find(By.XPATH, "//input[@type='password']")
        pw_el.clear()
        pw_el.send_keys(COUPANG_PW)

        # "로그인" 버튼 클릭
        self._click(By.XPATH,
            "//button[contains(.,'로그인')]"
            " | //input[@type='submit']")

        WebDriverWait(self.driver, 30).until(EC.url_contains("/agency/"))
        print("  ✓ 로그인 완료")

    # ── 광고주 선택 ──────────────────────────────────────────────
    def select_advertiser(self):
        print("▶ 광고주 선택...")
        self.driver.get(
            f"{BASE_URL}/agency/my-advertisers?teamId={TEAM_ID}")
        time.sleep(3)

        self.driver.save_screenshot(str(BASE_DIR / "debug_advertiser.png"))
        print(f"  현재 URL: {self.driver.current_url}")

        # 검색창 탐색 (다양한 XPath 시도)
        search_xpaths = [
            "//input[@type='search']",
            "//input[contains(@placeholder,'검색')]",
            "//input[contains(@class,'search')]",
            "//input[contains(@placeholder,'광고주')]",
            "//input[contains(@placeholder,'Search')]",
            "//input[@type='text']",
        ]
        search_el = None
        for xp in search_xpaths:
            try:
                search_el = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, xp)))
                print(f"  → 검색창 발견: {xp}")
                break
            except Exception:
                continue

        if search_el:
            self._react_set(search_el, ADVERTISER)
            search_el.send_keys(Keys.RETURN)
            time.sleep(3)
        else:
            print("  → 검색창 없음, 직접 광고주 클릭 시도")

        self.driver.save_screenshot(str(BASE_DIR / "debug_advertiser2.png"))

        # WING 버튼 클릭: 광고주 코드를 포함한 카드 안의 WING 버튼
        self._click(By.XPATH,
            f"//*[contains(text(),'{ADVERTISER}')]"
            f"/ancestor::div[contains(@class,'card') or contains(@class,'item') or contains(@class,'row')]"
            f"//button[translate(.,'wing','WING')='WING' or contains(.,'WING') or contains(.,'wing')]"
            f" | //*[contains(.,'{ADVERTISER}')]"
            f"//following::button[contains(.,'WING') or contains(.,'wing')][1]")

        WebDriverWait(self.driver, 30).until(EC.url_contains("/marketing/"))
        print(f"  ✓ {ADVERTISER} 진입 완료")

    # ── 날짜 입력 ────────────────────────────────────────────────
    def _set_dates(self):
        # "기간 설정" 라디오 버튼 클릭 (페이지 로드 대기 포함)
        self._click(By.XPATH,
            "//label[contains(.,'기간 설정')]"
            " | //span[contains(.,'기간 설정')][ancestor::label]",
            timeout=35)
        time.sleep(0.8)

        # 시작일 input 클릭 → 달력 팝업 열기
        start_inp = self._find(By.XPATH, "//input[@placeholder='시작일']")
        start_inp.click()
        time.sleep(0.5)

        # 달력에서 시작일/종료일 셀 클릭 (title 또는 data 속성 사용)
        for ds, label in [(self.start_str, "시작일"), (self.end_str, "종료일")]:
            self._click(By.XPATH,
                f"//td[@title='{ds}']"
                f" | //td[@aria-label='{ds}']"
                f" | //div[@title='{ds}']"
                f" | //button[@aria-label='{ds}']",
                timeout=8)
            time.sleep(0.4)
            print(f"  → {label} 선택: {ds}")

        time.sleep(0.5)
        print(f"  → 날짜 설정: {self.start_str} ~ {self.end_str}")

    # ── 캠페인 드롭다운에서 모든 캠페인 선택 ──────────────────────
    def _select_all_campaigns(self):
        # 캠페인 선택 섹션 내의 드롭다운 클릭
        # "캠페인을 선택하세요" 텍스트가 포함된 가장 구체적인 요소 클릭
        dropdown = self._find(By.XPATH,
            "//*[contains(text(),'캠페인을 선택하세요')]"
            " | //*[@placeholder='캠페인을 선택하세요']")
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", dropdown)
        time.sleep(0.2)
        # 부모 클릭 가능한 요소 클릭
        self.driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(1)
        self.driver.save_screenshot(str(BASE_DIR / "debug_campaign_dropdown.png"))

        # "전체선택" 체크박스 클릭
        self._click(By.XPATH,
            "//*[contains(text(),'전체선택')]"
            " | //label[contains(.,'전체선택')]"
            " | //span[contains(.,'전체선택')]",
            timeout=8)
        time.sleep(0.5)
        print("  → 전체선택 완료")

        # "확인" 버튼으로 드롭다운 닫기
        self._click(By.XPATH,
            "//button[normalize-space(text())='확인']"
            " | //button[contains(@class,'confirm') and contains(.,'확인')]",
            timeout=8)
        time.sleep(0.5)
        print("  → 캠페인 드롭다운 확인")

    # ── 폼 설정 + 보고서 만들기 클릭 ────────────────────────────
    def _request_report(self, structure: str):
        self._set_dates()

        # "일별" 라디오
        self._click(By.XPATH,
            "//label[normalize-space(text())='일별']"
            " | //span[normalize-space(text())='일별'][ancestor::label]")
        time.sleep(0.3)

        # 캠페인 선택
        self._select_all_campaigns()

        # 보고서 구조 라디오 (구조 텍스트로 선택, 없으면 건너뜀)
        try:
            self._click(By.XPATH,
                f"//label[contains(.,'{structure}')]"
                f" | //span[contains(.,'{structure}')][ancestor::label]",
                timeout=8)
            time.sleep(0.3)
        except Exception:
            print(f"  → 보고서 구조 선택 건너뜀 ('{structure}' 없음)")

        # 스크린샷: 보고서 만들기 클릭 전
        self.driver.save_screenshot(str(BASE_DIR / "debug_before_create.png"))

        # "보고서 만들기" 버튼
        self._click(By.XPATH,
            "//button[contains(.,'보고서 만들기')]"
            " | //button[contains(.,'보고서 요청')]"
            " | //button[contains(.,'생성')]")
        print("  → '보고서 만들기' 클릭")

    # ── 생성 완료 대기 + 다운로드 클릭 ──────────────────────────
    def _wait_and_download(self):
        print("  → 생성 대기 중... (최대 300초)")
        deadline = time.time() + 300
        dl_btn = None

        while time.time() < deadline:
            self._try_click(By.XPATH,
                "//button[contains(.,'새로 고침')]"
                " | //button[contains(.,'refresh')]"
                " | //*[@title='새로 고침']", timeout=2)
            time.sleep(3)

            rows = self.driver.find_elements(By.XPATH,
                "//table//tbody//tr"
                " | //div[@role='row']"
                " | //*[contains(@class,'ant-table-row')]")

            for row in rows:
                rt = row.text
                # 오늘 날짜 + 우리 시작일 + 일별(합계 아님) + 완료
                if self.today_str not in rt:
                    continue
                if self.start_str not in rt:
                    continue
                if "[합계]" in rt:
                    continue
                if "생성 완료" not in rt and "완료" not in rt:
                    continue
                row_btns = row.find_elements(By.XPATH, ".//button | .//a")
                for btn in row_btns:
                    if "다운" in btn.text:
                        dl_btn = btn
                        break
                if dl_btn is None and row_btns:
                    dl_btn = row_btns[-1]
                if dl_btn:
                    break

            if dl_btn:
                break

        if not dl_btn:
            self.driver.save_screenshot(str(BASE_DIR / "debug_wait_timeout.png"))
            raise TimeoutError("보고서 생성 300초 초과")

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", dl_btn)
        time.sleep(0.5)
        dl_btn.click()
        print("  → 다운로드 클릭")

    # ── 파일 완료 감지 ───────────────────────────────────────────
    def _wait_for_file(self, timeout: int = 60) -> Path | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            files = [f for f in DOWNLOAD_TMP.glob("*.xlsx")
                     if not f.name.endswith(".crdownload")]
            if files:
                newest = max(files, key=lambda f: f.stat().st_mtime)
                if time.time() - newest.stat().st_mtime >= 1:
                    return newest
            time.sleep(1)
        return None

    # ── RAW 폴더로 이동 ──────────────────────────────────────────
    def _move_to_raw(self, src: Path, ad_type: str) -> Path:
        dest_dir = RAW_DIRS[ad_type]
        dest_dir.mkdir(parents=True, exist_ok=True)
        # 같은 기간 기존 파일 덮어쓰기
        s = self.start_date.strftime("%Y%m%d")
        e = self.end_date.strftime("%Y%m%d")
        for old in dest_dir.glob(f"*{s}*{e}*.xlsx"):
            old.unlink()
        dest = dest_dir / src.name
        shutil.move(str(src), str(dest))
        return dest

    # ── 광고 유형 1개 처리 ───────────────────────────────────────
    def download_one(self, ad_type: str):
        cfg = REPORT_CONFIG[ad_type]
        print(f"\n▶ [{ad_type}]  {self.start_str} ~ {self.end_str}")

        self.driver.get(cfg["url"])
        time.sleep(4)

        self._request_report(cfg["structure"])
        self._wait_and_download()

        downloaded = self._wait_for_file()
        if downloaded:
            dest = self._move_to_raw(downloaded, ad_type)
            print(f"  ✓ 저장 완료: {dest.name}")
        else:
            print(f"  ✗ [{ad_type}] 파일 다운로드 타임아웃")

        # 다음 다운로드 전 tmp 폴더 비우기
        for f in DOWNLOAD_TMP.glob("*.xlsx"):
            f.unlink(missing_ok=True)

    # ── 전체 실행 ─────────────────────────────────────────────────
    def run(self):
        try:
            self.login()
            self.select_advertiser()
            for ad_type in ["PA", "NCA", "BA"]:
                self.download_one(ad_type)
            print("\n✅ 전체 다운로드 완료")
        except Exception as e:
            print(f"\n❌ 오류: {e}")
            self.driver.save_screenshot(str(BASE_DIR / "error_screenshot.png"))
            raise
        finally:
            self.driver.quit()


def main():
    today = date.today()

    if len(sys.argv) == 3:
        start = date.fromisoformat(sys.argv[1])
        end   = date.fromisoformat(sys.argv[2])
    elif len(sys.argv) == 2:
        end   = date.fromisoformat(sys.argv[1])
        start = end.replace(day=1)
    else:
        end   = today - timedelta(days=1)   # 어제
        start = today.replace(day=1)        # 이번 달 1일

    print(f"다운로드 기간: {start} ~ {end}")
    CoupangDownloader(start_date=start, end_date=end, headless=False).run()


if __name__ == "__main__":
    main()
