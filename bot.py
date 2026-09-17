import telebot
from telebot import types
import sqlite3
import time
import os
from urllib.parse import urlparse, parse_qs
from threading import Thread
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
            if num and code:
                dispatch_otp_auto(num, code)
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"OK")
                return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"NEOX FAST SMS (Cancel Button System Active)")
        
    def log_message(self, format, *args):
        return

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# --- Bot Config ---
BOT_TOKEN = "8843310193:AAH9ViXDNIi94hQnuZLjmiLe3UhtaaUM77U"
ADMIN_ID = 7241161752
BOT_USERNAME = "neoxfastsms_bot"

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect("bot_users.db", check_same_thread=False)
cursor = conn.cursor()

# টেবিলসমূহ
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, total_otp INTEGER DEFAULT 0, referrer INTEGER DEFAULT NULL
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, method_details TEXT, status TEXT DEFAULT 'PENDING'
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, number TEXT UNIQUE, status TEXT DEFAULT 'AVAILABLE', assigned_user INTEGER DEFAULT NULL
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

# ডিফল্ট সার্ভিস ও কান্ট্রি লোড (যদি খালি থাকে)
cursor.execute("SELECT COUNT(*) FROM services")
if cursor.fetchone()[0] == 0:
    default_services = ["FACEBOOK", "FB NEW CREATE", "TIKTOK"]
    for s in default_services:
        cursor.execute("INSERT OR IGNORE INTO services (name) VALUES (?)", (s,))
    
    default_countries = [
        ("FACEBOOK", "🇲🇲 Myanmar Top (1166)", "Myanmar"),
        ("FACEBOOK", "🇪🇬 Egypt S1 (9719)", "Egypt"),
        ("FACEBOOK", "🇸🇩 Sudan FB 🔥 (874)", "Sudan"),
        ("FACEBOOK", "🇧🇫 Burkina Faso (1792)", "Burkina"),
        ("FACEBOOK", "🇧🇯 Benin 638 🔥 (450)", "Benin"),
        ("FB NEW CREATE", "🇮🇹 Italy New FB (520)", "Italy"),
        ("FB NEW CREATE", "🇧🇯 Benin 638 🔥 (450)", "Benin"),
        ("TIKTOK", "🇳🇴 Norway TT (2547)", "Norway"),
        ("TIKTOK", "🇳🇵 Nepal TikTok (1752)", "Nepal")
    ]
    for s_name, d_name, c_tag in default_countries:
        cursor.execute("INSERT INTO countries (service_name, display_name, country_tag) VALUES (?, ?, ?)", (s_name, d_name, c_tag))
    conn.commit()

def get_setting(key, default_val):
    cursor.execute("SELECT val FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(default_val)))
    conn.commit()
    return str(default_val)

def set_setting(key, val):
    cursor.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(val)))
    conn.commit()

# ডিফল্ট বাটন সেটিংস
get_setting("btn_get_num", "☎️ Get Number")
get_setting("btn_avail_cnt", "🌍 Available Country")
get_setting("btn_support", "📍 Support")
get_setting("btn_balance", "💸 Balance")
get_setting("btn_withdraw", "😎 Withdraw")
get_setting("btn_traffic", "🟢 Live Traffic")
get_setting("support_link", "https://t.me/jaazadmin")
get_setting("otp_group", "https://t.me/jaazadmin")
get_setting("min_withdraw", "0.50")
get_setting("otp_rate", "0.010")
get_setting("traffic_text", "🟢 Live Traffic Active!\n\n1. 🇸🇩 Sudan FB — 37.5%\n2. 🇳🇴 Norway TT — 37.5%\n3. 🇳🇵 Nepal TikTok — 25.0%")

# ক্যানসেল বাটন তৈরির ফাংশন
def cancel_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel (বাতিল)", callback_data="cancel_action"))
    return markup

def get_user(user_id, ref_id=None):
    cursor.execute("SELECT balance, total_otp, referrer FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        ref = int(ref_id) if ref_id and str(ref_id).isdigit() and int(ref_id) != user_id else None
        cursor.execute("INSERT INTO users (user_id, balance, total_otp, referrer) VALUES (?, 0.0, 0, ?)", (user_id, ref))
        conn.commit()
        return (0.0, 0, ref)
    return row

def update_balance(user_id, amount, otp_inc=0):
    bal, otps, _ = get_user(user_id)
    new_bal = max(0.0, bal + amount)
    new_otps = otps + otp_inc
    cursor.execute("UPDATE users SET balance = ?, total_otp = ? WHERE user_id = ?", (new_bal, new_otps, user_id))
    conn.commit()
    return new_bal

def dispatch_otp_auto(num, code):
    try:
        clean_num = num.strip().replace(" ", "").replace("-", "")
        cursor.execute("SELECT assigned_user FROM numbers WHERE number LIKE ? AND status = 'ASSIGNED'", (f"%{clean_num[-8:]}%",))
        res = cursor.fetchone()
        if res and res[0]:
            target_user = res[0]
            otp_rate = float(get_setting("otp_rate", "0.010"))
            new_bal = update_balance(target_user, otp_rate, otp_inc=1)
            cursor.execute("UPDATE numbers SET status = 'AVAILABLE', assigned_user = NULL WHERE number LIKE ?", (f"%{clean_num[-8:]}%",))
            conn.commit()

            otp_text = (
                f"📬 **OTP Received!**\n\n"
                f"📞 Number: `{num}`\n"
                f"🔑 OTP Code: `{code}`\n\n"
                f"💰 ব্যালেন্সে যোগ হয়েছে: +{otp_rate:.3f} USDT\n"
                f"💵 বর্তমান ব্যালেন্স: {new_bal:.3f} USDT"
            )
            bot.send_message(target_user, otp_text, parse_mode="Markdown")
            bot.send_message(ADMIN_ID, f"⚡ **[Auto-OTP]** ইউজার `{target_user}` কোড `{code}` পেয়েছে! (+{otp_rate:.3f} USDT)")
            return True
    except Exception as e:
        print(e)
    return False

# --- মেনু ফাংশনসমূহ ---
def main_menu(user_id):
    b_get = get_setting("btn_get_num", "☎️ Get Number")
    b_cnt = get_setting("btn_avail_cnt", "🌍 Available Country")
    b_sup = get_setting("btn_support", "📍 Support")
    b_bal = get_setting("btn_balance", "💸 Balance")
    b_wit = get_setting("btn_withdraw", "😎 Withdraw")
    b_trf = get_setting("btn_traffic", "🟢 Live Traffic")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton(b_get), types.KeyboardButton(b_cnt))
    markup.add(types.KeyboardButton(b_sup), types.KeyboardButton(b_bal))
    markup.add(types.KeyboardButton(b_wit), types.KeyboardButton(b_trf))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ ADMIN PANEL"))
    return markup

def services_menu():
    cursor.execute("SELECT name FROM services")
    svcs = cursor.fetchall()
    markup = types.InlineKeyboardMarkup(row_width=1)
    for (name,) in svcs:
        markup.add(types.InlineKeyboardButton(name, callback_data=f"svc_{name}"))
    return markup

def country_menu(service):
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

    markup.add(types.InlineKeyboardButton("Back to Services", callback_data="back_to_services"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    # কোনো পেন্ডিং ইনপুট থাকলে ক্লিয়ার করা
    bot.clear_step_handler_by_chat_id(message.chat.id)
    
    args = message.text.split()
    ref_id = args[1].replace("ref_", "") if len(args) > 1 and "ref_" in args[1] else None
    get_user(message.chat.id, ref_id)
    
    welcome_text = (
        f"💖 **Welcome {message.from_user.first_name}!** 🎉\n\n"
        "🗣️ **Main Menu**\n\n"
        "📥 **Please select an option below:**"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu(message.chat.id))

@bot.message_handler(commands=['otp'])
def admin_manual_otp(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, num, code = message.text.split()
        if not dispatch_otp_auto(num, code):
            bot.send_message(ADMIN_ID, f"⚠️ এই নম্বরটি ({num}) বর্তমানে কারো কাছে সক্রিয় নেই!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ সঠিক ফরম্যাট: `/otp নম্বর কোড`", parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.send_message(message.chat.id, "🚫 **অপারেশনটি বাতিল করা হয়েছে!**", parse_mode="Markdown", reply_markup=main_menu(message.chat.id))
    if message.chat.id == ADMIN_ID:
        show_admin_panel(message.chat.id)

@bot.message_handler(func=lambda msg: True)
def handle_menu(message):
    chat_id = message.chat.id
    text = message.text

    b_get = get_setting("btn_get_num", "☎️ Get Number")
    b_cnt = get_setting("btn_avail_cnt", "🌍 Available Country")
    b_sup = get_setting("btn_support", "📍 Support")
    b_bal = get_setting("btn_balance", "💸 Balance")
    b_wit = get_setting("btn_withdraw", "😎 Withdraw")
    b_trf = get_setting("btn_traffic", "🟢 Live Traffic")

    if text == b_get:
        bot.send_message(chat_id, "🚦 **Select a service:** 📥", parse_mode="Markdown", reply_markup=services_menu())

    elif text == b_cnt:
        cursor.execute("SELECT country, COUNT(*) FROM numbers WHERE status = 'AVAILABLE' GROUP BY country")
        counts = cursor.fetchall()
        c_text = "🌍 **Available Countries & Numbers:**\n\n"
        if counts:
            for country, cnt in counts:
                c_text += f"• **{country}**: `{cnt}` টি নাম্বার সচল আছে\n"
        else:
            c_text += "বর্তমানে পুলে নতুন নাম্বার লোড করা হচ্ছে..."
        bot.send_message(chat_id, c_text, parse_mode="Markdown")

    elif text == b_sup:
        supp_link = get_setting("support_link", "https://t.me/jaazadmin")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎧 SUPPORT TEAM ↗️", url=supp_link))
        supp_text = "🎧 **SUPPORT TEAM**\n\n**If You Need Any Help Message On Support Team**\n\n⏰ **All Time Available**"
        bot.send_message(chat_id, supp_text, parse_mode="Markdown", reply_markup=markup)

    elif text == b_bal:
        bal, otps, _ = get_user(chat_id)
        bdt_val = int(bal * 120)
        otp_rate = float(get_setting("otp_rate", "0.010"))
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer = ?", (chat_id,))
        ref_count = cursor.fetchone()[0]

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Copy Referral Link", callback_data=f"copy_ref_{chat_id}"))

        bal_text = (
            f"💰 **Balance:** `${bal:.4f}` ≈ **{bdt_val} BDT**\n"
            f"🔗 **Referral Link:** `https://t.me/{BOT_USERNAME}?start=ref_{chat_id}`\n\n"
            f"👥 **Confirmed Referrals:** `{ref_count}`\n"
            f"💵 **Per Refer Earn:** `$0.1000`\n"
            f"📬 **Per OTP Rate:** `${otp_rate:.3f}`"
        )
        bot.send_message(chat_id, bal_text, parse_mode="Markdown", reply_markup=markup)

    elif text == b_wit:
        bal, _, _ = get_user(chat_id)
        min_w = float(get_setting("min_withdraw", "0.50"))
        if bal < min_w:
            bot.send_message(chat_id, f"❌ **You need at least ${min_w:.4f} to withdraw.**", parse_mode="Markdown")
        else:
            msg = bot.send_message(chat_id, "💳 **আপনার পেমেন্ট তথ্য দিন:**\n\nবিকাশ / নগদ নম্বর অথবা Binance Pay ID লিখে পাঠান:", parse_mode="Markdown", reply_markup=cancel_markup())
            bot.register_next_step_handler(msg, process_withdraw, bal)

    elif text == b_trf:
        live_msg = get_setting("traffic_text", "🟢 Live Traffic Active!")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"))
        bot.send_message(chat_id, live_msg, parse_mode="Markdown", reply_markup=markup)

    elif text == "⚙️ ADMIN PANEL" and chat_id == ADMIN_ID:
        show_admin_panel(chat_id)

def show_admin_panel(chat_id):
    cursor.execute("SELECT COUNT(*), SUM(balance), SUM(total_otp) FROM users")
    total_users, total_bal, total_otps = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM numbers WHERE status = 'AVAILABLE'")
    avail_num = cursor.fetchone()[0]

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📂 Manage Services", callback_data="adm_mng_svc"),
        types.InlineKeyboardButton("🌐 Manage Countries", callback_data="adm_mng_cnt")
    )
    markup.add(
        types.InlineKeyboardButton("➕ Add Numbers", callback_data="adm_add_num"),
        types.InlineKeyboardButton("📋 Number Pool", callback_data="adm_list_num")
    )
    markup.add(
        types.InlineKeyboardButton("🔤 Rename Buttons", callback_data="adm_menu_btns"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("🎧 Support Link", callback_data="adm_set_supp"),
        types.InlineKeyboardButton("📢 OTP Group Link", callback_data="adm_set_group")
    )
    markup.add(
        types.InlineKeyboardButton("💵 Min Withdraw", callback_data="adm_set_minw"),
        types.InlineKeyboardButton("🎁 Set OTP Rate", callback_data="adm_set_rate")
    )

    admin_text = (
        f"👑 **A-Z FULL DYNAMIC CONTROL PANEL** 👑\n\n"
        f"👥 মোট ইউজার: **{total_users} জন**\n"
        f"📬 মোট ওটিপি সম্পন্ন: **{total_otps or 0} টি**\n"
        f"📱 পুলে সচল আসল নাম্বার: **{avail_num} টি**\n\n"
        f"⚙️ *নিচের বাটনগুলো দিয়ে সার্ভিস, দেশ ও সব সেটিংস পরিবর্তন করুন:*"
    )
    bot.send_message(chat_id, admin_text, reply_markup=markup, parse_mode="Markdown")

def process_withdraw(message, balance):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        bot.send_message(message.chat.id, "🚫 উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে।")
        return
    chat_id = message.chat.id
    details = message.text
    update_balance(chat_id, -balance)
    cursor.execute("INSERT INTO withdrawals (user_id, amount, method_details, status) VALUES (?, ?, ?, 'PENDING')",
                   (chat_id, balance, details))
    w_id = cursor.lastrowid
    conn.commit()

    bot.send_message(chat_id, "✅ **উইথড্র রিকোয়েস্ট সফল হয়েছে!**\nঅ্যাডমিন যাচাই করে পেমেন্ট পাঠিয়ে দেবেন।", parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"wapp_{w_id}_{chat_id}_{balance}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"wrej_{w_id}_{chat_id}_{balance}")
    )

    bot.send_message(
        ADMIN_ID,
        f"🚨 **নতুন উইথড্র রিকোয়েস্ট #{w_id}!**\n\n"
        f"👤 ইউজার: `{chat_id}`\n"
        f"💵 পরিমাণ: **{balance:.3f} USDT**\n"
        f"📝 অ্যাকাউন্ট: `{details}`",
        parse_mode="Markdown",
        reply_markup=markup
    )

# --- ইনলাইন বাটন হ্যান্ডলার ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # ❌ ক্যানসেল বাটন হ্যান্ডলার
    if call.data == "cancel_action":
        bot.clear_step_handler_by_chat_id(chat_id)
        bot.answer_callback_query(call.id, text="বাতিল করা হয়েছে!")
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
        bot.send_message(chat_id, "🚫 **অপারেশনটি বাতিল করা হয়েছে!**", parse_mode="Markdown")
        if chat_id == ADMIN_ID:
            show_admin_panel(chat_id)
        return

    if call.data.startswith("svc_"):
        service = call.data.replace("svc_", "")
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text="🌍 **Select your country:** 📥", parse_mode="Markdown",
            reply_markup=country_menu(service)
        )

    elif call.data == "back_to_services":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text="🚦 **Select a service:** 📥", parse_mode="Markdown",
            reply_markup=services_menu()
        )

    elif call.data.startswith("cnt_"):
        parts = call.data.split("_")
        country_tag, service = parts[1], parts[2]
        bot.answer_callback_query(call.id)

        cursor.execute("SELECT id, number FROM numbers WHERE status = 'AVAILABLE' AND country LIKE ? LIMIT 1", (f"%{country_tag}%",))
        row = cursor.fetchone()
        
        if row:
            num_id, assigned_number = row
            cursor.execute("UPDATE numbers SET status = 'ASSIGNED', assigned_user = ? WHERE id = ?", (chat_id, num_id))
            conn.commit()

            otp_group_link = get_setting("otp_group", "https://t.me/jaazadmin")
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton(f"📞  {assigned_number}", callback_data=f"copy_{assigned_number}"),
                types.InlineKeyboardButton("🔄 Change Number", callback_data=f"cnt_{country_tag}_{service}"),
                types.InlineKeyboardButton("🌐 Change Country", callback_data=f"svc_{service}"),
                types.InlineKeyboardButton("📢 OTP Group ↗️", url=otp_group_link)
            )

            assigned_msg = f"📱 **{country_tag} Number Assigned:**\n\n🌟 **Waiting For OTP:**"
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=assigned_msg, parse_mode="Markdown", reply_markup=markup)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Choose Another Country", callback_data=f"svc_{service}"))
            bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=f"⚠️ **দুঃখিত! বর্তমানে {country_tag} দেশের কোনো চালু নাম্বার খালি নেই।**\n\nদয়া করে অন্য কোনো দেশ নির্বাচন করুন অথবা অ্যাডমিনকে নাম্বার লোড করতে বলুন।",
                parse_mode="Markdown", reply_markup=markup
            )

    elif call.data.startswith("copy_"):
        bot.answer_callback_query(call.id, text="Number Copied!")

    elif call.data.startswith("copy_ref_"):
        u_ref = call.data.replace("copy_ref_", "")
        bot.answer_callback_query(call.id, text=f"Referral Link: https://t.me/{BOT_USERNAME}?start=ref_{u_ref}")

    elif call.data == "refresh_traffic":
        bot.answer_callback_query(call.id, text="Traffic refreshed!")

    elif call.data.startswith("wapp_") and chat_id == ADMIN_ID:
        _, w_id, u_id, amt = call.data.split("_")
        cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (w_id,))
        conn.commit()
        bot.answer_callback_query(call.id, text="উইথড্র অ্যাপ্রুভ হয়েছে!")
        bot.edit_message_text(f"✅ **উইথড্র #{w_id} অ্যাপ্রুভ করা হয়েছে!**", chat_id, message_id, parse_mode="Markdown")
        bot.send_message(int(u_id), f"🎉 **আপনার ${float(amt):.3f} উইথড্র সফলভাবে পরিশোধ করা হয়েছে!**")

    elif call.data.startswith("wrej_") and chat_id == ADMIN_ID:
        _, w_id, u_id, amt = call.data.split("_")
        cursor.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (w_id,))
        conn.commit()
        update_balance(int(u_id), float(amt))
        bot.answer_callback_query(call.id, text="উইথড্র বাতিল হয়েছে!")
        bot.edit_message_text(f"❌ **উইথড্র #{w_id} বাতিল করা হয়েছে এবং ব্যালেন্স ফেরত দেওয়া হয়েছে।**", chat_id, message_id, parse_mode="Markdown")
        bot.send_message(int(u_id), f"⚠️ **আপনার উইথড্র রিকোয়েস্ট বাতিল হয়েছে এবং ${float(amt):.3f} ব্যালেন্সে ফেরত দেওয়া হয়েছে।**")

    # --- সার্ভিস ও কান্ট্রি অ্যাডমিন ---
    elif call.data == "adm_mng_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT name FROM services")
        svcs = [s[0] for s in cursor.fetchall()]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Service", callback_data="adm_add_svc"),
            types.InlineKeyboardButton("❌ Delete Service", callback_data="adm_del_svc")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main"))
        bot.edit_message_text(
            f"📂 **বর্তমান সার্ভিসসমূহ:**\n\n" + "\n".join([f"• `{s}`" for s in svcs]) + "\n\nনতুন সার্ভিস যোগ করতে বা মুছতে বাটন চাপুন:",
            chat_id, message_id, parse_mode="Markdown", reply_markup=markup
        )

    elif call.data == "adm_add_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "➕ নতুন সার্ভিসের নাম লিখে পাঠান (যেমন: `WHATSAPP`):", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_service)

    elif call.data == "adm_del_svc" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "❌ যে সার্ভিসটি মুছে ফেলতে চান তার নাম হুবহু লিখে পাঠান:", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_del_service)

    elif call.data == "adm_mng_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Country", callback_data="adm_add_cnt"),
            types.InlineKeyboardButton("❌ Delete Country", callback_data="adm_del_cnt")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main"))
        bot.edit_message_text(
            "🌐 **দেশ ও রেঞ্জ ম্যানেজমেন্ট:**\n\nযেকোনো সার্ভিসের ভেতরে নতুন দেশ যোগ করতে বা বাদ দিতে নিচের বাটন চাপুন:",
            chat_id, message_id, parse_mode="Markdown", reply_markup=markup
        )

    elif call.data == "adm_add_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        guide_text = (
            "➕ **নতুন দেশ যোগ করার নিয়ম:**\n\n"
            "এই ফরম্যাটে লিখে পাঠান:\n"
            "`সার্ভিস | বাটনের নাম ও পতাকা | দেশের আসল ট্যাগ`\n\n"
            "উদাহরণ:\n"
            "`FACEBOOK | 🇧🇯 Benin 638 🔥 (450) | Benin`"
        )
        msg = bot.send_message(chat_id, guide_text, parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_country)

    elif call.data == "adm_del_cnt" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "❌ যে দেশের বাটনটি মুছতে চান, তার মূল দেশের ট্যাগটি লিখে পাঠান (যেমন: `Myanmar` বা `Egypt`):", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_del_country)

    elif call.data == "adm_back_main" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        show_admin_panel(chat_id)

    # বাটন রিনেম
    elif call.data == "adm_menu_btns" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        rename_buttons_menu(chat_id, message_id)

    elif call.data.startswith("rnb_") and chat_id == ADMIN_ID:
        btn_key = call.data.replace("rnb_", "")
        bot.answer_callback_query(call.id)
        current_name = get_setting(btn_key, "Button")
        msg = bot.send_message(chat_id, f"✏️ বর্তমান নাম: `{current_name}`\n\nনতুন নাম ও ইমোজি লিখে পাঠান:", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_btn_and_notify(m, btn_key))

    # অন্যান্য সেটিংস
    elif call.data == "adm_add_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📱 দেশ ও নাম্বার পাঠান:\n`দেশ নম্বর১ নম্বর২`\nউদাহরণ: `Egypt +20155201 +20155202`", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_add_numbers)

    elif call.data == "adm_list_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT country, number, status FROM numbers LIMIT 15")
        nums = cursor.fetchall()
        list_text = "📋 বটের নাম্বার লিস্ট:\n\n" + "\n".join([f"• `{n}` ({c}) - {s}" for c, n, s in nums]) if nums else "কোনো নাম্বার নেই।"
        bot.send_message(chat_id, list_text, parse_mode="Markdown")

    elif call.data == "adm_broadcast" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 ব্রডকাস্ট মেসেজটি লিখুন:", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, do_broadcast)

    elif call.data == "adm_set_supp" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🎧 নতুন সাপোর্ট লিংক পাঠান:\n(যেমন: `https://t.me/jaazadmin`)", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "support_link", "সাপোর্ট লিংক"))

    elif call.data == "adm_set_group" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 নতুন OTP Group লিংক পাঠান:\n(যেমন: `https://t.me/YourGroup`)", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "otp_group", "OTP Group লিংক"))

    elif call.data == "adm_set_minw" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "💵 নতুন মিনিমাম উইথড্র অ্যামাউন্ট (ডলারে):", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "min_withdraw", "মিনিমাম উইথড্র"))

    elif call.data == "adm_set_rate" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🎁 প্রতি ওটিপির রেট (ডলারে):", parse_mode="Markdown", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, lambda m: save_setting_and_notify(m, "otp_rate", "প্রতি ওটিপির রেট"))

def rename_buttons_menu(chat_id, message_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("1. Get Number বাটন", callback_data="rnb_btn_get_num"),
        types.InlineKeyboardButton("2. Available Country বাটন", callback_data="rnb_btn_avail_cnt")
    )
    markup.add(
        types.InlineKeyboardButton("3. Support বাটন", callback_data="rnb_btn_support"),
        types.InlineKeyboardButton("4. Balance বাটন", callback_data="rnb_btn_balance")
    )
    markup.add(
        types.InlineKeyboardButton("5. Withdraw বাটন", callback_data="rnb_btn_withdraw"),
        types.InlineKeyboardButton("6. Live Traffic বাটন", callback_data="rnb_btn_traffic")
    )
    markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_back_main"))
    bot.edit_message_text("🔤 **কোন বাটনের নাম পরিবর্তন করতে চান?**", chat_id, message_id, parse_mode="Markdown", reply_markup=markup)

def do_add_service(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    s_name = message.text.strip().upper()
    try:
        cursor.execute("INSERT INTO services (name) VALUES (?)", (s_name,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে **{s_name}** সার্ভিস যোগ করা হয়েছে!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ এই সার্ভিসটি আগেই যোগ করা আছে!")

def do_del_service(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    s_name = message.text.strip().upper()
    cursor.execute("DELETE FROM services WHERE name = ?", (s_name,))
    cursor.execute("DELETE FROM countries WHERE service_name = ?", (s_name,))
    conn.commit()
    bot.send_message(ADMIN_ID, f"✅ **{s_name}** সার্ভিস এবং এর অন্তর্গত সব দেশ মুছে ফেলা হয়েছে!")

def do_add_country(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = [p.strip() for p in message.text.split("|")]
        s_name, d_name, c_tag = parts[0].upper(), parts[1], parts[2]
        cursor.execute("INSERT INTO countries (service_name, display_name, country_tag) VALUES (?, ?, ?)", (s_name, d_name, c_tag))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে **{s_name}** সার্ভিসে দেশ **{d_name}** যোগ করা হয়েছে!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ফরম্যাট ভুল! সঠিক ফরম্যাট:\n`FACEBOOK | 🇧🇯 Benin 638 🔥 (450) | Benin`", parse_mode="Markdown")

def do_del_country(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    c_tag = message.text.strip()
    cursor.execute("DELETE FROM countries WHERE country_tag LIKE ?", (f"%{c_tag}%",))
    conn.commit()
    bot.send_message(ADMIN_ID, f"✅ সফলভাবে **{c_tag}** দেশের বাটন মুছে ফেলা হয়েছে!")

def save_btn_and_notify(message, btn_key):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    new_title = message.text.strip()
    set_setting(btn_key, new_title)
    bot.send_message(ADMIN_ID, f"✅ বাটনের নাম আপডেট হয়ে **`{new_title}`** হয়েছে!", parse_mode="Markdown", reply_markup=main_menu(ADMIN_ID))

def save_setting_and_notify(message, key, name):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    set_setting(key, message.text.strip())
    bot.send_message(ADMIN_ID, f"✅ সফলভাবে **{name}** আপডেট করা হয়েছে!", parse_mode="Markdown")

def do_add_numbers(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    try:
        parts = message.text.split()
        country, number_list = parts[0], parts[1:]
        added = 0
        for num in number_list:
            try:
                cursor.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country, num))
                added += 1
            except:
                pass
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে **{country}** দেশের **{added} টি নাম্বার** যোগ হয়েছে!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট!")

def do_broadcast(message):
    if message.text in ["/cancel", "cancel", "বাতিল"]:
        return
    cursor.execute("SELECT user_id FROM users")
    for (u_id,) in cursor.fetchall():
        try:
            bot.send_message(u_id, f"📢 ADMIN NOTICE:\n\n{message.text}")
        except:
            pass
    bot.send_message(ADMIN_ID, "✅ ব্রডকাস্ট সম্পন্ন!")

print("NEOX FAST SMS [Cancel Button Engine Active] চালু হয়েছে...")
bot.infinity_polling()
