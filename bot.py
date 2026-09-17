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
        self.wfile.write(b"NEOX FAST SMS is Running 24/7!")
        
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

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0.0,
        total_otp INTEGER DEFAULT 0,
        referrer INTEGER DEFAULT NULL
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        method_details TEXT,
        status TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country TEXT,
        number TEXT UNIQUE,
        status TEXT DEFAULT 'AVAILABLE',
        assigned_user INTEGER DEFAULT NULL
    )
''')
conn.commit()

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
            new_bal = update_balance(target_user, 0.010, otp_inc=1)
            cursor.execute("UPDATE numbers SET status = 'AVAILABLE', assigned_user = NULL WHERE number LIKE ?", (f"%{clean_num[-8:]}%",))
            conn.commit()

            otp_text = (
                f"📬 **OTP Received!**\n\n"
                f"📞 Number: `{num}`\n"
                f"🔑 OTP Code: `{code}`\n\n"
                f"💰 ব্যালেন্সে যোগ হয়েছে: +0.010 USDT\n"
                f"💵 বর্তমান ব্যালেন্স: {new_bal:.3f} USDT"
            )
            bot.send_message(target_user, otp_text, parse_mode="Markdown")
            bot.send_message(ADMIN_ID, f"⚡ **[Auto-OTP]** ইউজার `{target_user}` কোড `{code}` পেয়েছে!")
            return True
    except Exception as e:
        print(e)
    return False

# --- মেনু ডিজাইন (ভিডিও অনুযায়ী হুবহু) ---
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("☎️ Get Number"),
        types.KeyboardButton("🌍 Available Country")
    )
    markup.add(
        types.KeyboardButton("📍 Support"),
        types.KeyboardButton("💸 Balance")
    )
    markup.add(
        types.KeyboardButton("😎 Withdraw"),
        types.KeyboardButton("🟢 Live Traffic")
    )
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ ADMIN PANEL"))
    return markup

def services_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("FACEBOOK", callback_data="svc_facebook"),
        types.InlineKeyboardButton("FB NEW CREATE", callback_data="svc_fbnew"),
        types.InlineKeyboardButton("TIKTOK", callback_data="svc_tiktok")
    )
    return markup

def country_menu(service):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if service == "TIKTOK":
        markup.add(
            types.InlineKeyboardButton("🇳🇴 Norway TT (2547)", callback_data=f"cnt_Norway_{service}"),
            types.InlineKeyboardButton("🇳🇵 Nepal TikTok (1752)", callback_data=f"cnt_Nepal_{service}")
        )
    elif service == "FBNEW":
        markup.add(
            types.InlineKeyboardButton("🇮🇹 Italy New FB (520)", callback_data=f"cnt_Italy_{service}"),
            types.InlineKeyboardButton("🇧🇯 Benin 638 🔥 (450)", callback_data=f"cnt_Benin_{service}")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("🇲🇲 Myanmar Top (1166)", callback_data=f"cnt_Myanmar_{service}"),
            types.InlineKeyboardButton("🇪🇬 Egypt S1 (9719)", callback_data=f"cnt_Egypt_{service}"),
            types.InlineKeyboardButton("🇸🇩 Sudan FB 🔥 (874)", callback_data=f"cnt_Sudan_{service}"),
            types.InlineKeyboardButton("🇧🇫 Burkina Faso (1792)", callback_data=f"cnt_Burkina_{service}")
        )
    markup.add(types.InlineKeyboardButton("Back to Services", callback_data="back_to_services"))
    return markup

# --- কমান্ডসমূহ ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
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

@bot.message_handler(func=lambda msg: True)
def handle_menu(message):
    chat_id = message.chat.id
    text = message.text

    if text == "☎️ Get Number":
        bot.send_message(chat_id, "🚦 **Select a service:** 📥", parse_mode="Markdown", reply_markup=services_menu())

    elif text == "🌍 Available Country":
        avail_text = (
            "🌍 **Available Countries:**\n\n"
            "🇲🇲 **Myanmar Top (+95)** - `11664`\n"
            "🇳🇴 **Norway TT (+47)** - `2547`\n"
            "🇪🇬 **Egypt S1 (+201)** - `9715`\n"
            "🇳🇵 **Nepal TikTok (+977)** - `1752`\n"
            "🇸🇩 **Sudan FB 🔥 (+249)** - `858`\n"
            "🇧🇫 **Burkina Faso (+22)** - `1792`\n"
            "🇮🇹 **Italy New FB (+393)** - `518`\n"
            "🇧🇯 **Benin 638 (+229)** - `450`"
        )
        bot.send_message(chat_id, avail_text, parse_mode="Markdown")

    elif text == "📍 Support":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎧 NEOX SUPPORT ↗️", url="https://t.me/jaazadmin"))
        supp_text = (
            "🎧 **NEOX SUPPORT**\n\n"
            "**If You Need Any Help**\n"
            "**Message On Support Team**\n\n"
            "⏰ **All Time Available**"
        )
        bot.send_message(chat_id, supp_text, parse_mode="Markdown", reply_markup=markup)

    elif text == "💸 Balance":
        bal, otps, _ = get_user(chat_id)
        bdt_val = int(bal * 120)  # ১ USDT = ১২০ টাকা
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer = ?", (chat_id,))
        ref_count = cursor.fetchone()[0]

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Copy Referral Link", callback_data=f"copy_ref_{chat_id}"))

        bal_text = (
            f"💰 **Balance:** `${bal:.4f}` ≈ **{bdt_val} BDT**\n"
            f"🔗 **Referral Link:** `https://t.me/{BOT_USERNAME}?start=ref_{chat_id}`\n\n"
            f"👥 **Confirmed Referrals:** `{ref_count}`\n"
            f"💵 **Per Refer Earn:** `$0.1000`\n\n"
            f"ℹ️ **Referral System:** Referrals are confirmed when referred user completes 10 OTP verifications."
        )
        bot.send_message(chat_id, bal_text, parse_mode="Markdown", reply_markup=markup)

    elif text == "😎 Withdraw":
        bal, _, _ = get_user(chat_id)
        if bal < 0.50:
            bot.send_message(chat_id, "❌ **You need at least $0.5000 to withdraw.**", parse_mode="Markdown")
        else:
            msg = bot.send_message(chat_id, "💳 **আপনার পেমেন্ট তথ্য দিন:**\n\nবিকাশ / নগদ নম্বর অথবা Binance Pay ID লিখে পাঠান:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_withdraw, bal)

    elif text == "🟢 Live Traffic":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"))
        traf_text = (
            "🟢 **Live Traffic**\n\n"
            "🗓️ **Window:** Last 5 minutes\n"
            "📊 **Results Sent:** 100%\n"
            "🔥 **Top Country:** 🇸🇩 Sudan FB 🔥\n\n"
            "🏆 **Top Countries:**\n"
            "1. 🇸🇩 **Sudan FB 🔥** — 37.5%\n"
            "2. 🇳🇴 **Norway TT** — 37.5%\n"
            "3. 🇳🇵 **Nepal TikTok** — 25.0%"
        )
        bot.send_message(chat_id, traf_text, parse_mode="Markdown", reply_markup=markup)

    elif text == "⚙️ ADMIN PANEL" and chat_id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*), SUM(balance), SUM(total_otp) FROM users")
        total_users, total_bal, total_otps = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM numbers WHERE status = 'AVAILABLE'")
        avail_num = cursor.fetchone()[0]

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Numbers", callback_data="admin_add_num"),
            types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
        )
        markup.add(
            types.InlineKeyboardButton("➕ Add Balance", callback_data="admin_addbal"),
            types.InlineKeyboardButton("📋 Number Pool", callback_data="admin_list_num")
        )

        admin_text = (
            f"👑 **ADMIN CONTROL PANEL** 👑\n\n"
            f"👥 মোট ইউজার: **{total_users} জন**\n"
            f"📬 মোট ওটিপি সম্পন্ন: **{total_otps or 0} টি**\n"
            f"📱 পুলে সচল আসল নাম্বার: **{avail_num} টি**\n\n"
            f"⚡ অটো-ওটিপি সিস্টেম: **সক্রিয় ✅**"
        )
        bot.send_message(chat_id, admin_text, reply_markup=markup, parse_mode="Markdown")

def process_withdraw(message, balance):
    chat_id = message.chat.id
    details = message.text
    update_balance(chat_id, -balance)
    cursor.execute("INSERT INTO withdrawals (user_id, amount, method_details, status) VALUES (?, ?, ?, 'PENDING')",
                   (chat_id, balance, details))
    conn.commit()
    bot.send_message(chat_id, "✅ **উইথড্র রিকোয়েস্ট সফল হয়েছে!**\nঅ্যাডমিন যাচাই করে পেমেন্ট পাঠিয়ে দেবেন।", parse_mode="Markdown")
    bot.send_message(ADMIN_ID, f"🚨 **নতুন উইথড্র রিকোয়েস্ট!**\n👤 ইউজার: `{chat_id}`\n💵 পরিমাণ: **{balance:.3f} USDT**\n📝 অ্যাকাউন্ট: `{details}`", parse_mode="Markdown")

# --- ইনলাইন বাটন হ্যান্ডলার (AZ স্টাইলের মতো হুবহু) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data.startswith("svc_"):
        service = call.data.replace("svc_", "").upper()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🌍 **Select your country:** 📥",
            parse_mode="Markdown",
            reply_markup=country_menu(service)
        )

    elif call.data == "back_to_services":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🚦 **Select a service:** 📥",
            parse_mode="Markdown",
            reply_markup=services_menu()
        )

    elif call.data.startswith("cnt_"):
        parts = call.data.split("_")
        country = parts[1]
        service = parts[2]
        bot.answer_callback_query(call.id, text=f"2 {country} numbers assigned!")

        # বিভিন্ন দেশের পতাকা ও ডেমো/আসল নম্বর পেয়ার (ভিডিওর মতো হুবহু)
        country_data = {
            "Myanmar": ("🇲🇲", "+959650645279", "+959650502688"),
            "Egypt": ("🇪🇬", "+201552032352", "+201552032843"),
            "Italy": ("🇮🇹", "+393241946464", "+393241946465"),
            "Norway": ("🇳🇴", "+4740174027", "+4740167337"),
            "Sudan": ("🇸🇩", "+249126297403", "+249126297476"),
            "Benin": ("🇧🇯", "+22965620194", "+22965620195")
        }
        flag, num1, num2 = country_data.get(country, ("🌐", "+249126297403", "+249126297476"))

        markup = types.InlineKeyboardMarkup(row_width=1)
        # ভিডিওর মতো সুন্দর বাটন আকারে নম্বর
        markup.add(
            types.InlineKeyboardButton(f"{flag}  {num1}", callback_data=f"copy_{num1}"),
            types.InlineKeyboardButton(f"{flag}  {num2}", callback_data=f"copy_{num2}")
        )
        markup.add(
            types.InlineKeyboardButton("🔄 Change Number", callback_data=f"cnt_{country}_{service}"),
            types.InlineKeyboardButton("🌐 Change Country", callback_data="back_to_services"),
            types.InlineKeyboardButton("📢 OTP Group ↗️", url="https://t.me/jaazadmin")
        )

        assigned_msg = (
            f"{flag} **{country} Number Assigned:**\n\n"
            f"🌟 **Waiting For OTP:**"
        )
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=assigned_msg,
            parse_mode="Markdown",
            reply_markup=markup
        )

    elif call.data.startswith("copy_"):
        num = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, text=f"Number Copied: {num}")

    elif call.data.startswith("copy_ref_"):
        user_ref = call.data.replace("copy_ref_", "")
        bot.answer_callback_query(call.id, text=f"Referral Link: https://t.me/{BOT_USERNAME}?start=ref_{user_ref}")

    elif call.data == "refresh_traffic":
        bot.answer_callback_query(call.id, text="Traffic refreshed!")

    elif call.data == "admin_add_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📱 দেশ ও নাম্বার পাঠান:\n`দেশ নম্বর১ নম্বর২`\nউদাহরণ: `Benin +229656201 +229656202`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, do_add_numbers)

    elif call.data == "admin_list_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT country, number, status FROM numbers LIMIT 15")
        nums = cursor.fetchall()
        list_text = "📋 বটের নাম্বার লিস্ট:\n\n" + "\n".join([f"• `{n}` ({c}) - {s}" for c, n, s in nums]) if nums else "কোনো নাম্বার নেই।"
        bot.send_message(chat_id, list_text, parse_mode="Markdown")

    elif call.data == "admin_broadcast" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 ব্রডকাস্ট মেসেজ লিখে পাঠান:")
        bot.register_next_step_handler(msg, do_broadcast)

    elif call.data == "admin_addbal" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "ফরম্যাট: `আইডি ব্যালেন্স` (যেমন: 7241161752 0.50)")
        bot.register_next_step_handler(msg, do_add_balance)

def do_add_numbers(message):
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
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে {added} টি নাম্বার যোগ হয়েছে!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট!")

def do_broadcast(message):
    cursor.execute("SELECT user_id FROM users")
    for (u_id,) in cursor.fetchall():
        try:
            bot.send_message(u_id, f"📢 ADMIN NOTICE:\n\n{message.text}")
        except:
            pass
    bot.send_message(ADMIN_ID, "✅ ব্রডকাস্ট সম্পন্ন!")

def do_add_balance(message):
    try:
        u_id, amt = message.text.split()
        new_b = update_balance(int(u_id), float(amt))
        bot.send_message(ADMIN_ID, f"✅ ব্যালেন্স যোগ হয়েছে: {new_b:.3f}")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট!")

print("NEOX FAST SMS [100% AZ Number Bot Replica] চালু হয়েছে...")
bot.infinity_polling()
