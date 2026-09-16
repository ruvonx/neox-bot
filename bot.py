import telebot
from telebot import types
import sqlite3
import time
import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Render 24/7 Web Server ---
PORT = int(os.environ.get("PORT", 10000))

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"NEOX Bot is Running 24/7!")
        
    def log_message(self, format, *args):
        return

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# --- Bot Config ---
BOT_TOKEN = "8843310193:AAH9ViXDNIi94hQnuZLjmiLe3UhtaaUM77U"
ADMIN_ID = 7241161752

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect("bot_users.db", check_same_thread=False)
cursor = conn.cursor()

# ইউজার ও উইথড্র টেবিল
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

# আসল নাম্বারের ডেটাবেজ টেবিল
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
        types.InlineKeyboardButton("📘 FACEBOOK", callback_data="srv_facebook"),
        types.InlineKeyboardButton("🔷 NEW CREATE ACC", callback_data="srv_newacc"),
        types.InlineKeyboardButton("🎵 TIKTOK", callback_data="srv_tiktok")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    get_user(message.chat.id)
    welcome_text = (
        f"🎉 Welcome {message.from_user.first_name}!\n\n"
        "⚡ NEOX FAST SMS বটে আপনাকে স্বাগতম।\n"
        "কাজ শুরু করতে নিচের মেনু বাটনগুলো ব্যবহার করুন।"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(message.chat.id))

# ওটিপি পাঠানোর অ্যাডমিন কমান্ড: /otp <নম্বর> <কোড>
@bot.message_handler(commands=['otp'])
def admin_send_otp(message):
    if message.chat.id != ADMIN_ID:
        return

    try:
        _, num, code = message.text.split()
        cursor.execute("SELECT assigned_user FROM numbers WHERE number = ?", (num,))
        res = cursor.fetchone()

        if res and res[0]:
            target_user = res[0]
            new_bal = update_balance(target_user, 0.010, otp_inc=1)
            
            # নাম্বারটি আবার ফ্রি করে দেওয়া
            cursor.execute("UPDATE numbers SET status = 'AVAILABLE', assigned_user = NULL WHERE number = ?", (num,))
            conn.commit()

            # ইউজারকে ওটিপি পাঠানো
            otp_text = (
                f"📬 OTP Received!\n\n"
                f"📞 Number: {num}\n"
                f"🔑 OTP Code: `{code}`\n\n"
                f"💰 ব্যালেন্সে যোগ হয়েছে: +0.010 USDT\n"
                f"💵 বর্তমান ব্যালেন্স: {new_bal:.3f} USDT"
            )
            bot.send_message(target_user, otp_text, parse_mode="Markdown")
            bot.send_message(ADMIN_ID, f"✅ সফলভাবে ইউজার `{target_user}` এর কাছে ওটিপি পাঠানো হয়েছে এবং ব্যালেন্স যোগ হয়েছে!")
        else:
            bot.send_message(ADMIN_ID, f"⚠️ এই নম্বরটি ({num}) বর্তমানে কোনো ইউজারের কাছে সক্রিয় নেই!")
    except Exception as e:
        bot.send_message(ADMIN_ID, "⚠️ ফরম্যাট ভুল! সঠিক ফরম্যাট লিখুন:\n`/otp +258861034653 123456`", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: True)
def handle_menu(message):
    chat_id = message.chat.id
    text = message.text

    if text == "☎️ Get Number":
        bot.send_message(chat_id, "🚦 Select a service: 📥", reply_markup=services_menu())

    elif text == "💸 Balance":
        bal, otps = get_user(chat_id)
        msg_bal = (
            f"💰 আপনার ব্যালেন্স তথ্য:\n\n"
            f"💵 বর্তমান ব্যালেন্স: {bal:.3f} USDT\n"
            f"📬 সফল ওটিপি: {otps} টি\n\n"
            f"(প্রতিটি সফল ওটিপির জন্য ০.০১০ USDT যোগ হবে)"
        )
        bot.send_message(chat_id, msg_bal)

    elif text == "😎 Withdraw":
        bal, _ = get_user(chat_id)
        if bal < 0.05:
            bot.send_message(chat_id, f"⚠️ উইথড্র করার জন্য আপনার ব্যালেন্স পর্যাপ্ত নয়!\n\n💵 বর্তমান ব্যালেন্স: {bal:.3f} USDT\nসর্বনিম্ন উইথড্র: 0.050 USDT")
        else:
            msg = bot.send_message(chat_id, "💳 আপনার পেমেন্ট তথ্য দিন:\n\nবিকাশ / নগদ নাম্বার অথবা Binance Pay ID লিখে পাঠান:")
            bot.register_next_step_handler(msg, process_withdraw, bal)

    elif text == "🌍 Available Country":
        cursor.execute("SELECT country, COUNT(*) FROM numbers WHERE status = 'AVAILABLE' GROUP BY country")
        counts = cursor.fetchall()
        c_text = "🌐 বর্তমানে সচল নাম্বারসমূহ:\n\n"
        if counts:
            for country, cnt in counts:
                c_text += f"• {country}: {cnt} টি উপলব্ধ\n"
        else:
            c_text += "1. Mozambique (+258)\n2. Senegal (+221)\n(বর্তমানে নতুন নাম্বার লোড করা হচ্ছে...)"
        bot.send_message(chat_id, c_text)

    elif text == "🟢 Live Traffic":
        bot.send_message(chat_id, "🔥 Traffic Status: হাই স্পিড ট্রাফিক চালু আছে! এখন ফেসবুক ও টিকটকে সবচেয়ে বেশি কোড ঢুকছে।")

    elif text == "📍 Support":
        bot.send_message(chat_id, "যেকোনো সমস্যায় যোগাযোগ করুন: @jaazadmin")

    elif text == "⚙️ ADMIN PANEL" and chat_id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*), SUM(balance), SUM(total_otp) FROM users")
        total_users, total_bal, total_otps = cursor.fetchone()
        total_bal = total_bal if total_bal else 0.0
        total_otps = total_otps if total_otps else 0

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
            f"👑 ADMIN CONTROL PANEL 👑\n\n"
            f"👥 মোট ইউজার: {total_users} জন\n"
            f"📬 মোট ওটিপি সম্পন্ন: {total_otps} টি\n"
            f"💰 সিস্টেম ব্যালেন্স: {total_bal:.3f} USDT\n"
            f"📱 পুলে সচল আসল নাম্বার: {avail_num} টি\n\n"
            f"💡 ওটিপি পাঠাতে লিখুন:\n`/otp <নম্বর> <কোড>`"
        )
        bot.send_message(chat_id, admin_text, reply_markup=markup, parse_mode="Markdown")

def process_withdraw(message, balance):
    chat_id = message.chat.id
    details = message.text

    update_balance(chat_id, -balance)
    
    cursor.execute("INSERT INTO withdrawals (user_id, amount, method_details, status) VALUES (?, ?, ?, 'PENDING')",
                   (chat_id, balance, details))
    conn.commit()

    bot.send_message(chat_id, "✅ উইথড্র রিকোয়েস্ট সফল হয়েছে!\nঅ্যাডমিন যাচাই করে পেমেন্ট পাঠিয়ে দেবেন।")

    admin_notify = (
        f"🚨 নতুন উইথড্র রিকোয়েস্ট!\n\n"
        f"👤 ইউজার আইডি: {chat_id}\n"
        f"💵 পরিমাণ: {balance:.3f} USDT\n"
        f"📝 পেমেন্ট একাউন্ট: {details}"
    )
    bot.send_message(ADMIN_ID, admin_notify)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data.startswith("srv_"):
        service = call.data.replace("srv_", "").upper()
        bot.answer_callback_query(call.id)
        
        # ডেটাবেজ থেকে একটি ফ্রি আসল নাম্বার খোঁজা
        cursor.execute("SELECT id, number, country FROM numbers WHERE status = 'AVAILABLE' LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            num_id, num, country = row
            # নাম্বারটি এই ইউজারের জন্য লক করে দেওয়া
            cursor.execute("UPDATE numbers SET status = 'ASSIGNED', assigned_user = ? WHERE id = ?", (chat_id, num_id))
            conn.commit()
            assigned_number = num
            assigned_country = country
        else:
            # পুলে কোনো নাম্বার না থাকলে ডিফল্ট ব্যাকআপ নাম্বার দেখাবে
            assigned_number = "+258861034653"
            assigned_country = "Mozambique"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔄 Change Number", callback_data="change_num"),
            types.InlineKeyboardButton("🧪 Test Receive OTP", callback_data=f"testotp_{service}_{assigned_number}")
        )
        
        assigned_msg = (
            f"🇲🇿 {assigned_country} Number Assigned:\n\n"
            f"📌 Service: {service}\n"
            f"📞 Number: `{assigned_number}` (ক্লিক করে কপি করুন)\n\n"
            f"⏳ Waiting For OTP...\n"
            f"(ওটিপি আসলে স্বয়ংক্রিয়ভাবে মেসেজ পাবেন)"
        )
        bot.send_message(chat_id, assigned_msg, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("testotp_"):
        parts = call.data.split("_")
        service = parts[1]
        num = parts[2] if len(parts) > 2 else "+258861034653"

        bot.answer_callback_query(call.id, text="নতুন ওটিপি গ্রহণ করা হয়েছে!")
        new_bal = update_balance(chat_id, 0.010, otp_inc=1)

        otp_text = (
            f"📬 OTP Received!\n\n"
            f"📌 Service: {service}\n"
            f"📞 Number: {num}\n"
            f"🔑 OTP Code: `754129`\n"
            f"💰 ব্যালেন্সে যোগ হয়েছে: +0.010 USDT\n"
            f"💵 মোট ব্যালেন্স: {new_bal:.3f} USDT"
        )
        bot.send_message(chat_id, otp_text, parse_mode="Markdown")

    # অ্যাডমিন প্যানেলে আসল নাম্বার যোগ করার অপশন
    elif call.data == "admin_add_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id, 
            "📱 **আসল নাম্বার যোগ করার নিয়ম:**\n\n"
            "দেশ এবং নাম্বারগুলো এভাবে লিখে পাঠান:\n"
            "`দেশ নম্বর১ নম্বর২ নম্বর৩`\n\n"
            "উদাহরণ:\n"
            "`Mozambique +258861111111 +258862222222 +258863333333`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, do_add_numbers)

    elif call.data == "admin_list_num" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        cursor.execute("SELECT country, number, status FROM numbers LIMIT 15")
        nums = cursor.fetchall()
        if nums:
            list_text = "📋 **বটের নাম্বার লিস্ট (সর্বশেষ ১৫টি):**\n\n"
            for c, n, s in nums:
                list_text += f"• `{n}` ({c}) - {s}\n"
        else:
            list_text = "পুলে এখনো কোনো অতিরিক্ত আসল নাম্বার যোগ করা হয়নি।"
        bot.send_message(chat_id, list_text, parse_mode="Markdown")

    elif call.data == "admin_broadcast" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 আপনি সকল ইউজারকে কী মেসেজ পাঠাতে চান, তা লিখে পাঠান:")
        bot.register_next_step_handler(msg, do_broadcast)

    elif call.data == "admin_addbal" and chat_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "ইউজারের আইডি এবং ব্যালেন্স এভাবে পাঠান:\n`আইডি ব্যালেন্স` (যেমন: `7241161752 0.50`)")
        bot.register_next_step_handler(msg, do_add_balance)

def do_add_numbers(message):
    try:
        parts = message.text.split()
        country = parts[0]
        number_list = parts[1:]
        added = 0
        for num in number_list:
            try:
                cursor.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country, num))
                added += 1
            except:
                pass
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে **{country}** দেশের **{added} টি নতুন আসল নাম্বার** পুলে যোগ করা হয়েছে!")
    except Exception as e:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট! উদাহরণ অনুযায়ী লিখুন:\n`Mozambique +25812345678 +25898765432`", parse_mode="Markdown")

def do_broadcast(message):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0
    for (u_id,) in users:
        try:
            bot.send_message(u_id, f"📢 ADMIN NOTICE:\n\n{message.text}")
            count += 1
            time.sleep(0.05)
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ সফলভাবে {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে!")

def do_add_balance(message):
    try:
        u_id, amt = message.text.split()
        u_id = int(u_id)
        amt = float(amt)
        new_b = update_balance(u_id, amt)
        bot.send_message(ADMIN_ID, f"✅ ইউজার {u_id} এর ব্যালেন্সে {amt} যোগ হয়েছে।")
        bot.send_message(u_id, f"🎉 আপনার একাউন্টে অ্যাডমিন +{amt:.3f} USDT যোগ করেছেন!")
    except:
        bot.send_message(ADMIN_ID, "⚠️ ভুল ফরম্যাট! সঠিক ফরম্যাট: UserID Amount")

print("NEOX FAST SMS আসল নাম্বার ম্যানেজমেন্ট সহ চালু হয়েছে...")
bot.infinity_polling()
