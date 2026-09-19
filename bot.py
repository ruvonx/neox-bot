import os
import time
import sqlite3
from threading import Thread, Lock
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

import telebot
from telebot import types

# ==========================================
# ⚙️ BOT & SERVER CONFIGURATION
# ==========================================
PORT = int(os.environ.get("PORT", 10000))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8843310193:AAH9ViXDNIi94hQnuZLjmiLe3UhtaaUM77U")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7241161752))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "neoxfastsms_bot")

# অটো ওটিপি এপিআই নিরাপদ রাখার সিক্রেট কি (আপনার ইচ্ছেমতো পরিবর্তন করতে পারেন)
API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "neox_secure_key_2026")

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 🗄️ DATABASE CONNECTION & THREAD SAFETY
# ==========================================
db_lock = Lock()
DB_FILE = "bot_users.db"

def get_db():
    """থ্রেড-সেফ ডাটাবেজ কানেকশন রিটার্ন করে"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ডাটাবেজ টেবিল ইনিশিয়ালাইজেশন
with db_lock:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            balance REAL DEFAULT 0.0, 
            total_otp INTEGER DEFAULT 0, 
            referrer INTEGER DEFAULT NULL
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            amount REAL, 
            method_details TEXT, 
            status TEXT DEFAULT 'PENDING'
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            country TEXT, 
            number TEXT UNIQUE, 
            status TEXT DEFAULT 'AVAILABLE', 
            assigned_user INTEGER DEFAULT NULL, 
            assigned_service TEXT DEFAULT 'FACEBOOK'
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, 
            val TEXT
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT UNIQUE
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            service_name TEXT, 
            display_name TEXT, 
            country_tag TEXT
        )''')
        conn.commit()

        # ডিফল্ট সার্ভিস ও কান্ট্রি লোড
        cursor.execute("SELECT COUNT(*) FROM services")
        if cursor.fetchone()[0] == 0:
            for s in ["FACEBOOK", "FB NEW CREATE", "TIKTOK"]:
                cursor.execute("INSERT OR IGNORE INTO services (name) VALUES (?)", (s,))
            
            default_countries = [
                ("FACEBOOK", "🇧🇯 Benin 638 🔥 (450)", "Benin"),
                ("FACEBOOK", "🇸🇩 Sudan FB 🔥 (874)", "Sudan"),
                ("FACEBOOK", "🇪🇬 Egypt S1 (9719)", "Egypt"),
                ("FACEBOOK", "🇲🇲 Myanmar Top (1166)", "Myanmar"),
                ("FACEBOOK", "🇧🇫 Burkina Faso (1792)", "Burkina"),
                ("FB NEW CREATE", "🇧🇯 Benin 638 🔥 (450)", "Benin"),
                ("FB NEW CREATE", "🇮🇹 Italy New FB (520)", "Italy"),
                ("TIKTOK", "🇳🇴 Norway TT (2547)", "Norway"),
                ("TIKTOK", "🇳🇵 Nepal TikTok (1752)", "Nepal")
            ]
            for s_name, d_name, c_tag in default_countries:
                cursor.execute("INSERT INTO countries (service_name, display_name, country_tag) VALUES (?, ?, ?)", 
                               (s_name, d_name, c_tag))
            conn.commit()

# ==========================================
# ⚙️ HELPER FUNCTIONS (SETTINGS & USERS)
# ==========================================
def get_setting(key, default_val):
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT val FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                return row["val"]
            cur.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(default_val)))
            conn.commit()
            return str(default_val)

def set_setting(key, val):
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(val)))
            conn.commit()

# ডিফল্ট সেটিংস নিশ্চিতকরণ
get_setting("support_link", "https://t.me/jaazadmin")
get_setting("otp_group", "https://t.me/jaazadmin")
get_setting("min_withdraw", "0.50")
get_setting("otp_rate", "0.010")
get_setting("msg_sel_service", "🚦 <b>Select a service:</b> 📥")
get_setting("msg_sel_country", "🌍 <b>Select your country:</b> 📥")
get_setting("msg_assigned", "📱 <b>{country} Number Assigned:</b>\n\n🌟 <b>Waiting For OTP:</b>")
get_setting("msg_no_number", "⚠️ <b>দুঃখিত! বর্তমানে {country} দেশের কোনো চালু নাম্বার খালি নেই।</b>\n\nদয়া করে অন্য কোনো দেশ নির্বাচন করুন অথবা অ্যাডমিনকে নাম্বার লোড করতে বলুন।")

def get_support_message():
    custom = get_setting("msg_support_custom", "")
    if custom:
        return custom
    return (
        "🛡️ <b>NEOX SUPPORT</b>\n\n"
        "If You Need Any Help\n"
        "Message On Support Team\n\n"
        "⤵️ <b>All Time Available</b>"
    )

def get_live_traffic_message():
    custom = get_setting("msg_traffic_custom", "")
    if custom:
        return custom
    return (
        "🟢 <b>Live Traffic</b>\n\n"
        "📅 <b>Window:</b> Last 5 minutes\n"
        "🎯 <b>Results Sent:</b> 100%\n"
        "🔝 <b>Top Country:</b> 🇸🇳 Senegal Top 🔥\n\n"
        "🌍 <b>Top Countries:</b>\n"
        "1. 🇸🇳 Senegal Top 🔥 — 47.8%\n"
        "2. 🇸🇳 Senegal FB — 26.1%\n"
        "3. 🇳🇴 Norway TT — 21.7%\n"
        "4. 🇲🇲 Myanmar FB — 4.3%"
    )

def get_user(user_id, ref_id=None):
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT balance, total_otp, referrer FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                ref = int(ref_id) if ref_id and str(ref_id).isdigit() and int(ref_id) != user_id else None
                cur.execute("INSERT INTO users (user_id, balance, total_otp, referrer) VALUES (?, 0.0, 0, ?)", (user_id, ref))
                conn.commit()
                return 0.0, 0, ref
            return float(row["balance"]), int(row["total_otp"]), row["referrer"]

def update_balance(user_id, amount, otp_inc=0):
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT balance, total_otp, referrer FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO users (user_id, balance, total_otp) VALUES (?, 0.0, 0)", (user_id,))
                bal, otps, ref = 0.0, 0, None
            else:
                bal, otps, ref = float(row["balance"]), int(row["total_otp"]), row["referrer"]

            new_bal = max(0.0, bal + amount)
            new_otps = otps + otp_inc
            cur.execute("UPDATE users SET balance = ?, total_otp = ? WHERE user_id = ?", (new_bal, new_otps, user_id))
            
            # ১০টি ওটিপি সম্পন্ন হলে রেফারেল বোনাস লজিক
            if otp_inc > 0 and new_otps == 10 and ref:
                cur.execute("UPDATE users SET balance = balance + 0.10 WHERE user_id = ?", (ref,))
                conn.commit()
                try:
                    bot.send_message(ref, "🎉 <b>অভিনন্দন!</b> আপনার একজন রেফারেল ১০টি OTP সম্পন্ন করায় আপনি <b>$0.1000</b> বোনাস পেয়েছেন!", parse_mode="HTML")
                except:
                    pass
            else:
                conn.commit()

            return new_bal

def cancel_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel (বাতিল)", callback_data="cancel_action"))
    return markup

def make_copy_btn(num_str):
    num_clean = str(num_str).strip()
    try:
        if hasattr(types, 'CopyTextButton'):
            return types.InlineKeyboardButton(f"📞  {num_clean}", copy_text=types.CopyTextButton(text=num_clean))
    except:
        pass
    return types.InlineKeyboardButton(f"📞  {num_clean}", callback_data=f"copy_{num_clean}")

# ==========================================
# 🌐 WEB SERVER & AUTO-OTP DISPATCH
# ==========================================
def dispatch_otp_auto(num, code, full_msg=None):
    try:
        clean_num = num.strip().replace(" ", "").replace("-", "")
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, assigned_user, assigned_service FROM numbers WHERE number LIKE ? AND status = 'ASSIGNED'", (f"%{clean_num[-8:]}%",))
                res = cur.fetchone()

                if res and res["assigned_user"]:
                    num_id = res["id"]
                    target_user = res["assigned_user"]
                    service_name = res["assigned_service"] if res["assigned_service"] else "FACEBOOK"
                    
                    # নাম্বারটি ডিলিট করে দেওয়া যাতে পুনরায় ব্যবহার না হয়
                    cur.execute("DELETE FROM numbers WHERE id = ?", (num_id,))
                    conn.commit()
                else:
                    return False

        otp_rate = float(get_setting("otp_rate", "0.010"))
        new_bal = update_balance(target_user, otp_rate, otp_inc=1)
        bdt_earned = otp_rate * 120

        if not full_msg:
            full_msg = f"<#> {code} est votre code {service_name} H29Q+Fsn4Sr"

        otp_text = (
            f"✓ <b>OTP Received!</b>\n"
            f"📲 <b>Number:</b> <code>{clean_num}</code>\n"
            f"🔑 <b>OTP Code:</b> <code>{code}</code>\n"
            f"🛠 <b>Service:</b> {service_name}\n"
            f"✉️ <b>Full Message:</b>\n"
            f"<pre><code class=\"language-powershell\">{full_msg}</code></pre>\n\n"
            f"💸 <b>Earned:</b> ৳{bdt_earned:.2f} (${otp_rate:.3f})"
        )

        bot.send_message(target_user, otp_text, parse_mode="HTML")
        bot.send_message(ADMIN_ID, f"⚡ <b>[Auto-OTP]</b> ইউজার <code>{target_user}</code> ওটিপি পেয়েছে!\n📲 <code>{clean_num}</code> | 🔑 <code>{code}</code>", parse_mode="HTML")
        return True
    except Exception as e:
        print("Dispatch error:", e)
        return False

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/auto-otp":
            params = parse_qs(parsed.query)
            secret = params.get('secret', [None])[0]
            
            # সিকিউরিটি চেক
            if secret != API_SECRET_KEY:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden: Invalid Secret Key")
                return

            num = params.get('num', [None])[0]
            code = params.get('code', [None])[0]
            full_msg = params.get('msg', [None])[0]
            if num and code:
                success = dispatch_otp_auto(num, code, full_msg)
                self.send_response(200 if success else 404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"OK" if success else b"Number Not Assigned")
                return
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing parameters")
                return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"NEOX FAST SMS Server Online 24/7")

    def log_message(self, format, *args):
        return

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# ==========================================
# 📱 KEYBOARDS & MENUS
# ==========================================
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("☎️ Get Number"), types.KeyboardButton("🌍 Available Country"))
    markup.add(types.KeyboardButton("📡 Support"), types.KeyboardButton("💰 Balance"))
    markup.add(types.KeyboardButton("😎 Withdraw"), types.KeyboardButton("🟢 Live Traffic"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ ADMIN PANEL"))
    return markup

def services_menu():
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM services")
            svcs = cur.fetchall()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for row in svcs:
        name = row["name"]
        markup.add(types.InlineKeyboardButton(name, callback_data=f"svc_{name}"))
    return markup

def country_menu(service):
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT display_name, country_tag FROM countries WHERE service_name = ?", (service,))
            rows = cur.fetchall()
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(row["display_name"], callback_data=f"cnt_{row['country_tag']}_{service}") for row in rows]
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])

    markup.add(types.InlineKeyboardButton("🔙 Back to Services", callback_data="back_to_services"))
    return markup

# ==========================================
# 🤖 BOT COMMAND HANDLERS
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    args = message.text.split()
    ref_id = args[1].replace("ref_", "") if len(args) > 1 and "ref_" in args[1] else None
    get_user(message.chat.id, ref_id)
    
    welcome_text = (
        "╔═════════════════════╗\n"
        "   👑 ⚡ <b>NEOX FAST SMS</b>\n"
        "╚═════════════════════╝\n"
        "🚀 <b>Welcome to Number & OTP Service</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ <b>Choose an option below</b>\n"
        "<b>to continue using the bot.</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <b>Premium OTP Service</b>"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=main_menu(message.chat.id))

@bot.message_handler(commands=['otp'])
def admin_manual_otp(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        num = parts[1]
        code = parts[2]
        full_msg = " ".join(parts[3:]) if len(parts) > 3 else None
        if not dispatch_otp_auto(num, code, full_msg):
            bot.send_message(ADMIN_ID, f"⚠️ এই নম্বরটি ({num}) বর্তমানে কারো কাছে সক্রিয় নেই!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ফরম্যাট: <code>/otp নম্বর কোড [মেসেজ]</code>", parse_mode="HTML")

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.send_message(message.chat.id, "🚫 <b>অপারেশনটি বাতিল করা হয়েছে!</b>", parse_mode="HTML", reply_markup=main_menu(message.chat.id))
    if message.chat.id == ADMIN_ID:
        show_admin_panel(message.chat.id)

# ==========================================
# 📩 TEXT / BUTTON HANDLERS
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_menu(message):
    chat_id = message.chat.id
    text = message.text

    if "Get Number" in text:
        msg_service = get_setting("msg_sel_service", "🚦 <b>Select a service:</b> 📥")
        bot.send_message(chat_id, msg_service, parse_mode="HTML", reply_markup=services_menu())

    elif "Available Country" in text:
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT country, COUNT(*) as cnt FROM numbers WHERE status = 'AVAILABLE' GROUP BY country")
                counts = cur.fetchall()
        c_text = "🌍 <b>Available Countries & Numbers:</b>\n\n"
        if counts:
            for row in counts:
                c_text += f"• <b>{row['country']}</b>: <code>{row['cnt']}</code> টি নাম্বার সচল আছে\n"
        else:
            c_text += "বর্তমানে পুলে কোনো নাম্বার খালি নেই।"
        bot.send_message(chat_id, c_text, parse_mode="HTML")

    elif "Support" in text:
        supp_link = get_setting("support_link", "https://t.me/jaazadmin")
        supp_text = get_support_message()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎧 24/7 NEOX SUPPORT", url=supp_link))
        bot.send_message(chat_id, supp_text, parse_mode="HTML", reply_markup=markup)

    elif "Balance" in text:
        bal, otps, _ = get_user(chat_id)
        bdt_val = int(bal * 120)
        
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM users WHERE referrer = ? AND total_otp >= 10", (chat_id,))
                ref_count = cur.fetchone()[0]

        ref_url = f"https://t.me/{BOT_USERNAME}?start=ref_{chat_id}"
        bal_text = (
            f"😎 <b>Balance:</b> ${bal:.4f} ≈ {bdt_val} BDT\n"
            f"💬 <b>Referral Link:</b> <code>{ref_url}</code>\n"
            f"🟢 <b>Confirmed Referrals:</b> {ref_count}\n"
            f"💲 <b>Per Refer Earn:</b> $0.1000\n\n"
            f"ℹ️ <b>Referral Info:</b> রেফারেল তখন কনফার্ম হবে যখন ব্যবহারকারী ১০টি OTP সফলভাবে গ্রহণ করবেন।"
        )

        markup = types.InlineKeyboardMarkup()
        try:
            if hasattr(types, 'CopyTextButton'):
                markup.add(types.InlineKeyboardButton("👤 Copy Referral Link", copy_text=types.CopyTextButton(text=ref_url)))
            else:
                markup.add(types.InlineKeyboardButton("👤 Copy Referral Link", callback_data=f"copy_ref_{chat_id}"))
        except:
            markup.add(types.InlineKeyboardButton("👤 Copy Referral Link", callback_data=f"copy_ref_{chat_id}"))

        bot.send_message(chat_id, bal_text, parse_mode="HTML", reply_markup=markup)

    elif "Withdraw" in text:
        bal, _, _ = get_user(chat_id)
        min_w = float(get_setting("min_withdraw", "0.50"))
        if bal < min_w:
            bot.send_message(chat_id, f"❌ <b>উইথড্র করার জন্য ন্যূনতম ${min_w:.4f} প্রয়োজন।</b>\nআপনার বর্তমান ব্যালেন্স: ${bal:.4f}", parse_mode="HTML")
        else:
            msg = bot.send_message(chat_id, f"💳 <b>আপনার পেমেন্ট তথ্য দিন:</b>\nবর্তমান ব্যালেন্স: <b>${bal:.4f}</b>\n\nবিকাশ / নগদ নম্বর অথবা Binance Pay ID লিখে পাঠান:", parse_mode="HTML", reply_markup=cancel_markup())
            bot.register_next_step_handler(msg, process_withdraw)

    elif "Live Traffic" in text:
        live_msg = get_live_traffic_message()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"))
        bot.send_message(chat_id, live_msg, parse_mode="HTML", reply_markup=markup)

    elif text == "⚙️ ADMIN PANEL" and chat_id == ADMIN_ID:
        show_admin_panel(chat_id)

def process_withdraw(message):
    chat_id = message.chat.id
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        bot.send_message(chat_id, "🚫 উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে।")
        return

    details = message.text.strip()
    bal, _, _ = get_user(chat_id)
    min_w = float(get_setting("min_withdraw", "0.50"))

    # রিয়েল-টাইম ব্যালেন্স ভ্যালিডেশন (Race condition প্রতিরোধে)
    if bal < min_w:
        bot.send_message(chat_id, f"❌ <b>ব্যালেন্স অপর্যাপ্ত!</b>\nন্যূনতম: ${min_w:.4f} | আপনার আছে: ${bal:.4f}", parse_mode="HTML")
        return

    # ব্যালেন্স কেটে নেওয়া হচ্ছে
    update_balance(chat_id, -bal)
    
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO withdrawals (user_id, amount, method_details, status) VALUES (?, ?, ?, 'PENDING')",
                        (chat_id, bal, details))
            w_id = cur.lastrowid
            conn.commit()

    bot.send_message(chat_id, f"✅ <b>উইথড্র রিকোয়েস্ট সফল হয়েছে!</b>\nপরিমাণ: <b>${bal:.4f}</b>\nঅ্যাডমিন দ্রুত পেমেন্ট সম্পন্ন করবেন।", parse_mode="HTML")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"wapp_{w_id}_{chat_id}_{bal}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"wrej_{w_id}_{chat_id}_{bal}")
    )

    bot.send_message(
        ADMIN_ID,
        f"🚨 <b>নতুন উইথড্র রিকোয়েস্ট #{w_id}!</b>\n\n"
        f"👤 ইউজার: <code>{chat_id}</code>\n"
        f"💵 পরিমাণ: <b>{bal:.4f} USDT</b>\n"
        f"📝 অ্যাকাউন্ট: <code>{details}</code>",
        parse_mode="HTML",
        reply_markup=markup
    )

# ==========================================
# 👑 ADMIN PANEL & CALLBACKS
# ==========================================
def show_admin_panel(chat_id):
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(balance), SUM(total_otp) FROM users")
            stats = cur.fetchone()
            total_users = stats[0] or 0
            total_bal = stats[1] or 0.0
            total_otps = stats[2] or 0

            cur.execute("SELECT COUNT(*) FROM numbers WHERE status = 'AVAILABLE'")
            avail_num = cur.fetchone()[0]

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 Edit Texts", callback_data="adm_menu_texts"),
        types.InlineKeyboardButton("📂 Services", callback_data="adm_mng_svc")
    )
    markup.add(
        types.InlineKeyboardButton("🌐 Countries", callback_data="adm_mng_cnt"),
        types.InlineKeyboardButton("➕ Add Numbers", callback_data="adm_add_num")
    )
    markup.add(
        types.InlineKeyboardButton("📋 Number Pool", callback_data="adm_list_num"),
        types.InlineKeyboardButton("🎧 Support Link", callback_data="adm_set_supp")
    )
    markup.add(
        types.InlineKeyboardButton("📢 OTP Group Link", callback_data="adm_set_group"),
        types.InlineKeyboardButton("💵 Min Withdraw", callback_data="adm_set_minw")
    )
    markup.add(
        types.InlineKeyboardButton("🎁 Set OTP Rate", callback_data="adm_set_rate"),
        types.InlineKeyboardButton("➕ Add/Cut Bal", callback_data="adm_addbal")
    )
    markup.add(
        types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")
    )

    admin_text = (
        f"👑 <b>A-Z DYNAMIC CONTROL PANEL</b> 👑\n\n"
        f"👥 মোট ইউজার: <b>{total_users} জন</b>\n"
        f"💰 মোট ইউজার ফান্ড: <b>${total_bal:.3f}</b>\n"
        f"📬 মোট ওটিপি সম্পন্ন: <b>{total_otps} টি</b>\n"
        f"📱 পুলে সচল আসল নাম্বার: <b>{avail_num} টি</b>\n"
    )
    bot.send_message(chat_id, admin_text, reply_markup=markup, parse_mode="HTML")

def edit_texts_menu(chat_id, message_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("1. 🚦 Select Service Text", callback_data="edt_msg_sel_service"),
        types.InlineKeyboardButton("2. 🌍 Select Country Text", callback_data="edt_msg_sel_country"),
        types.InlineKeyboardButton("3. 📱 Number Assigned Text", callback_data="edt_msg_assigned"),
        types.InlineKeyboardButton("4. 🎧 Support Message", callback_data="edt_msg_support"),
        types.InlineKeyboardButton("5. 🟢 Live Traffic Message", callback_data="edt_msg_traffic"),
        types.InlineKeyboardButton("6. ⚠️ No Numbers Alert", callback_data="edt_msg_no_number"),
        types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main")
    )
    bot.edit_message_text(
        "📝 <b>কোন লেখাটি এডিট করতে চান?</b> নির্বাচন করুন:",
        chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data == "cancel_action":
        bot.clear_step_handler_by_chat_id(chat_id)
        bot.answer_callback_query(call.id, text="বাতিল করা হয়েছে!")
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
        bot.send_message(chat_id, "🚫 <b>অপারেশনটি বাতিল করা হয়েছে!</b>", parse_mode="HTML")
        if chat_id == ADMIN_ID:
            show_admin_panel(chat_id)
        return

    if call.data.startswith("svc_"):
        service = call.data.replace("svc_", "")
        bot.answer_callback_query(call.id)
        msg_country = get_setting("msg_sel_country", "🌍 <b>Select your country:</b> 📥")
        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=msg_country, parse_mode="HTML",
            reply_markup=country_menu(service)
        )

    elif call.data == "back_to_services":
        bot.answer_callback_query(call.id)
        msg_service = get_setting("msg_sel_service", "🚦 <b>Select a service:</b> 📥")
        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=msg_service, parse_mode="HTML",
            reply_markup=services_menu()
        )

    elif call.data.startswith("cnt_"):
        parts = call.data.split("_")
        country_tag, service = parts[1], parts[2]
        bot.answer_callback_query(call.id)

        try:
            with db_lock:
                with get_db() as conn:
                    cur = conn.cursor()
                    # পূর্ববর্তী অ্যাসাইন করা আন-ব্যবহৃত নাম্বার রিলিজ
                    cur.execute("UPDATE numbers SET status = 'AVAILABLE', assigned_user = NULL WHERE assigned_user = ?", (chat_id,))
                    
                    cur.execute(
                        "SELECT id, number FROM numbers WHERE status = 'AVAILABLE' AND (country LIKE ? OR country = ?) ORDER BY id ASC LIMIT 3", 
                        (f"%{country_tag}%", country_tag)
                    )
                    rows = cur.fetchall()
                    
                    if rows:
                        assigned_numbers = []
                        for row in rows:
                            cur.execute("UPDATE numbers SET status = 'ASSIGNED', assigned_user = ?, assigned_service = ? WHERE id = ?", 
                                        (chat_id, service, row["id"]))
                            assigned_numbers.append(row["number"])
                        conn.commit()

                        otp_group_link = get_setting("otp_group", "https://t.me/jaazadmin")
                        markup = types.InlineKeyboardMarkup(row_width=1)
                        for num in assigned_numbers:
                            markup.add(make_copy_btn(num))

                        markup.add(
                            types.InlineKeyboardButton("🔄 Change Number", callback_data=f"cnt_{country_tag}_{service}"),
                            types.InlineKeyboardButton("🌐 Change Country", callback_data=f"svc_{service}"),
                            types.InlineKeyboardButton("📢 OTP Group", url=otp_group_link)
                        )

                        assigned_tpl = get_setting("msg_assigned", "📱 <b>{country} Number Assigned:</b>\n\n🌟 <b>Waiting For OTP:</b>")
                        assigned_msg = assigned_tpl.replace("{country}", country_tag)
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=assigned_msg, parse_mode="HTML", reply_markup=markup)
                    else:
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 Choose Another Country", callback_data=f"svc_{service}"))
                        no_num_tpl = get_setting("msg_no_number", "⚠️ <b>বর্তমানে {country} দেশের কোনো চালু নাম্বার খালি নেই।</b>")
                        no_num_msg = no_num_tpl.replace("{country}", country_tag)
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=no_num_msg, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            print("Error assigning country/number:", e)

    elif call.data.startswith("copy_"):
        bot.answer_callback_query(call.id, text=f"Copied: {call.data.replace('copy_', '')}")

    elif call.data.startswith("copy_ref_"):
        bot.answer_callback_query(call.id, text="রেফারেল লিংক কপি হয়েছে!")

    elif call.data == "refresh_traffic":
        bot.answer_callback_query(call.id, text="Traffic refreshed!")
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"))
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=get_live_traffic_message(), parse_mode="HTML", reply_markup=markup)
        except:
            pass

    elif call.data.startswith("wapp_") and chat_id == ADMIN_ID:
        _, w_id, u_id, amt = call.data.split("_")
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (w_id,))
                conn.commit()
        bot.answer_callback_query(call.id, text="উইথড্র অ্যাপ্রুভ হয়েছে!")
        bot.edit_message_text(f"✅ <b>উইথড্র #{w_id} অ্যাপ্রুভ করা হয়েছে!</b>", chat_id, message_id, parse_mode="HTML")
        bot.send_message(int(u_id), f"🎉 <b>আপনার ${float(amt):.4f} উইথড্র সফলভাবে সম্পন্ন হয়েছে!</b>", parse_mode="HTML")

    elif call.data.startswith("wrej_") and chat_id == ADMIN_ID:
        _, w_id, u_id, amt = call.data.split("_")
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (w_id,))
                conn.commit()
        # রিজেক্ট হলে ব্যালেন্স ফেরত দেওয়া
        update_balance(int(u_id), float(amt))
        bot.answer_callback_query(call.id, text="উইথড্র বাতিল হয়েছে!")
        bot.edit_message_text(f"❌ <b>উইথড্র #{w_id} বাতিল এবং ব্যালেন্স ফেরত দেওয়া হয়েছে।</b>", chat_id, message_id, parse_mode="HTML")
        bot.send_message(int(u_id), f"⚠️ <b>আপনার উইথড্র বাতিল করা হয়েছে এবং ${float(amt):.4f} ব্যালেন্সে ফেরত দেওয়া হয়েছে।</b>", parse_mode="HTML")

    elif call.data == "adm_menu_texts" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        edit_texts_menu(chat_id, message_id)

    elif call.data.startswith("edt_") and chat_id == ADMIN_ID:
        txt_key = call.data.replace("edt_", "")
        bot.answer_callback_query(call.id)
        current_val = get_setting(txt_key, "টেক্সট খালি")
        msg = bot.send_message(
            chat_id,
            f"📝 <b>বর্তমান মেসেজ:</b>\n━━━━━━━━━━━━━━━━━━━━━\n{current_val}\n━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👉 <b>নতুন লেখাটি লিখে পাঠান:</b>",
            parse_mode="HTML", reply_markup=cancel_markup()
        )
        bot.register_next_step_handler(msg, lambda m: save_text_and_notify(m, txt_key))

    elif call.data == "adm_mng_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM services")
                svcs = [row["name"] for row in cur.fetchall()]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Service", callback_data="adm_add_svc"), types.InlineKeyboardButton("❌ Delete Service", callback_data="adm_del_svc"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main"))
        bot.edit_message_text(f"📂 <b>বর্তমান সার্ভিসসমূহ:</b>\n\n" + "\n".join([f"• <code>{s}</code>" for s in svcs]), chat_id, message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "adm_add_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "➕ নতুন সার্ভিসের নাম লিখে পাঠান (যেমন: <code>WHATSAPP</code>):", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_service)

    elif call.data == "adm_del_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "❌ যে সার্ভিসটি মুছে ফেলতে চান তার নাম লিখুন:", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_del_service)

    elif call.data == "adm_mng_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Country", callback_data="adm_add_cnt"), types.InlineKeyboardButton("❌ Delete Country", callback_data="adm_del_cnt"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main"))
        bot.edit_message_text("🌐 <b>দেশ ও রেঞ্জ ম্যানেজমেন্ট:</b>", chat_id, message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "adm_add_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        guide_text = "➕ <b>নতুন দেশ যোগ করার ফরম্যাট:</b>\n<code>সার্ভিস | বাটনের নাম | দেশের ট্যাগ</code>\n\nউদাহরণ:\n<code>FACEBOOK | 🇧🇯 Benin 638 🔥 (450) | Benin</code>"
        msg = bot.send_message(chat_id, guide_text, parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_country)

    elif call.data == "adm_del_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "❌ যে দেশের বাটনটি মুছতে চান তার ট্যাগ লিখুন (যেমন: <code>Benin</code>):", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_del_country)

    elif call.data == "adm_back_main" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        show_admin_panel(chat_id)

    elif call.data == "adm_add_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📱 দেশ ও নাম্বার পাঠান:\n<code>দেশ নম্বর১ নম্বর২ ...</code>\nউদাহরণ: <code>Benin +229656201 +229656202</code>", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_numbers)

    elif call.data == "adm_list_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT country, number, status FROM numbers LIMIT 25")
                nums = cur.fetchall()
        list_text = "📋 বটের নাম্বার পুল (সর্বোচ্চ ২৫টি):\n\n" + "\n".join([f"• <code>{r['number']}</code> ({r['country']}) - {r['status']}" for r in nums]) if nums else "কোনো নাম্বার নেই।"
        bot.send_message(chat_id, list_text, parse_mode="HTML")

    elif call.data == "adm_addbal" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "➕/➖ <b>ব্যালেন্স পরিবর্তন ফরম্যাট:</b> <code>UserID Amount</code>\nউদাহরণ: <code>12345678 0.50</code>", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_modify_user_balance)

    elif call.data == "adm_broadcast" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 ব্রডকাস্ট মেসেজটি লিখুন:", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_broadcast)

    elif call.data == "adm_set_supp" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🎧 নতুন সাপোর্ট লিংক পাঠান:\n(যেমন: <code>https://t.me/jaazadmin</code>)", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "support_link", "সাপোর্ট লিংক"))

    elif call.data == "adm_set_group" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 নতুন OTP Group লিংক পাঠান:\n(যেমন: <code>https://t.me/YourGroup</code>)", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "otp_group", "OTP Group লিংক"))

    elif call.data == "adm_set_minw" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "💵 নতুন মিনিমাম উইথড্র অ্যামাউন্ট (ডলারে):", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "min_withdraw", "মিনিমাম উইথড্র"))

    elif call.data == "adm_set_rate" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🎁 প্রতি ওটিপির রেট (ডলারে):", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "otp_rate", "প্রতি ওটিপির রেট"))

# ==========================================
# 🛠️ ADMIN STEP HANDLERS
# ==========================================
def do_modify_user_balance(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = message.text.split()
        target_uid = int(parts[0])
        amt = float(parts[1])
        new_b = update_balance(target_uid, amt)
        bot.send_message(ADMIN_ID, f"✅ ইউজার <code>{target_uid}</code>-এর নতুন ব্যালেন্স: <b>${new_b:.4f}</b>", parse_mode="HTML")
        try:
            action = "যোগ" if amt >= 0 else "কর্তন"
            bot.send_message(target_uid, f"🔔 অ্যাডমিন আপনার অ্যাকাউন্টে <b>${abs(amt):.4f}</b> {action} করেছেন।\nবর্তমান ব্যালেন্স: <b>${new_b:.4f}</b>", parse_mode="HTML")
        except:
            pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ ভুল ফরম্যাট! উদাহরণ: <code>12345678 0.50</code>", parse_mode="HTML")
    show_admin_panel(ADMIN_ID)

def save_text_and_notify(message, txt_key):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    if txt_key == "msg_traffic":
        set_setting("msg_traffic_custom", message.text.strip())
    elif txt_key == "msg_support":
        set_setting("msg_support_custom", message.text.strip())
    else:
        set_setting(txt_key, message.text.strip())
    bot.send_message(ADMIN_ID, "✅ <b>মেসেজটি সফলভাবে আপডেট করা হয়েছে!</b>", parse_mode="HTML")
    show_admin_panel(ADMIN_ID)

def do_add_service(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    s_name = message.text.strip().upper()
    try:
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO services (name) VALUES (?)", (s_name,))
                conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সার্ভিস <b>{s_name}</b> যোগ করা হয়েছে!", parse_mode="HTML")
    except:
        bot.send_message(ADMIN_ID, "⚠️ এই সার্ভিসটি আগেই রয়েছে!", parse_mode="HTML")

def do_del_service(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    s_name = message.text.strip().upper()
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM services WHERE name = ?", (s_name,))
            cur.execute("DELETE FROM countries WHERE service_name = ?", (s_name,))
            conn.commit()
    bot.send_message(ADMIN_ID, f"✅ <b>{s_name}</b> সার্ভিস মুছে ফেলা হয়েছে!", parse_mode="HTML")

def do_add_country(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = [p.strip() for p in message.text.split("|")]
        s_name, d_name, c_tag = parts[0].upper(), parts[1], parts[2]
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO countries (service_name, display_name, country_tag) VALUES (?, ?, ?)", (s_name, d_name, c_tag))
                conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে <b>{s_name}</b> সার্ভিসে <b>{d_name}</b> যোগ হয়েছে!", parse_mode="HTML")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ফরম্যাট ভুল! উদাহরণ:\n<code>FACEBOOK | 🇧🇯 Benin 638 🔥 (450) | Benin</code>", parse_mode="HTML")

def do_del_country(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    c_tag = message.text.strip()
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM countries WHERE country_tag LIKE ?", (f"%{c_tag}%",))
            conn.commit()
    bot.send_message(ADMIN_ID, f"✅ <b>{c_tag}</b> দেশ মুছে ফেলা হয়েছে!", parse_mode="HTML")

def save_setting_and_notify(message, key, name):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    set_setting(key, message.text.strip())
    bot.send_message(ADMIN_ID, f"✅ <b>{name}</b> সফলভাবে আপডেট হয়েছে!", parse_mode="HTML")

def do_add_numbers(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = message.text.split()
        country = parts[0]
        number_list = parts[1:]
        added = 0
        with db_lock:
            with get_db() as conn:
                cur = conn.cursor()
                for num in number_list:
                    clean_n = num.strip().replace(" ", "").replace("-", "")
                    try:
                        cur.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country, clean_n))
                        added += 1
                    except:
                        pass
                conn.commit()
        bot.send_message(ADMIN_ID, f"✅ <b>{country}</b> দেশে <b>{added} টি নাম্বার</b> যুক্ত হয়েছে!", parse_mode="HTML")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট!", parse_mode="HTML")

def do_broadcast(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    with db_lock:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users")
            user_list = cur.fetchall()
    
    sent = 0
    for row in user_list:
        try:
            bot.send_message(row["user_id"], f"📢 <b>ADMIN NOTICE:</b>\n\n{message.text}", parse_mode="HTML")
            sent += 1
            time.sleep(0.04) # টেলিগ্রাম রেট লিমিট রক্ষা করতে বিরতি
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ ব্রডকাস্ট সম্পন্ন! মোট <b>{sent}</b> জনের কাছে পাঠানো হয়েছে।", parse_mode="HTML")

# ==========================================
# 🚀 RUN BOT
# ==========================================
if __name__ == "__main__":
    print("NEOX FAST SMS [Production Setup] চালু হচ্ছে...")
    bot.infinity_polling(skip_pending=True)
