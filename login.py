import os
import json
import time
import sys
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import WebDriverException, NoSuchElementException

# ---------------- 配置 ----------------
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "campus_login_config.json"
LOGIN_URL = "http://172.19.0.1/"
CHROMEDRIVER_PATH = SCRIPT_DIR / "chromedriver.exe"

# 可调参数
MAX_WAIT_INPUT = 5.0      # 等待输入框最大时间（仅在未登录且需填写时生效）
CHECK_INTERVAL = 0.1      # 轮询间隔（秒）
MAX_WAIT_LOGIN_AFTER_SUBMIT = 3.0  # 提交后等待登录成功的最大时间（秒）
DOM_WAIT_TIMEOUT = 1.0    # 页面打开后等待 body.text 渲染的最大时间

# ---------------- 配置读取/保存 ----------------
def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("配置文件解析失败，将重新输入信息")
    return None

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def prompt_for_config():
    print("首次运行，请输入校园网登录信息（密码明文保存）")
    username = input("账号（学号/教职工号）: ").strip()
    password = input("密码: ").strip()
    print("请选择运营商：1 校园网  2 中国移动  3 中国联通  4 中国电信")
    isp_map = {"1": "", "2": "@cmcc", "3": "@unicom", "4": "@telecom"}
    while True:
        c = input("请输入对应数字: ").strip()
        if c in isp_map:
            isp = isp_map[c]
            break
        print("无效输入，请重试")
    cfg = {"username": username, "password": password, "isp": isp}
    save_config(cfg)
    return cfg

# ---------------- Chrome 选项 ----------------
def build_chrome_options(headless=False):
    opts = Options()
    opts.page_load_strategy = "eager"
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--log-level=3")
    return opts

# ---------------- 更稳健的已登录检测 ----------------
def dom_has_rendered(driver, min_len=5, timeout=DOM_WAIT_TIMEOUT):
    """等待 body.text 渲染到一定长度，避免在白屏/空 DOM 时误判"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            text = (body.text or "").strip()
            if len(text) >= min_len:
                return True
        except WebDriverException:
            pass
        time.sleep(0.05)
    # 即使未达到 min_len，也返回 False，调用方会继续轮询或检查元素存在
    return False

def is_logged_by_elements(driver):
    """
    更精确的判定登录成功（返回 True/False）。
    仅在页面已经渲染后调用才可靠。
    条件（任一满足则视为已登录）：
      - 存在 name="PageTips" 且文本包含 '成功' 或 '已成功登录' 等
      - 存在 name="logout" 的可见按钮（注销）
    """
    try:
        # 检查 PageTips
        try:
            el = driver.find_element(By.NAME, "PageTips")
            txt = (el.text or "").strip()
            if txt and ("成功" in txt or "已成功" in txt or "登录" in txt):
                return True
        except NoSuchElementException:
            pass

        # 检查 logout 按钮存在且可见
        try:
            logout = driver.find_element(By.NAME, "logout")
            if logout.is_displayed():
                return True
        except NoSuchElementException:
            pass

    except WebDriverException:
        # 任意 WebDriver 错误时保守返回 False
        pass
    return False

def is_logged_immediately(driver):
    """
    初步快速检查（不依赖大量渲染），用于页面刚打开时的快速判断。
    它先等待短时间 DOM 渲染（dom_has_rendered），然后用 is_logged_by_elements 判断。
    """
    # 等待 body.text 渲染到一定程度（避免白屏模板）
    dom_has_rendered(driver, min_len=1, timeout=DOM_WAIT_TIMEOUT)
    return is_logged_by_elements(driver)

def wait_for_login_after_submit(driver, timeout=MAX_WAIT_LOGIN_AFTER_SUBMIT):
    start = time.time()
    while time.time() - start < timeout:
        if is_logged_by_elements(driver):
            return True
        time.sleep(CHECK_INTERVAL)
    return False

# ---------------- 主登录流程 ----------------
def fast_login(cfg, headless=False):
    if not CHROMEDRIVER_PATH.exists():
        print(f"请将 chromedriver.exe 放在脚本目录：{CHROMEDRIVER_PATH}")
        sys.exit(2)

    service = Service(str(CHROMEDRIVER_PATH))
    driver = webdriver.Chrome(service=service, options=build_chrome_options(headless=headless))

    try:
        driver.get(LOGIN_URL)

        # ---------- 立即且可靠地判断已登录（避免无谓等待） ----------
        if is_logged_immediately(driver):
            print("已登录校园网，脚本退出")
            driver.quit()
            sys.exit(0)


        # ---------- 若未登录，等待输入框出现（轮询） ----------
        username_input = password_input = isp_select = None
        start = time.time()
        while time.time() - start < MAX_WAIT_INPUT:
            try:
                # 查找对应 name 的元素集合
                els_username = driver.find_elements(By.NAME, "DDDDD")
                els_password = driver.find_elements(By.NAME, "upass")
                els_isp = driver.find_elements(By.NAME, "ISP_select")

                if els_username and els_password and els_isp:
                    username_input = next((el for el in els_username if el.is_displayed()), None)
                    password_input = next((el for el in els_password if el.is_displayed()), None)
                    isp_select = next((el for el in els_isp if el.is_displayed()), None)
                    if username_input and password_input and isp_select:
                        break
            except WebDriverException:
                pass

            # 等待期间再次检测是否已登录（页面可能在这段时间被别的逻辑切换为已登录）
            if is_logged_by_elements(driver):
                print("检测到页面在等待期间已变为登录状态，脚本退出")
                driver.quit()
                sys.exit(0)

            time.sleep(CHECK_INTERVAL)

        # 如果输入框始终没出现，说明页面可能是已登录（但 earlier checks failed) 或页面加载异常
        if not (username_input and password_input and isp_select):
            # 最后再确认一次登录状态
            if is_logged_by_elements(driver):
                print("已登录校园网（2），脚本退出")
                driver.quit()
                sys.exit(0)
            else:
                print("页面可能加载失败或未能找到输入框（超时）")
                driver.quit()
                sys.exit(3)

        # ---------- 填充账号密码并选择 ISP ----------
        username_input.clear()
        username_input.send_keys(cfg["username"])
        password_input.clear()
        password_input.send_keys(cfg["password"])

        # 使用 Select 选择运营商，容错回退到 send_keys
        try:
            select = Select(isp_select)
            select.select_by_value(cfg.get("isp", ""))
        except Exception:
            try:
                isp_select.send_keys(cfg.get("isp", ""))
            except Exception:
                pass

        # ---------- 提交登录（调用页面函数） ----------
        try:
            driver.execute_script("if(typeof ee === 'function'){ ee(1); }")
        except WebDriverException:
            # JS 执行异常也继续等待页面变化（某些页面会自动提交 form）
            pass

        # ---------- 提交后等待并检测登录成功 ----------
        if wait_for_login_after_submit(driver):
            print("登录成功！")
            driver.quit()
            sys.exit(0)
        else:
            # 最后再做一次元素级别检查
            if is_logged_by_elements(driver):
                print("登录成功！(2)")
                driver.quit()
                sys.exit(0)
            else:
                print("登录失败，请检查账号/密码/运营商选择")
                driver.quit()
                sys.exit(4)

    except Exception as e:
        print("发生未处理异常：", repr(e))
        try:
            driver.quit()
        except Exception:
            pass
        sys.exit(5)

# ---------------- 主函数 ----------------
def main():
    cfg = load_config() or prompt_for_config()
    fast_login(cfg, headless=False)  # headless=True 可后台运行

if __name__ == "__main__":
    main()
