import os
import sys
import json
import time
import socket
import uuid
import requests
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "校园网自动登录助手"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "config.json")
GATEWAY_IP = "10.10.12.13"
CURRENT_VERSION = "1.0.0"
GITHUB_USER = "HAC-0"
GITHUB_REPO = "GMU-Auto-Campus-Login"

# GitHub 获取最新 Release 的 API
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"

session = requests.Session()
session.trust_env = False  # 防止代理拦截

def apply_update_and_restart(new_exe_path):
    """通过静默批处理覆盖旧文件并重启"""
    current_exe = os.path.abspath(sys.argv[0])
    bat_path = os.path.join(os.environ["TEMP"], "update_campus_login.bat")

    bat_content = f"""@echo off
timeout /t 1 /nobreak >nul
move /y "{new_exe_path}" "{current_exe}"
del "%~f0"
start "" "{current_exe}"
"""
    with open(bat_path, "w", encoding="gbk") as f:
        f.write(bat_content)

    subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    os._exit(0)

def check_for_updates():
    """从 GitHub Releases 检查并自动更新"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # 获取最新 Release 信息
        resp = session.get(LATEST_RELEASE_API, headers=headers, timeout=4)
        if resp.status_code != 200:
            return

        release_data = resp.json()
        latest_tag = release_data.get("tag_name", "").lstrip("v")  # 去掉 v1.0.1 前面的 v

        # 版本比对（如果 GitHub 上的版本高于当前版本）
        if latest_tag and latest_tag > CURRENT_VERSION:
            download_url = None
            # 找到 Release 中上传的 .exe 附件
            for asset in release_data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break

            if download_url:
                # 拼接国内镜像加速节点，确保没有梯子也能流畅下载
                mirror_url = f"https://ghfast.top/{download_url}"
                temp_new_exe = os.path.join(os.environ["TEMP"], "campus_login_latest.exe")

                dl_resp = session.get(mirror_url, timeout=20)
                if dl_resp.status_code == 200:
                    with open(temp_new_exe, "wb") as f:
                        f.write(dl_resp.content)
                    
                    # 触发替换重启
                    apply_update_and_restart(temp_new_exe)
    except Exception:
        # 网络抖动、访问受限时不影响正常登录流程
        pass
def set_startup(enable=True):
    """自动将程序加入 Windows 启动文件夹"""
    startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
    vbs_path = os.path.join(startup_dir, "AutoCampusLogin.vbs")
    current_exe = os.path.abspath(sys.argv[0])

    if enable:
        content = f'Set ws = CreateObject("Wscript.Shell")\nws.Run """{current_exe}""", 0'
        with open(vbs_path, "w", encoding="gbk") as f:
            f.write(content)
    else:
        if os.path.exists(vbs_path):
            os.remove(vbs_path)

def get_local_ip_and_mac():
    local_ip = "10.81.43.34"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((GATEWAY_IP, 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    mac_num = hex(uuid.getnode())[2:].zfill(12)
    return local_ip, mac_num

def is_online():
    """检测外网连通性"""
    test_urls = ["https://www.baidu.com", "https://connect.rom.miui.com/generate_204"]
    for url in test_urls:
        try:
            resp = session.get(url, timeout=2, allow_redirects=False)
            if resp.status_code in [200, 204]:
                return True
        except requests.RequestException:
            pass
    return False

def request_login(user, pwd, service):
    local_ip, local_mac = get_local_ip_and_mac()
    query_string = f"wlanuserip={local_ip}&wlanacname=HHXY_XXL2F_HUIJU&t=wireless-v2-plain&nasip=2.2.2.230&mac={local_mac}"

    url = f"http://{GATEWAY_IP}/eportal/InterFace.do?method=login"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Referer": f"http://{GATEWAY_IP}/eportal/index.jsp?{query_string}",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    payload = {
        "userId": user,
        "password": pwd,
        "service": service,
        "queryString": query_string,
        "passwordEncrypt": "false"
    }
    try:
        resp = session.post(url, data=payload, headers=headers, timeout=4)
        data = resp.json()
        if data.get("result") == "success":
            return True, "登录成功"
        return False, data.get("message", "认证失败")
    except Exception as e:
        return False, f"网络错误: {e}"

def request_logout():
    """主动向网关下线，清理网关残留/假在线状态"""
    local_ip, local_mac = get_local_ip_and_mac()
    url = f"http://{GATEWAY_IP}/eportal/InterFace.do?method=logout"
    try:
        session.post(url, data={"userIp": local_ip}, timeout=2)
    except Exception:
        pass

def show_config_gui(default_user="", default_service="电信", error_msg=""):
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("360x320")
    root.resizable(False, False)
    
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 180
    y = (root.winfo_screenheight() // 2) - 160
    root.geometry(f"360x320+{x}+{y}")

    style = ttk.Style()
    style.theme_use("vista" if "vista" in style.theme_names() else "default")

    frame = ttk.Frame(root, padding="20 15 20 15")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="校园网登录配置", font=("微软雅黑", 13, "bold"), foreground="#0078D4").pack(pady=(0, 10))

    if error_msg:
        ttk.Label(frame, text=error_msg, foreground="#D83B01", font=("微软雅黑", 9)).pack(pady=(0, 5))

    ttk.Label(frame, text="学号 / 账号:").pack(anchor=tk.W, pady=(5, 2))
    entry_user = ttk.Entry(frame, width=32)
    entry_user.insert(0, default_user)
    entry_user.pack(fill=tk.X)

    ttk.Label(frame, text="校园网密码:").pack(anchor=tk.W, pady=(8, 2))
    entry_pwd = ttk.Entry(frame, show="●", width=32)
    entry_pwd.pack(fill=tk.X)

    ttk.Label(frame, text="网络运营商:").pack(anchor=tk.W, pady=(8, 2))
    combo_service = ttk.Combobox(frame, values=["电信", "移动", "联通", "校园网"], state="readonly")
    combo_service.set(default_service)
    combo_service.pack(fill=tk.X, pady=(0, 10))

    saved_data = {}

    def on_save():
        user = entry_user.get().strip()
        pwd = entry_pwd.get().strip()
        service = combo_service.get()

        if not user or not pwd:
            messagebox.showwarning("提示", "学号与密码不能为空！")
            return

        saved_data["username"] = user
        saved_data["password"] = pwd
        saved_data["service"] = service

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(saved_data, f, ensure_ascii=False, indent=2)
        set_startup(True)

        messagebox.showinfo("成功", "配置已保存！\n程序正在连网，完成后将自动退出。")
        root.destroy()
        root.quit()

    ttk.Button(frame, text="保存并登录", command=on_save).pack(fill=tk.X, pady=(10, 0))
    root.mainloop()
    return saved_data

def get_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("username") and cfg.get("password"):
                    return cfg
        except Exception:
            pass
    return show_config_gui()

def exit_now():
    """强制彻底终结自身进程，绕过一切残留钩子"""
    try:
        session.close()
    except Exception:
        pass
    os._exit(0)

def main():
    cfg = get_config()
    if not cfg:
        exit_now()

    # 1. 如果外网已经通了，顺便静默检查更新，然后退出
    if is_online():
        check_for_updates()
        exit_now()

    # 2. 外网不通时，清理假会话并登录
    request_logout()
    time.sleep(1)

    for attempt in range(1, 6):
        request_login(cfg["username"], cfg["password"], cfg["service"])
        time.sleep(2)

        if is_online():
            check_for_updates()
            exit_now()

        request_logout()
        time.sleep(1)

    # 失败重置
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    show_config_gui(default_user=cfg.get("username", ""), default_service=cfg.get("service", "电信"), error_msg="连接失败，请检查账号密码")
    exit_now()

if __name__ == "__main__":
    main()