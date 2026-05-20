import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from gtts import gTTS
import time
import threading
import json
import os
import requests
import hashlib
import pickle
from colorama import init, Fore, Style

# ================= FILES =================
AMBIL_FILE = "file/ambil_nomor.json"
ADDNUM_API_URL = "https://ws.websocket.web.id/admin/addnumber"
ADDNUM_API_KEY = "112231"
SENT_CACHE_FILE = "sent_otp_cache.pkl"

os.makedirs("voice", exist_ok=True)
os.makedirs("file", exist_ok=True)

with open("flag.json", "r", encoding="utf-8") as f:
    FLAGS = json.load(f)
    
# ================= CONFIG =================
OWNER_ID = 8737366854
CHAT_ID = "-1003742958303"
BASE = "http://159.69.3.189"
LOGIN_URL = f"{BASE}/login"
TEST_SMS_URL = f"{BASE}/portal/sms/test/sms"
GET_RANGE_URL = f"{BASE}/portal/sms/received/getsms"
GET_NUMBER_URL = f"{BASE}/portal/sms/received/getsms/number"
GET_SMS_URL = f"{BASE}/portal/sms/received/getsms/number/sms"

BOT_TOKEN = "8870648512:AAFT7ecq26VxdOcTFte3HDdvOZdunv7LFh8"
GROUPS_FILE = "groups.json"

SERVICE_SHORT = {
    "WHATSAPP": "WS", "TELEGRAM": "TG", "GOOGLE": "GO",
    "FACEBOOK": "FB", "INSTAGRAM": "IG", "SHOPEE": "SP",
    "TOKOPEDIA": "TP", "GRAB": "GR", "GOJEK": "GJ", "TIKTOK": "TT"
}

sms_stats = {"total_sms": 0, "total_otp": 0, "total_number": set()}
sent_persistent_cache = set()
last_update_id = 0
init(autoreset=True)
accounts_lock = threading.Lock()
LOGIN_COOLDOWN = 300

# ================= PERSISTENT CACHE =================
def load_sent_cache():
    global sent_persistent_cache
    if os.path.exists(SENT_CACHE_FILE):
        try:
            with open(SENT_CACHE_FILE, "rb") as f:
                sent_persistent_cache = pickle.load(f)
                print(Fore.GREEN + f"✅ Loaded {len(sent_persistent_cache)} cached OTPs")
        except Exception as e:
            print(Fore.RED + f"⚠️ Gagal load cache: {e}")
            sent_persistent_cache = set()
    else:
        sent_persistent_cache = set()

def save_sent_cache():
    try:
        with open(SENT_CACHE_FILE, "wb") as f:
            pickle.dump(sent_persistent_cache, f)
    except Exception as e:
        print(Fore.RED + f"⚠️ Gagal save cache: {e}")

def is_otp_sent(uid):
    return uid in sent_persistent_cache

def mark_otp_sent(uid):
    sent_persistent_cache.add(uid)
    save_sent_cache()

def reset_otp_cache():
    global sent_persistent_cache
    sent_persistent_cache = set()
    save_sent_cache()
    return "✅ Cache OTP berhasil direset!"

load_sent_cache()

# ================= GROUPS =================
def load_groups():
    if not os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "w") as f:
            json.dump({"groups": []}, f)
    try:
        with open(GROUPS_FILE, "r") as f:
            return json.load(f).get("groups", [])
    except:
        return []

def save_groups():
    with open(GROUPS_FILE, "w") as f:
        json.dump({"groups": groups}, f, indent=2)

groups = load_groups()
if CHAT_ID and str(CHAT_ID) not in groups:
    groups.append(str(CHAT_ID))
    save_groups()

# ================= ACCOUNTS =================
ACCOUNTS = [
    {
        "USERNAME": "davae5270@gmail.com",
        "PASSWORD": "dava0987.",
        "COOKIES": {
            "_fbp": "fb.1.1779039389687.981062339538478435",
            "XSRF-TOKEN": "eyJpdiI6Ijd1bEpRY2FBZDBac0VUZXpuYTYyVUE9PSIsInZhbHVlIjoiN01KZ2Y5K0I4RGphNE91MXdYNWxDdnppd01BL09DbllNSFZsbjQxQ2VscE00WjlTM0k5NGRtVnlCSmM5cmJqWjhrSzlmd0xoTXVvWEo1RHpFT3hNM3B5Z3RCeUpaaUhQdFVndzRVTkxiWnUwdG5reitKQkduRUJhQ1l2S05weUoiLCJtYWMiOiJiY2YxYzhiNzdlNmEzN2I1MmUzNDgwMzJmYWU2ZjM0NzA3N2M0ZGQwYmRhNGU5MjQ3NGVkZjM5NDNlYmQ1M2I3IiwidGFnIjoiIn0%3D",
            "ivas_sms_session": "eyJpdiI6IlBoZzczSEQzY2VlN2s1VXRpT1g1Y1E9PSIsInZhbHVlIjoiYXkvcktMQkowZWgxd09OSWFPOFlreUFabFB4SFM5Z0tUOXY2R1hXTDNIUVJKVHB1bW45SFZ2RlduemJWd1BCSXBKZnJYUlRTMXdRTTlYT0VJZzdvU3BLRklESWlOYTNWK3pDMXdNMGtaaElLMzJpRi9oSTdDMi9VSjkrYmdMeHIiLCJtYWMiOiJhMGFkY2FlYmQ1NWIwYjhmNTIzOWFlNWRkNmRlOTM1NzY0NGY2NGFkYjZjZmU2MDk5NWEyY2VkZTdkY2JhOTYxIiwidGFnIjoiIn0%3D"
        }
    },
]

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

accounts = []
for _acc in ACCOUNTS:
    _session = httpx.Client(follow_redirects=True, timeout=30)
    _session.headers.update(DEFAULT_HEADERS)
    for _name, _val in _acc["COOKIES"].items():
        if _val:
            _session.cookies.set(_name, _val)
    accounts.append({
        "USERNAME": _acc["USERNAME"],
        "PASSWORD": _acc["PASSWORD"],
        "COOKIES": dict(_acc["COOKIES"]),
        "session": _session,
        "csrf_token": "",
        "last_login": 0
    })

# ================= TELEGRAM UTILS =================
def send_msg(chat_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"Error send_msg: {e}")

def delete_msg(chat_id, message_id):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
            data={"chat_id": chat_id, "message_id": message_id},
            timeout=10
        )
    except:
        pass

def tg_send(msg, otp, chat_id=None):
    target_chat = chat_id if chat_id else CHAT_ID
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔑 COPY OTP", "copy_text": {"text": otp}}],
            [
                {"text": "DEVELOPER", "url": "t.me/davaofc4"},
                {"text": "CHANNEL", "url": "t.me/numberdavaofc"}
            ]
        ]
    }
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": target_chat, "text": msg, "parse_mode": "HTML", "reply_markup": keyboard},
            timeout=10
        )
    except Exception as e:
        print(f"Error tg_send: {e}")

def tg_active(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": OWNER_ID, "text": msg, "parse_mode": "HTML"}
    )

# ================= UTILS =================
def extract_otp(text):
    m = re.search(r"\b(\d{3}[- ]?\d{3}|\d{4,6})\b", text)
    return m.group(1) if m else None

def format_phone_number(number):
    number = str(number).replace("+", "").replace(" ", "")
    if len(number) >= 8:
        return f"{number[:3]}THAP{number[-4:]}"
    return number

def clean_country(rng):
    country = re.sub(r"\s*\(.*?\)", "", rng)
    country = re.sub(r"\d+", "", country)
    return country.strip().upper()

def extract_service_short(text):
    m = re.search(
        r"(WhatsApp|Telegram|Google|Facebook|Instagram|Shopee|Tokopedia|Grab|Gojek|TikTok)",
        text, re.I
    )
    if m:
        return SERVICE_SHORT.get(m.group(1).upper(), "Unknown")
    return "Unknown"

def mask_email(email):
    try:
        name, domain = email.split("@")
        masked = name[0] + "••••" + (name[-1] if len(name) > 2 else "")
        return f"{masked}@{domain}"
    except:
        return email

def get_flag(country):
    return FLAGS.get(country.upper(), "🏴‍☠️")

def normalize_number(num, country_code):
    num = str(num).strip().replace(" ", "").replace("-", "").replace("+", "")
    if num.startswith(country_code): return num
    if num.startswith("0"): return country_code + num[1:]
    return num

def parse_range(rng):
    country = re.sub(r"\s*\(.*?\)", "", rng)
    country = re.sub(r"\d+", "", country)
    country = re.sub(r"\s+", " ", country).strip().upper()
    code_match = re.search(r"\((\d+)\)", rng)
    code = code_match.group(1) if code_match else ""
    return country, code

# ================= HELPER KEYBOARD AKUN =================
def make_accounts_keyboard(callback_prefix, extra=""):
    keyboard = {"inline_keyboard": []}
    for acc in accounts:
        email = acc["USERNAME"]
        label = mask_email(email)
        cb_data = f"{callback_prefix}|{extra}|{email}" if extra else f"{callback_prefix}|{email}"
        keyboard["inline_keyboard"].append([{"text": label, "callback_data": cb_data}])
    return keyboard

# ================= LOGIN =================
def login(acc):
    session = acc["session"]
    try:
        r = session.get(LOGIN_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        csrf_token = soup.find("input", {"name": "_token"})["value"]
        acc["csrf_token"] = csrf_token
        session.post(LOGIN_URL, data={
            "_token": csrf_token,
            "email": acc["USERNAME"],
            "password": acc["PASSWORD"]
        })
        print(f"[✓] Login Berhasil: {acc['USERNAME']}")
        return True
    except Exception as e:
        print(f"[X] Gagal login untuk {acc['USERNAME']}: {e}")
        return False

def ensure_login(acc):
    if not acc.get("csrf_token"):
        return login(acc)
    return True

# ================= GET DATA =================
def get_ranges(acc):
    today = datetime.now().strftime("%Y-%m-%d")
    r = acc["session"].post(GET_RANGE_URL, data={
        "_token": acc["csrf_token"], "from": today, "to": today
    })
    soup = BeautifulSoup(r.text, "html.parser")
    ranges = []
    for div in soup.find_all("div", onclick=True):
        if "toggleRange" in div["onclick"]:
            try: ranges.append(div["onclick"].split("'")[1])
            except: pass
    return list(set(ranges))

def get_numbers(acc, rng):
    today = datetime.now().strftime("%Y-%m-%d")
    r = acc["session"].post(GET_NUMBER_URL, data={
        "_token": acc["csrf_token"], "start": today, "end": today, "range": rng
    })
    soup = BeautifulSoup(r.text, "html.parser")
    numbers = []
    for div in soup.find_all("div", onclick=True):
        try:
            val = div["onclick"].split("'")[1]
            if val and val != rng: numbers.append(val)
        except: pass
    return list(set(numbers))

def get_sms(acc, rng, number):
    today = datetime.now().strftime("%Y-%m-%d")
    r = acc["session"].post(GET_SMS_URL, data={
        "_token": acc["csrf_token"], "start": today, "end": today,
        "Number": number, "Range": rng
    })
    soup = BeautifulSoup(r.text, "html.parser")
    sms_texts = [p.get_text(strip=True) for p in soup.find_all("p")]
    if not sms_texts:
        raw_text = soup.get_text(separator="\n", strip=True)
        if raw_text: sms_texts = raw_text.split('\n')
    return list(set(sms_texts))

# ================= CEK IVAS =================
def cek_ivas(chat_id=None):
    try:
        r = requests.get("http://ws.websocket.web.id/api/cekivas?platform=whatsapp", timeout=10)
        send_to = chat_id if chat_id else OWNER_ID
        if r.status_code != 200:
            send_msg(send_to, "❌ Gagal ambil data IVAS"); return
        data = r.json()
        if not data.get("success"):
            send_msg(send_to, "❌ API gagal"); return
        results = sorted(data.get("results", []), key=lambda x: x["count"], reverse=True)
        if not results:
            send_msg(send_to, "⚠️ Tidak ada data IVAS"); return
        msg = "📊 <b>CEK IVAS WHATSAPP</b>\n\n"
        for i, item in enumerate(results, 1):
            msg += f"{i}. {item.get('country','').upper()} : {item.get('count',0)} SMS\n"
        send_msg(send_to, msg)
    except Exception as e:
        send_msg(chat_id if chat_id else OWNER_ID, f"❌ Error: {e}")

# ================= STATSMS =================
def stats_sms(chat_id):
    msg = (
        "📊 <b>STATISTIK SMS OTP</b>\n\n"
        f"📩 Total SMS Masuk : {sms_stats['total_sms']}\n"
        f"🔑 Total OTP       : {sms_stats['total_otp']}\n"
        f"📞 Total Nomor     : {len(sms_stats['total_number'])}\n"
        f"👤 Total Akun      : {len(accounts)}\n"
        f"💾 Cache OTP       : {len(sent_persistent_cache)}\n"
    )
    send_msg(chat_id, msg)

# ================= ADD NUM =================
def addnum_api(target, email):
    from requests.exceptions import ConnectionError, Timeout
    MAX_RETRY = 3
    last_error = ""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            params = {"target": target, "email": email, "apikey": ADDNUM_API_KEY}
            r = requests.get(ADDNUM_API_URL, params=params, timeout=20)
            try: res = r.json()
            except: res = {}
            if r.status_code == 200:
                return True, res.get("target_number", target)
            return False, f"HTTP {r.status_code}"
        except ConnectionError as e:
            err_str = str(e)
            if "NameResolutionError" in err_str or "Name or service not known" in err_str:
                last_error = f"DNS gagal resolve host API (percobaan {attempt}/{MAX_RETRY})"
            else:
                last_error = f"Connection error ({attempt}/{MAX_RETRY}): {err_str[:80]}"
        except Timeout:
            last_error = f"Timeout ({attempt}/{MAX_RETRY})"
        except Exception as e:
            last_error = str(e)[:100]; break
        if attempt < MAX_RETRY: time.sleep(0)
    return False, last_error

def addnum_command(text, chat_id, msg_id):
    if not accounts:
        send_msg(chat_id, "❌ Tidak ada akun di ACCOUNTS")
        delete_msg(chat_id, msg_id); return
    parts = text.split()
    if len(parts) < 2:
        send_msg(chat_id, "❌ Format:\n/addnum SAUDI ARABIA 15022")
        delete_msg(chat_id, msg_id); return
    target = " ".join(parts[1:])
    keyboard = make_accounts_keyboard("ADDNUM", target)
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": f"📌 Pilih akun untuk add number:\n\n<b>{target}</b>",
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }
    )
    delete_msg(chat_id, msg_id)

# ================= DEL NUM ALL =================
def return_all_number(acc):
    try:
        r = acc["session"].post(
            f"{BASE}/portal/numbers/return/allnumber/bluck",
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{BASE}/portal/numbers", "Origin": BASE}
        )
        return (True, r.text) if r.status_code == 200 else (False, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)

def delnumall_command(chat_id):
    if not accounts:
        send_msg(chat_id, "❌ Tidak ada akun di ACCOUNTS"); return
    keyboard = make_accounts_keyboard("DELNUMALL")
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": "⚠️ Pilih akun untuk <b>return semua nomor</b>:",
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }
    )

# ================= AMBIL FILE =================
def export_numbers_ivas(chat_id, email):
    acc_target = next((a for a in accounts if a["USERNAME"] == email), None)
    if not acc_target:
        send_msg(chat_id, "❌ Akun tidak ditemukan"); return
    if not ensure_login(acc_target):
        send_msg(chat_id, "❌ Gagal login akun"); return
    session = acc_target["session"]
    try:
        r_home = session.get(f"{BASE}/portal/numbers")
        token_match = re.search(r'name="_token" value="(.*?)"', r_home.text)
        token = token_match.group(1) if token_match else acc_target.get("csrf_token", "")
        r = session.post(
            f"{BASE}/portal/numbers/export",
            data={"_token": token},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        if r.status_code != 200 or "login" in str(r.url):
            send_msg(chat_id, "❌ Gagal export / session expired"); return
        filename = f"ivas_export_{int(time.time())}.xlsx"
        filepath = f"file/{filename}"
        with open(filepath, "wb") as f:
            f.write(r.content)
        with open(filepath, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": chat_id, "caption": f"📊 <b>FILE IVAS</b>\n👤 {mask_email(email)}", "parse_mode": "HTML"},
                files={"document": (filename, f)}
            )
        os.remove(filepath)
    except Exception as e:
        send_msg(chat_id, f"❌ Error export: {e}")

def ambilfile_command(chat_id):
    if not accounts:
        send_msg(chat_id, "❌ Tidak ada akun di ACCOUNTS"); return
    keyboard = make_accounts_keyboard("EXPORT")
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": "📂 Pilih akun untuk <b>export nomor</b>:",
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }
    )

# ================= CEK RANGE =================
def cek_range_command(chat_id, text):
    try:
        parts = text.split()
        search_query = ""
        target_apps = ["WhatsApp", "Telegram"]
        if len(parts) > 1:
            first_arg = parts[1].upper()
            if first_arg in ["TG", "TELEGRAM", "#TG"]:
                target_apps = ["Telegram"]
                search_query = " ".join(parts[2:]).strip().upper()
            elif first_arg in ["WS", "WA", "WHATSAPP", "#WS"]:
                target_apps = ["WhatsApp"]
                search_query = " ".join(parts[2:]).strip().upper()
            else:
                search_query = " ".join(parts[1:]).strip().upper()

        acc_target = next((a for a in accounts if a.get("csrf_token")), None)
        if not acc_target:
            send_msg(chat_id, "❌ Tidak ada akun aktif"); return
        if not ensure_login(acc_target):
            send_msg(chat_id, "❌ Gagal login ke IVASMS"); return

        session = acc_target["session"]
        now_ms = int(time.time() * 1000)
        all_results_raw = []
        unique_ranges_count = set()

        for app_name in target_apps:
            params = {"app": app_name, "draw": "1", "start": "0", "length": "400",
                      "search[value]": search_query, "_": str(now_ms)}
            headers = {"X-Requested-With": "XMLHttpRequest",
                       "Accept": "application/json, text/javascript, */*; q=0.01",
                       "Referer": f"{BASE}/portal/sms/test/sms?app={app_name}"}
            resp = session.get(TEST_SMS_URL, params=params, headers=headers, timeout=30)
            items = resp.json().get("data", [])
            tag_service = "#WS" if app_name == "WhatsApp" else "#TG"

            for item in items:
                range_raw = item.get("range", "") if isinstance(item, dict) else ""
                if not range_raw: continue
                range_clean = BeautifulSoup(str(range_raw), "html.parser").text.strip()
                m = re.search(r"^(.*?)\s*\(?(\d{2,})\)?$", range_clean)
                country = m.group(1).strip().upper() if m else range_clean.strip().upper()
                code = m.group(2) if m else "N/A"
                if search_query and search_query not in country: continue
                if code != "N/A": unique_ranges_count.add(f"{tag_service}_{code}")

                all_text = BeautifulSoup(
                    " ".join([str(v) for v in (item.values() if isinstance(item, dict) else item)]),
                    "html.parser"
                ).text.strip().lower()
                m_sec = re.search(r"(\d+)\s*(sec|detik)", all_text)
                m_min = re.search(r"(\d+)\s*(min|menit)", all_text)
                m_hr  = re.search(r"(\d+)\s*(hour|jam)", all_text)
                diff = 0
                if "just now" in all_text or "baru saja" in all_text: diff = 0
                elif m_sec: diff = int(m_sec.group(1))
                elif m_min: diff = int(m_min.group(1)) * 60
                elif m_hr:  diff = int(m_hr.group(1)) * 3600
                all_results_raw.append({"diff": diff, "tag": tag_service, "country": country, "code": code})

        if not all_results_raw:
            send_msg(chat_id, "❌ Data tidak ditemukan."); return

        unique_map = {}
        for item in all_results_raw:
            key = (item["tag"], item["country"], item["code"])
            if key not in unique_map or item["diff"] < unique_map[key]["diff"]:
                unique_map[key] = item

        final = sorted(unique_map.values(), key=lambda x: x["diff"])
        lines = []
        for item in final:
            d = item["diff"]
            wt = f"{d} detik" if d < 60 else (f"{d//60} menit {d%60} detik" if d < 3600 else f"{d//3600} jam {(d%3600)//60} menit")
            lines.append(f"{item['tag']} {item['country']}  {item['code']}  {wt}")

        msg = f"📱 RANGE TERBARU ({len(unique_ranges_count)} unik):\n\n"
        msg += "\n".join(lines[:40])
        if len(lines) > 40: msg += f"\n\n... dan {len(lines)-40} lainnya"
        send_msg(chat_id, msg)

    except Exception as e:
        send_msg(chat_id, f"❌ Error cek range: {e}")

# ================= COMMAND LISTENER =================
def listen_command():
    global last_update_id
    while True:
        try:
            r = httpx.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 90}, timeout=120
            )
            data = r.json()

            for upd in data.get("result", []):
                last_update_id = upd["update_id"]

                # ===== CALLBACK =====
                if "callback_query" in upd:
                    try:
                        cb = upd["callback_query"]
                        data_cb = cb.get("data", "")
                        chat_id = cb["message"]["chat"]["id"]
                        msg_id  = cb["message"]["message_id"]

                        if data_cb.startswith("ADDNUM"):
                            _, target, email = data_cb.split("|", 2)
                            delete_msg(chat_id, msg_id)
                            success, result = addnum_api(target, email)
                            if success:
                                send_msg(chat_id, f"✅ ADD NUMBER BERHASIL\n📌 Range: {result}\n📧 {mask_email(email)}")
                            else:
                                send_msg(chat_id, f"❌ GAGAL: {result}")

                        elif data_cb.startswith("DELNUMALL"):
                            _, email = data_cb.split("|", 1)
                            delete_msg(chat_id, msg_id)
                            acc_target = next((a for a in accounts if a["USERNAME"] == email), None)
                            if not acc_target:
                                send_msg(chat_id, "❌ Akun tidak ditemukan"); continue
                            if not ensure_login(acc_target):
                                send_msg(chat_id, "❌ Gagal login akun"); continue
                            ok, res = return_all_number(acc_target)
                            if ok:
                                send_msg(chat_id, f"✅ DELETE ALL NUMBER BERHASIL\n📧 {mask_email(email)}")
                            else:
                                send_msg(chat_id, f"❌ GAGAL: {res[:100]}")

                        elif data_cb.startswith("EXPORT"):
                            _, email = data_cb.split("|", 1)
                            delete_msg(chat_id, msg_id)
                            export_numbers_ivas(chat_id, email)

                    except Exception as e:
                        print(f"Callback error: {e}")
                    continue

                if "message" not in upd:
                    continue

                msg  = upd["message"]
                text = msg.get("text", "") or ""
                user_id   = msg["from"]["id"]
                chat_id   = msg["chat"]["id"]
                chat_type = msg["chat"]["type"]
                msg_id    = msg["message_id"]

                # ===== PUBLIC =====
                if text == "/start":
                    send_msg(chat_id,
                        "🤖 <b>Bot OTP IVAS Aktif!</b>\n\n"
                        "/cekivas - Cek stok IVAS\n"
                        "/cekrange - Cek range terbaru\n"
                        "/statsms - Statistik OTP\n"
                        "/addnum - Add number\n"
                        "/delnumall - Return semua nomor\n"
                        "/ambilfile - Export nomor ke Excel"
                    )
                elif text.startswith("/cekivas"):
                    cek_ivas(chat_id)
                elif text.startswith("/statsms"):
                    stats_sms(chat_id)
                elif text.startswith("/cekrange"):
                    cek_range_command(chat_id, text)
                elif text.startswith("/addnum"):
                    addnum_command(text, chat_id, msg_id)
                elif text.startswith("/delnumall"):
                    delnumall_command(chat_id)
                elif text.startswith("/ambilfile"):
                    ambilfile_command(chat_id)
                elif text.startswith("/resetcache") and user_id == OWNER_ID:
                    send_msg(chat_id, reset_otp_cache())

        except httpx.TimeoutException:
            continue
        except Exception as e:
            print("ERROR LISTENER:", e)
        time.sleep(0)

# ================= BOT LOOP =================
def run_bot():
    for acc in accounts:
        acc["session"] = httpx.Client(
            follow_redirects=True, timeout=10,
            headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
        )
        acc["session"].cookies.update(acc["COOKIES"])
        acc["csrf_token"] = ""
        login(acc)

    print(Fore.GREEN + "[✓] Bot Berjalan..")
    print(Fore.YELLOW + f"📡 CHAT_ID: {CHAT_ID}")

    while True:
        for acc in accounts:
            try:
                if not acc.get("csrf_token"):
                    continue
                for rng in get_ranges(acc):
                    country = clean_country(rng)
                    flag = get_flag(country)
                    for num in get_numbers(acc, rng):
                        for sms in get_sms(acc, rng, num):
                            if "$" in sms and len(sms) < 15: continue
                            otp = extract_otp(sms)
                            if not otp: continue
                            uid = hashlib.md5(f"{num}-{otp}-{sms[:50]}".encode()).hexdigest()
                            if is_otp_sent(uid): continue
                            service = extract_service_short(sms)
                            msg = (
                                f"<b>{flag} {country} | {service} | {format_phone_number(num)}</b>\n"
                                f"<i>Penerima: {mask_email(acc['USERNAME'])}</i>\n"
                            )
                            tg_send(msg, otp)
                            mark_otp_sent(uid)
                            sms_stats["total_sms"] += 1
                            sms_stats["total_otp"] += 1
                            sms_stats["total_number"].add(num)
                            print(Fore.GREEN + f"[{acc['USERNAME']}] OTP Terkirim: {otp} → {num}")
                time.sleep(0)
            except Exception as e:
                print(Fore.RED + f"[ERROR {acc['USERNAME']}] {e}")
                time.sleep(0)
        time.sleep(0)

# ================= START =================
print(Fore.GREEN + "="*50)
print(Fore.GREEN + "🤖 BOT OTP DAVA STARTED!")
print(Fore.GREEN + "="*50)
print(Fore.YELLOW + f"📦 Loaded {len(sent_persistent_cache)} cached OTPs")
print(Fore.YELLOW + f"📡 CHAT_ID: {CHAT_ID}")
threading.Thread(target=listen_command, daemon=True).start()
run_bot()