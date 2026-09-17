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
                self.wfile.write(b"OTP Sent Automatically!")
                return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"NEOX Fast SMS is Running 24/7!")
        
    def log_message(self, format, *args):
        return

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# --- Bot Configuration ---
BOT_TOKEN = "8843310193:AAH9ViXDNIi94hQnuZLjmiLe3UhtaaUM77U"
ADMIN_ID = 7241161752

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect("bot_users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0.0,
        total_otp INTEGER DEFAULT 0
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

def get_user(user_id):
    cursor.execute("SELECT balance, total_otp FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, total_otp) VALUES (?, 0.0, 0)", (user_id,))
        conn.commit()
        return (0.0, 0)
    return row

def update_balance(user_id, amount, otp_inc=0):
    bal, otps = get_user(user_id)
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

# --- মেনু ডিজাইন ---
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

# সার্ভিস মেনু (AZ স্টাইল)
def services_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📘 FACEBOOK", callback_data="svc_facebook"),
        types.InlineKeyboardButton("📸 INSTAGRAM", callback_data="svc_instagram"),
        types.InlineKeyboardButton("🔷 NEW CREATE ACC", callback_data="svc_newacc"),
        types.InlineKeyboardButton("🎵 TIKTOK", callback_data="svc_tiktok")
    )
    return markup

# দেশ নির্বাচন মেনু (২ কলাম বিশিষ্ট AZ স্টাইল)
def country_menu(service):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇧🇯 Benin 638 🔥 (450)", callback_data=f"cnt_Benin_{service}"),
        types.InlineKeyboardButton("🇸🇩 Sudan FB 🔥 (924)", callback_data=f"cnt_Sudan_{service}"),
        types.InlineKeyboardButton("🇲🇿 Mozambique (3420)", callback_data=f"cnt_Mozambique_{service}"),
        types.InlineKeyboardButton("🇸🇳 Senegal FB (3398)", callback_data=f"cnt_Senegal_{service}"),
        types.InlineKeyboardButton("🇱🇷 Liberia (5680)", callback_data=f"cnt_Liberia_{service}"),
        types.InlineKeyboardButton("🇧🇫 Burkina Faso (1796)", callback_data=f"cnt_Burkina_{service}")
    )
    markup.add(types.InlineKeyboardButton("🔙 Back to Services", callback_data="back_to_services"))
    return markup

# --- স্টার্ট কমান্ড ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    get_user(message.chat.id)
    welcome_text = (
        f"💖 **Welcome {message.from_user.first_name}!** 🎉\n\n"
        "🗣️ **Main Menu**\n\n"
        "📥 **Please select an option below:**"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu(message.chat.id))

# ম্যানুয়াল ওটিপি কমান্ড
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

    elif text == "💸 Balance":
        bal, otps = get_user(chat_id)
        bot.send_message(
            chat_id,
            f"💰 **আপনার ব্যালেন্স তথ্য:**\n\n"
            f"💵 বর্তমান ব্যালেন্স: **{bal:.3f} USDT**\n"
            f"📬 সফল ওটিপি: **{otps} টি**\n\n"
            f"*(প্রতিটি সফল ওটিপিতে ০.০১০ USDT যোগ হবে)*",
            parse_mode="Markdown"
        )

    elif text == "😎 Withdraw":
        bal, _ = get_user(chat_id)
        if bal < 0.05:
            bot.send_message(chat_id, f"⚠️ উইথড্র করার জন্য আপনার ব্যালেন্স পর্যাপ্ত নয়!\n\n💵 বর্তমান ব্যালেন্স: **{bal:.3f} USDT**\nসর্বনিম্ন উইথড্র: **0.050 USDT**", parse_mode="Markdown")
        else:
            msg = bot.send_message(chat_id, "💳 **আপনার পেমেন্ট তথ্য দিন:**\n\nবিকাশ / নগদ নম্বর অথবা Binance Pay ID লিখে পাঠান:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, process_withdraw, bal)

    elif text == "🌍 Available Country":
        cursor.execute("SELECT country, COUNT(*) FROM numbers WHERE status = 'AVAILABLE' GROUP BY country")
        counts = cursor.fetchall()
        c_text = "🌐 **বর্তমানে সচল নাম্বারসমূহ:**\n\n"
        if counts:
            for country, cnt in counts:
                c_text += f"• **{country}**: `{cnt}` টি সচল আছে\n"
        else:
            c_text += "1. 🇧🇯 Benin (+229)\n2. 🇸🇩 Sudan (+249)\n3. 🇲🇿 Mozambique (+258)\n\n*(বর্তমানে নতুন রেঞ্জ লোড হচ্ছে...)*"
        bot.send_message(chat_id, c_text, parse_mode="Markdown")

    elif text == "🟢 Live Traffic":
        bot.send_message(chat_id, "🔥 **Traffic Status:** হাই স্পিড ট্রাফিক চালু আছে! এখন ফেসবুক, টিকটক ও ইনস্টাগ্রামে ফুল স্পিডে কোড ঢুকছে।", parse_mode="Markdown")

    elif text == "📍 Support":
        bot.send_message(chat_id, "যেকোনো সমস্যায় যোগাযোগ করুন: @jaazadmin")

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

# --- ইনলাইন বাটন হ্যান্ডলার (AZ স্টাইলে স্মুথ স্ক্রিন বদল) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # ১. সার্ভিস নির্বাচন করলে দেশের লিস্টে যাবে (স্মুথ এডিট)
    if call.data.startswith("svc_"):
        service = call.data.replace("svc_", "").upper()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🌍 **Select your country:** 📥\n(Service: `{service}`)",
            parse_mode="Markdown",
            reply_markup=country_menu(service)
        )

    # ব্যাক বাটন চাপলে আবার সার্ভিসের মেনু আসবে
    elif call.data == "back_to_services":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="🚦 **Select a service:** 📥",
            parse_mode="Markdown",
            reply_markup=services_menu()
        )

    # ২. দেশ নির্বাচন করলে নাম্বার অ্যাসাইন স্ক্রিন আসবে
    elif call.data.startswith("cnt_"):
        parts = call.data.split("_")
        country = parts[1]
        service = parts[2]
        bot.answer_callback_query(call.id)

        # ডেটাবেজ থেকে নির্দিষ্ট দেশের আসল নাম্বার খোঁজা
        cursor.execute("SELECT id, number FROM numbers WHERE status = 'AVAILABLE' AND country LIKE ? LIMIT 1", (f"%{country}%",))
        row = cursor.fetchone()

        if row:
            num_id, num = row
            cursor.execute("UPDATE numbers SET status = 'ASSIGNED', assigned_user = ? WHERE id = ?", (chat_id, num_id))
            conn.commit()
            assigned_number = num
        else:
            # পুলে নাম্বার না থাকলে ডিফল্ট আসল নাম্বার
            fallback_map = {
                "Benin": "+22965620194",
                "Sudan": "+249126297403",
                "Mozambique": "+258861034653",
                "Senegal": "+221773019482"
            }
            assigned_number = fallback_map.get(country, "+22965620194")

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔄 Change Number", callback_data=f"cnt_{country}_{service}"),
            types.InlineKeyboardButton("🌐 Change Country", callback_data=f"svc_{service.lower()}")
        )
        markup.add(types.InlineKeyboardButton("🧪 Test Receive OTP", callback_data=f"testotp_{service}_{assigned_number}"))

        assigned_msg = (
            f"📱 **{country} Number Assigned:**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Service: **{service}**\n"
            f"📞 Number: `{assigned_number}` *(ট্যাপ করে কপি করুন)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏳ **Waiting For OTP...**\n"
            f"*(কোড পাঠালে স্বয়ংক্রিয়ভাবে মেসেজ চলে আসবে)*"
        )
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=assigned_msg,
            parse_mode="Markdown",
            reply_markup=markup
        )

    # টেস্ট ওটিপি বাটন
    elif call.data.startswith("testotp_"):
        parts = call.data.split("_")
        service = parts[1]
        num = parts[2] if len(parts) > 2 else "Number"

        bot.answer_callback_query(call.id, text="নতুন ওটিপি গ্রহণ করা হয়েছে!")
        new_bal = update_balance(chat_id, 0.010, otp_inc=1)

        otp_text = (
            f"📬 **OTP Received!**\n\n"
            f"📌 Service: **{service}**\n"
            f"📞 Number: `{num}`\n"
            f"🔑 OTP Code: `849201`\n\n"
            f"💰 ব্যালেন্সে যোগ হয়েছে: **+0.010 USDT**\n"
            f"💵 বর্তমান ব্যালেন্স: **{new_bal:.3f} USDT**"
        )
        bot.send_message(chat_id, otp_text, parse_mode="Markdown")

    # অ্যাডমিন প্যানেল অপশনসমূহ
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

print("NEOX FAST SMS [VIP AZ-Style UI Engine] চালু হয়েছে...")
bot.infinity_polling()
