import telebot
from telebot import types
import sqlite3
import time
import os
from urllib.parse import urlparse, parse_qs
from threading import Thread, Lock
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Render 24/7 Web Server ---
PORT = int(os.environ.get("PORT", 10000))

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/auto-otp":
            params = parse_qs(parsed.query)
            num = params.get('num', [None])[0]
            code = params.get('code', [None])[0]
            full_msg = params.get('msg', [None])[0]
            if num and code:
                dispatch_otp_auto(num, code, full_msg)
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"OK")
                return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"NEOX FAST SMS Online")
        
    def log_message(self, format, *args):
        return

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# --- Bot Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8843310193:AAH9ViXDNIi94hQnuZLjmiLe3UhtaaUM77U")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7241161752))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "neoxfastsms_bot")

bot = telebot.TeleBot(BOT_TOKEN)

# থ্রেড-সেফটি লক
db_lock = Lock()
conn = sqlite3.connect("bot_users.db", check_same_thread=False)
cursor = conn.cursor()

# টেবিলসমূহ তৈরি
with db_lock:
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, total_otp INTEGER DEFAULT 0, referrer INTEGER DEFAULT NULL
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, method_details TEXT, status TEXT DEFAULT 'PENDING'
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, number TEXT UNIQUE, status TEXT DEFAULT 'AVAILABLE', assigned_user INTEGER DEFAULT NULL, assigned_service TEXT DEFAULT 'FACEBOOK'
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, val TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS countries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, service_name TEXT, display_name TEXT, country_tag TEXT
    )''')
    conn.commit()

# ডিফল্ট সার্ভিস ও কান্ট্রি
with db_lock:
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
            cursor.execute("INSERT INTO countries (service_name, display_name, country_tag) VALUES (?, ?, ?)", (s_name, d_name, c_tag))
        conn.commit()

def get_setting(key, default_val):
    with db_lock:
        cursor.execute("SELECT val FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(default_val)))
        conn.commit()
        return str(default_val)

def set_setting(key, val):
    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(val)))
        conn.commit()

# ডিফল্ট সেটিংস লোড
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
    e_badge = '<tg-emoji emoji-id="5377676285864595613">🛡️</tg-emoji>'
    e_arrow = '<tg-emoji emoji-id="5197474438970363734">⤵️</tg-emoji>'
    return (
        f"{e_badge} <b>NEOX SUPPORT</b>\n\n"
        f"If You Need Any Help\n"
        f"Message On Support Team\n\n"
        f"{e_arrow} <b>All Time Available</b>"
    )

def get_live_traffic_message():
    custom_saved = get_setting("msg_traffic_custom", "")
    if custom_saved:
        return custom_saved

    e_trf = '<tg-emoji emoji-id="6276077203876745608">🟢</tg-emoji>'
    e_win = '<tg-emoji emoji-id="5413879192267805083">📅</tg-emoji>'
    e_res = '<tg-emoji emoji-id="6012782561737054888">🎯</tg-emoji>'
    e_top = '<tg-emoji emoji-id="6206090539989734881">🔝</tg-emoji>'
    e_senegal = '<tg-emoji emoji-id="5434001565021123877">🇸🇳</tg-emoji>'
    e_fire = '<tg-emoji emoji-id="5204382305455467942">🔥</tg-emoji>'
    e_norway = '<tg-emoji emoji-id="5434147542369579483">🇳🇴</tg-emoji>'
    e_myanmar = '<tg-emoji emoji-id="5433666360003540231">🇲🇲</tg-emoji>'

    return (
        f"{e_trf} <b>Live Traffic</b>\n\n"
        f"{e_win} <b>Window:</b> Last 5 minutes\n"
        f"{e_res} <b>Results Sent:</b> 100%\n"
        f"{e_top} <b>Top Country:</b> {e_senegal} Senegal Top {e_fire}\n\n"
        f"🌍 <b>Top Countries:</b>\n"
        f"1. {e_senegal} Senegal Top {e_fire} — 47.8%\n"
        f"2. {e_senegal} Senegal FB — 26.1%\n"
        f"3. {e_norway} Norway TT — 21.7%\n"
        f"4. {e_myanmar} Myanmar FB — 4.3%"
    )

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

def get_user(user_id, ref_id=None):
    with db_lock:
        cursor.execute("SELECT balance, total_otp, referrer FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            ref = int(ref_id) if ref_id and str(ref_id).isdigit() and int(ref_id) != user_id else None
            cursor.execute("INSERT INTO users (user_id, balance, total_otp, referrer) VALUES (?, 0.0, 0, ?)", (user_id, ref))
            conn.commit()
            return (0.0, 0, ref)
        return row

def update_balance(user_id, amount, otp_inc=0):
    with db_lock:
        bal, otps, ref = get_user(user_id)
        new_bal = max(0.0, bal + amount)
        new_otps = otps + otp_inc
        cursor.execute("UPDATE users SET balance = ?, total_otp = ? WHERE user_id = ?", (new_bal, new_otps, user_id))
        conn.commit()

        # ১০টি ওটিপি সম্পন্ন হলে রেফারেল বোনাস প্রদান লজিক
        if otp_inc > 0 and new_otps == 10 and ref:
            cursor.execute("UPDATE users SET balance = balance + 0.10 WHERE user_id = ?", (ref,))
            conn.commit()
            try:
                bot.send_message(ref, "🎉 <b>অভিনন্দন!</b> আপনার একজন রেফারেল ১০টি OTP সফলভাবে সম্পন্ন করায় আপনি <b>$0.1000</b> রেফার বোনাস পেয়েছেন!", parse_mode="HTML")
            except:
                pass

        return new_bal

def dispatch_otp_auto(num, code, full_msg=None):
    try:
        clean_num = num.strip().replace(" ", "").replace("-", "")
        with db_lock:
            cursor.execute("SELECT assigned_user, assigned_service FROM numbers WHERE number LIKE ? AND status = 'ASSIGNED'", (f"%{clean_num[-8:]}%",))
            res = cursor.fetchone()

        if res and res[0]:
            target_user = res[0]
            service_name = res[1] if res[1] else "FACEBOOK"
            otp_rate = float(get_setting("otp_rate", "0.010"))
            new_bal = update_balance(target_user, otp_rate, otp_inc=1)
            bdt_earned = otp_rate * 120

            with db_lock:
                cursor.execute("DELETE FROM numbers WHERE number LIKE ?", (f"%{clean_num[-8:]}%",))
                conn.commit()

            if not full_msg:
                full_msg = f"<#> {code} est votre code {service_name} H29Q+Fsn4Sr"

            otp_text = (
                f"✓ <b>OTP Received!</b>\n"
                f"📲 <b>Number:</b> <code>{clean_num}</code>\n"
                f"🔑 <b>OTP Code:</b> <code>{code}</code>\n"
                f"🛠 <b>Service:</b> {service_name}\n"
                f"✉️ <b>Full Message:</b>\n"
                f"<pre><code class=\"language-powershell\">{full_msg}</code></pre>\n\n"
                f"🛠 <b>Service:</b> {service_name}\n"
                f"📲 <b>Number:</b> <code>{clean_num}</code>\n"
                f"💸 <b>Earned:</b> ৳{bdt_earned:.2f} (${otp_rate:.3f})"
            )

            bot.send_message(target_user, otp_text, parse_mode="HTML")
            bot.send_message(ADMIN_ID, f"⚡ <b>[Auto-OTP]</b> ইউজার <code>{target_user}</code> ওটিপি পেয়েছে!\n📲 <code>{clean_num}</code> | 🔑 <code>{code}</code>", parse_mode="HTML")
            return True
    except Exception as e:
        print("Dispatch error:", e)
    return False

def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    try:
        btn_get = types.KeyboardButton("Get Number", icon_custom_emoji_id="5947265786279104211")
        btn_cnt = types.KeyboardButton("Available Country", icon_custom_emoji_id="5363817109300200686")
        btn_sup = types.KeyboardButton("Support", icon_custom_emoji_id="5803071317401933205")
        btn_bal = types.KeyboardButton("Balance", icon_custom_emoji_id="6190336264940559752")
        btn_wit = types.KeyboardButton("Withdraw", icon_custom_emoji_id="5300737719192795674")
        btn_trf = types.KeyboardButton("Live Traffic", icon_custom_emoji_id="6314486714152784983")
        
        markup.add(btn_get, btn_cnt)
        markup.add(btn_sup, btn_bal)
        markup.add(btn_wit, btn_trf)
    except Exception:
        markup.add(types.KeyboardButton("☎️ Get Number"), types.KeyboardButton("🌍 Available Country"))
        markup.add(types.KeyboardButton("📡 Support"), types.KeyboardButton("💰 Balance"))
        markup.add(types.KeyboardButton("😎 Withdraw"), types.KeyboardButton("🟢 Live Traffic"))

    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ ADMIN PANEL"))
    return markup

def services_menu():
    with db_lock:
        cursor.execute("SELECT name FROM services")
        svcs = cursor.fetchall()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for (name,) in svcs:
        markup.add(types.InlineKeyboardButton(name, callback_data=f"svc_{name}"))
    return markup

def country_menu(service):
    with db_lock:
        cursor.execute("SELECT display_name, country_tag FROM countries WHERE service_name = ?", (service,))
        rows = cursor.fetchall()
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for d_name, c_tag in rows:
        buttons.append(types.InlineKeyboardButton(d_name, callback_data=f"cnt_{c_tag}_{service}"))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])

    markup.add(types.InlineKeyboardButton("🔙 Back to Services", callback_data="back_to_services"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    args = message.text.split()
    ref_id = args[1].replace("ref_", "") if len(args) > 1 and "ref_" in args[1] else None
    get_user(message.chat.id, ref_id)
    
    e_crown = '<tg-emoji emoji-id="5353032893096567467">👑</tg-emoji>'
    e_rocket = '<tg-emoji emoji-id="5352597830089347330">🚀</tg-emoji>'
    e_badge = '<tg-emoji emoji-id="5352694861990501856">🛡️</tg-emoji>'
    e_diamond = '<tg-emoji emoji-id="5352838545826420397">💎</tg-emoji>'

    welcome_box_text = (
        f"╔═════════════════════╗\n"
        f"   {e_crown} ⚡ <b>NEOX FAST SMS</b>\n"
        f"╚═════════════════════╝\n"
        f"{e_rocket} <b>Welcome to Number & OTP Service</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{e_badge} <b>Choose an option below</b>\n"
        f"<b>to continue using the bot.</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{e_diamond} <b>Premium OTP Service</b>"
    )
    bot.send_message(message.chat.id, welcome_box_text, parse_mode="HTML", reply_markup=main_menu(message.chat.id))

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

@bot.message_handler(content_types=['text'])
def handle_menu_and_emojis(message):
    chat_id = message.chat.id
    text = message.text

    if "Get Number" in text:
        msg_service = get_setting("msg_sel_service", "🚦 <b>Select a service:</b> 📥")
        bot.send_message(chat_id, msg_service, parse_mode="HTML", reply_markup=services_menu())

    elif "Available Country" in text:
        with db_lock:
            cursor.execute("SELECT country, COUNT(*) FROM numbers WHERE status = 'AVAILABLE' GROUP BY country")
            counts = cursor.fetchall()
        c_text = "🌍 <b>Available Countries & Numbers:</b>\n\n"
        if counts:
            for country, cnt in counts:
                c_text += f"• <b>{country}</b>: <code>{cnt}</code> টি নাম্বার সচল আছে\n"
        else:
            c_text += "বর্তমানে পুলে কোনো নাম্বার খালি নেই।"
        bot.send_message(chat_id, c_text, parse_mode="HTML")

    elif "Support" in text:
        supp_link = get_setting("support_link", "https://t.me/jaazadmin")
        supp_text = get_support_message()
        markup = types.InlineKeyboardMarkup()
        try:
            markup.add(types.InlineKeyboardButton("NEOX SUPPORT", url=supp_link, icon_custom_emoji_id="5188635482174546097"))
        except:
            markup.add(types.InlineKeyboardButton("24/7 NEOX SUPPORT", url=supp_link))
        bot.send_message(chat_id, supp_text, parse_mode="HTML", reply_markup=markup)

    elif "Balance" in text:
        bal, otps, _ = get_user(chat_id)
        bdt_val = int(bal * 120)
        
        with db_lock:
            # ১০টি ওটিপি পূরণকারী কনফার্ম রেফারেল গণনা
            cursor.execute("SELECT COUNT(*) FROM users WHERE referrer = ? AND total_otp >= 10", (chat_id,))
            ref_count = cursor.fetchone()[0]

        e_bal = '<tg-emoji emoji-id="6275881112849880302">😎</tg-emoji>'
        e_link = '<tg-emoji emoji-id="5942904397313873606">💬</tg-emoji>'
        e_ref = '<tg-emoji emoji-id="5972240522889138094">🟢</tg-emoji>'
        e_earn = '<tg-emoji emoji-id="5776429119868767579">💲</tg-emoji>'

        ref_url = f"https://t.me/{BOT_USERNAME}?start=ref_{chat_id}"

        bal_text = (
            f"{e_bal} <b>Balance:</b> ${bal:.4f} ≈ {bdt_val} BDT\n"
            f"{e_link} <b>Referral Link:</b> {ref_url}\n"
            f"{e_ref} <b>Confirmed Referrals:</b> {ref_count}\n"
            f"{e_earn} <b>Per Refer Earn:</b> $0.1000\n\n"
            f"ℹ️ <b>Referral System:</b> Referrals are confirmed when referred user completes 10 OTP verifications."
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
            bot.send_message(chat_id, f"❌ <b>You need at least ${min_w:.4f} to withdraw.</b>\nYour current balance: ${bal:.4f}", parse_mode="HTML")
        else:
            msg = bot.send_message(chat_id, "💳 <b>আপনার পেমেন্ট তথ্য দিন:</b>\n\nবিকাশ / নগদ নম্বর অথবা Binance Pay ID লিখে পাঠান:", parse_mode="HTML", reply_markup=cancel_markup())
            bot.register_next_step_handler(msg, process_withdraw, bal)

    elif "Live Traffic" in text:
        live_msg = get_live_traffic_message()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"))
        bot.send_message(chat_id, live_msg, parse_mode="HTML", reply_markup=markup)

    elif text == "⚙️ ADMIN PANEL" and chat_id == ADMIN_ID:
        show_admin_panel(chat_id)

def show_admin_panel(chat_id):
    with db_lock:
        cursor.execute("SELECT COUNT(*), SUM(balance), SUM(total_otp) FROM users")
        stats = cursor.fetchone()
        total_users = stats[0] or 0
        total_bal = stats[1] or 0.0
        total_otps = stats[2] or 0

        cursor.execute("SELECT COUNT(*) FROM numbers WHERE status = 'AVAILABLE'")
        avail_num = cursor.fetchone()[0]

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 Edit Bot Texts", callback_data="adm_menu_texts"),
        types.InlineKeyboardButton("📂 Manage Services", callback_data="adm_mng_svc")
    )
    markup.add(
        types.InlineKeyboardButton("🌐 Manage Countries", callback_data="adm_mng_cnt"),
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
        f"👑 <b>A-Z FULL DYNAMIC CONTROL PANEL</b> 👑\n\n"
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
        "📝 <b>আপনি বটের কোন লেখাটি এডিট করতে চান?</b>\nনিচ থেকে সিলেক্ট করুন:",
        chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup
    )

def process_withdraw(message, balance):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        bot.send_message(message.chat.id, "🚫 উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে।")
        return
    chat_id = message.chat.id
    details = message.text
    update_balance(chat_id, -balance)
    
    with db_lock:
        cursor.execute("INSERT INTO withdrawals (user_id, amount, method_details, status) VALUES (?, ?, ?, 'PENDING')",
                       (chat_id, balance, details))
        w_id = cursor.lastrowid
        conn.commit()

    bot.send_message(chat_id, "✅ <b>উইথড্র রিকোয়েস্ট সফল হয়েছে!</b>\nঅ্যাডমিন যাচাই করে পেমেন্ট পাঠিয়ে দেবেন।", parse_mode="HTML")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"wapp_{w_id}_{chat_id}_{balance}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"wrej_{w_id}_{chat_id}_{balance}")
    )

    bot.send_message(
        ADMIN_ID,
        f"🚨 <b>নতুন উইথড্র রিকোয়েস্ট #{w_id}!</b>\n\n"
        f"👤 ইউজার: <code>{chat_id}</code>\n"
        f"💵 পরিমাণ: <b>{balance:.3f} USDT</b>\n"
        f"📝 অ্যাকাউন্ট: <code>{details}</code>",
        parse_mode="HTML",
        reply_markup=markup
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
                # আগের পুলে থাকা অ্যাসাইন বাতিল করা
                cursor.execute("UPDATE numbers SET status = 'AVAILABLE', assigned_user = NULL WHERE assigned_user = ?", (chat_id,))
                
                # সর্বোচ্চ ৩টি নাম্বার তোলা
                cursor.execute(
                    "SELECT id, number FROM numbers WHERE status = 'AVAILABLE' AND (country LIKE ? OR country = ?) ORDER BY id ASC LIMIT 3", 
                    (f"%{country_tag}%", country_tag)
                )
                rows = cursor.fetchall()
                
                if rows:
                    assigned_numbers = []
                    for num_id, num in rows:
                        # বাগ ফিক্স: প্যারামিটারের সঠিক ক্রম (assigned_user, assigned_service, id)
                        cursor.execute("UPDATE numbers SET status = 'ASSIGNED', assigned_user = ?, assigned_service = ? WHERE id = ?", (chat_id, service, num_id))
                        assigned_numbers.append(num)
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
                    no_num_tpl = get_setting("msg_no_number", "⚠️ <b>দুঃখিত! বর্তমানে {country} দেশের কোনো চালু নাম্বার খালি নেই।</b>")
                    no_num_msg = no_num_tpl.replace("{country}", country_tag)
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=no_num_msg, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            print("Error assigning country/number:", e)

    elif call.data.startswith("copy_"):
        copied_num = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, text=f"Copied: {copied_num}")

    elif call.data.startswith("copy_ref_"):
        u_ref = call.data.replace("copy_ref_", "")
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{u_ref}"
        bot.answer_callback_query(call.id, text=f"Copied: {ref_link}")

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
            cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (w_id,))
            conn.commit()
        bot.answer_callback_query(call.id, text="উইথড্র অ্যাপ্রুভ হয়েছে!")
        bot.edit_message_text(f"✅ <b>উইথড্র #{w_id} অ্যাপ্রুভ করা হয়েছে!</b>", chat_id, message_id, parse_mode="HTML")
        bot.send_message(int(u_id), f"🎉 <b>আপনার ${float(amt):.3f} উইথড্র সফলভাবে পরিশোধ করা হয়েছে!</b>", parse_mode="HTML")

    elif call.data.startswith("wrej_") and chat_id == ADMIN_ID:
        _, w_id, u_id, amt = call.data.split("_")
        with db_lock:
            cursor.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (w_id,))
            conn.commit()
        update_balance(int(u_id), float(amt))
        bot.answer_callback_query(call.id, text="উইথড্র বাতিল হয়েছে!")
        bot.edit_message_text(f"❌ <b>উইথড্র #{w_id} বাতিল করা হয়েছে এবং ব্যালেন্স ফেরত দেওয়া হয়েছে।</b>", chat_id, message_id, parse_mode="HTML")
        bot.send_message(int(u_id), f"⚠️ <b>আপনার উইথড্র রিকোয়েস্ট বাতিল হয়েছে এবং ${float(amt):.3f} ব্যালেন্সে ফেরত দেওয়া হয়েছে।</b>", parse_mode="HTML")

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
            f"👉 <b>নতুন যা লিখতে চান তা লিখে পাঠান:</b>\n*(ক্যানসেল করতে নিচের বাটনে চাপুন)*",
            parse_mode="HTML", reply_markup=cancel_markup()
        )
        bot.register_next_step_handler(msg, lambda m: save_text_and_notify(m, txt_key))

    elif call.data == "adm_mng_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        with db_lock:
            cursor.execute("SELECT name FROM services")
            svcs = [s[0] for s in cursor.fetchall()]
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
        msg = bot.send_message(chat_id, "❌ যে সার্ভিসটি মুছে ফেলতে চান তার নাম হুবহু লিখে পাঠান:", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_del_service)

    elif call.data == "adm_mng_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Country", callback_data="adm_add_cnt"), types.InlineKeyboardButton("❌ Delete Country", callback_data="adm_del_cnt"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main"))
        bot.edit_message_text("🌐 <b>দেশ ও রেঞ্জ ম্যানেজমেন্ট:</b>\nনতুন দেশ যোগ বা বাদ দিতে পারেন:", chat_id, message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "adm_add_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        guide_text = "➕ <b>নতুন দেশ যোগ করার ফরম্যাট:</b>\n<code>সার্ভিস | বাটনের নাম ও পতাকা | দেশের আসল ট্যাগ</code>\n\nউদাহরণ:\n<code>FACEBOOK | 🇧🇯 Benin 638 🔥 (450) | Benin</code>"
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
        msg = bot.send_message(chat_id, "📱 দেশ ও নাম্বার পাঠান:\n<code>দেশ নম্বর১ নম্বর২</code>\nউদাহরণ: <code>Benin +229656201 +229656202</code>", parse_mode="HTML", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_numbers)

    elif call.data == "adm_list_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        with db_lock:
            cursor.execute("SELECT country, number, status FROM numbers LIMIT 25")
            nums = cursor.fetchall()
        list_text = "📋 বটের নাম্বার লিস্ট (সর্বোচ্চ ২৫টি):\n\n" + "\n".join([f"• <code>{n}</code> ({c}) - {s}" for c, n, s in nums]) if nums else "কোনো নাম্বার নেই।"
        bot.send_message(chat_id, list_text, parse_mode="HTML")

    elif call.data == "adm_addbal" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "➕/➖ <b>ইউজার ব্যালেন্স পরিবর্তন:</b>\nফরম্যাট: <code>User_ID Amount</code>\nউদাহরণ যোগ করতে: <code>12345678 0.50</code>\nউদাহরণ কাটতে: <code>12345678 -0.50</code>", parse_mode="HTML", reply_markup=cancel_markup())
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

def do_modify_user_balance(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = message.text.split()
        target_uid = int(parts[0])
        amt = float(parts[1])
        new_b = update_balance(target_uid, amt)
        bot.send_message(ADMIN_ID, f"✅ ইউজার <code>{target_uid}</code>-এর ব্যালেন্স আপডেট হয়েছে!\nনতুন ব্যালেন্স: <b>${new_b:.4f}</b>", parse_mode="HTML")
        try:
            action = "যোগ" if amt >= 0 else "কর্তন"
            bot.send_message(target_uid, f"🔔 অ্যাডমিন আপনার অ্যাকাউন্টে <b>${abs(amt):.4f}</b> {action} করেছেন।\nনতুন ব্যালেন্স: <b>${new_b:.4f}</b>", parse_mode="HTML")
        except:
            pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ ভুল ফরম্যাট! উদাহরণ: <code>12345678 0.50</code>\nএরর: {e}", parse_mode="HTML")
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
            cursor.execute("INSERT INTO services (name) VALUES (?)", (s_name,))
            conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে <b>{s_name}</b> সার্ভিস যোগ করা হয়েছে!", parse_mode="HTML")
    except:
        bot.send_message(ADMIN_ID, "⚠️ এই সার্ভিসটি আগেই যোগ করা আছে!", parse_mode="HTML")

def do_del_service(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    s_name = message.text.strip().upper()
    with db_lock:
        cursor.execute("DELETE FROM services WHERE name = ?", (s_name,))
        cursor.execute("DELETE FROM countries WHERE service_name = ?", (s_name,))
        conn.commit()
    bot.send_message(ADMIN_ID, f"✅ <b>{s_name}</b> সার্ভিস মুছে ফেলা হয়েছে!", parse_mode="HTML")

def do_add_country(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = [p.strip() for p in message.text.split("|")]
        s_name, d_name, c_tag = parts[0].upper(), parts[1], parts[2]
        with db_lock:
            cursor.execute("INSERT INTO countries (service_name, display_name, country_tag) VALUES (?, ?, ?)", (s_name, d_name, c_tag))
            conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে <b>{s_name}</b> সার্ভিসে দেশ <b>{d_name}</b> যোগ করা হয়েছে!", parse_mode="HTML")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ফরম্যাট ভুল! উদাহরণ:\n<code>FACEBOOK | 🇧🇯 Benin 638 🔥 (450) | Benin</code>", parse_mode="HTML")

def do_del_country(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    c_tag = message.text.strip()
    with db_lock:
        cursor.execute("DELETE FROM countries WHERE country_tag LIKE ?", (f"%{c_tag}%",))
        conn.commit()
    bot.send_message(ADMIN_ID, f"✅ সফলভাবে <b>{c_tag}</b> দেশের বাটন মুছে ফেলা হয়েছে!", parse_mode="HTML")

def save_setting_and_notify(message, key, name):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    set_setting(key, message.text.strip())
    bot.send_message(ADMIN_ID, f"✅ সফলভাবে <b>{name}</b> আপডেট করা হয়েছে!", parse_mode="HTML")

def do_add_numbers(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = message.text.split()
        country = parts[0]
        number_list = parts[1:]
        added = 0
        with db_lock:
            for num in number_list:
                clean_n = num.strip().replace(" ", "").replace("-", "")
                try:
                    cursor.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country, clean_n))
                    added += 1
                except:
                    pass
            conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে <b>{country}</b> দেশের <b>{added} টি নাম্বার</b> যোগ হয়েছে!", parse_mode="HTML")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট!", parse_mode="HTML")

def do_broadcast(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    with db_lock:
        cursor.execute("SELECT user_id FROM users")
        user_list = cursor.fetchall()
    
    sent = 0
    for (u_id,) in user_list:
        try:
            bot.send_message(u_id, f"📢 <b>ADMIN NOTICE:</b>\n\n{message.text}", parse_mode="HTML")
            sent += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ ব্রডকাস্ট সম্পন্ন! মোট <b>{sent}</b> জনের কাছে মেসেজ পাঠানো হয়েছে।", parse_mode="HTML")

print("NEOX FAST SMS [Optimized & Bug-free] চালু হয়েছে...")
bot.infinity_polling()
