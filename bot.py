import os
import logging
import sqlite3
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    ContextTypes, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8997431493:AAFVJa8I9cM-MTnNHUCn0xptTyRw9MFS_lI"
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "@nhomsharemodallgame")
ADMIN_ID = 7907990385  # ID Admin của ông

admin_states = {}

# --- KHỞI TẠO SQLITE ---
def init_db():
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    # Bảng User
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            xu INTEGER DEFAULT 0,
            joined INTEGER DEFAULT 0,
            has_been_referred INTEGER DEFAULT 0,
            referrer_id INTEGER DEFAULT 0,
            reward_given INTEGER DEFAULT 0
        )
    """)
    # Bảng Kho hàng (Virtual Stocks)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_stocks (
            item_type TEXT PRIMARY KEY,
            stock_count INTEGER DEFAULT 0,
            price INTEGER DEFAULT 50
        )
    """)
    # Bảng Quản lý Giftcode
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS giftcodes (
            code TEXT PRIMARY KEY,
            reward_xu INTEGER,
            max_uses INTEGER,
            used_count INTEGER DEFAULT 0
        )
    """)
    # Bảng Lịch sử người dùng đã nhập code nào (tránh dùng lại)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_redeemed_codes (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    """)
    
    # Khởi tạo mặc định 3 gói sản phẩm nếu chưa có
    cursor.execute("INSERT OR IGNORE INTO virtual_stocks (item_type, stock_count, price) VALUES ('goi_500skin', 0, 100)")
    cursor.execute("INSERT OR IGNORE INTO virtual_stocks (item_type, stock_count, price) VALUES ('goi_anime_1m', 0, 50)")
    cursor.execute("INSERT OR IGNORE INTO virtual_stocks (item_type, stock_count, price) VALUES ('goi_rand_23s', 0, 30)")
    conn.commit()
    conn.close()

init_db()

def get_stock_info(item_type):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    cursor.execute("SELECT stock_count, price FROM virtual_stocks WHERE item_type = ?", (item_type,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"stock": row[0], "price": row[1]}
    return {"stock": 0, "price": 50}

def add_stock_count(item_type, amount):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    # Cộng dồn vào kho hiện tại
    cursor.execute("UPDATE virtual_stocks SET stock_count = stock_count + ? WHERE item_type = ?", (amount, item_type))
    conn.commit()
    conn.close()

def update_item_price(item_type, new_price):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE virtual_stocks SET price = ? WHERE item_type = ?", (new_price, item_type))
    conn.commit()
    conn.close()

def sub_stock_count(item_type, amount=1):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    cursor.execute("SELECT stock_count FROM virtual_stocks WHERE item_type = ?", (item_type,))
    row = cursor.fetchone()
    if row and row[0] >= amount:
        cursor.execute("UPDATE virtual_stocks SET stock_count = stock_count - ? WHERE item_type = ?", (amount, item_type))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def generate_fake_account(item_type):
    acc_id = random.randint(10000000, 99999999)
    password = ''.join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
    
    if item_type == "goi_500skin":
        return f"👑 <b>Acc Chủ Off 3 Tháng (>500 Skin, 1 Skin 3s):</b>\nUsername: <code>acc_500s_{acc_id}@gmail.com</code>\nPassword: <code>{password}</code>\n💎 <i>Thông tin: Hơn 500 skin, kèm theo ít nhất 1 skin 3s cực xịn!</i>\n⚠️ <i>Lưu ý: Đổi mật khẩu ngay sau khi nhận!</i>"
    elif item_type == "goi_anime_1m":
        return f"🎌 <b>Random Skin Anime (Off >1 Tháng, Uy tín >90):</b>\nUsername: <code>anime_1m_{acc_id}@gmail.com</code>\nPassword: <code>{password}</code>\n⭐ <i>Thông tin: Chủ off trên 1 tháng, uy tín >90, có skin anime hợp tác!</i>\n⚠️ <i>Lưu ý: Đổi mật khẩu ngay sau khi nhận!</i>"
    else:
        return f"🎲 <b>Random Skin Ngẫu Nhiên 2s-3s (Uy tín >90):</b>\nUsername: <code>rand_23s_{acc_id}@gmail.com</code>\nPassword: <code>{password}</code>\n🛡️ <i>Thông tin: Uy tín trên 90, sở hữu skin 2s-3s random!</i>\n⚠️ <i>Lưu ý: Đổi mật khẩu ngay sau khi nhận!</i>"

def get_user(user_id):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    cursor.execute("SELECT xu, joined, has_been_referred, referrer_id, reward_given FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, xu, joined) VALUES (?, 0, 0)", (user_id,))
        conn.commit()
        row = (0, 0, 0, 0, 0)
    conn.close()
    return {"xu": row[0], "joined": row[1], "has_been_referred": row[2], "referrer_id": row[3], "reward_given": row[4]}

def update_user_field(user_id, field, value):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def add_user_xu(user_id, amount):
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    cursor.execute("SELECT xu FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        new_xu = row[0] + amount
        cursor.execute("UPDATE users SET xu = ? WHERE user_id = ?", (new_xu, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, xu, joined) VALUES (?, ?, 0)", (user_id, amount))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    get_user(user_id)

    args = context.args
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].split("_")[1])
            if referrer_id != user_id:
                u_data = get_user(user_id)
                if not u_data["has_been_referred"]:
                    update_user_field(user_id, "has_been_referred", 1)
                    update_user_field(user_id, "referrer_id", referrer_id)
        except Exception as e:
            logger.error(f"Lỗi ref: {e}")

    u_data = get_user(user_id)
    if u_data["joined"] == 1:
        await send_main_menu(update, context)
        return

    is_joined = False
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_CHAT_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            is_joined = True
    except Exception as e:
        logger.error(f"Lỗi check join: {e}")

    if is_joined:
        update_user_field(user_id, "joined", 1)
        u_data = get_user(user_id)
        if u_data["has_been_referred"] == 1 and u_data["reward_given"] == 0:
            referrer_id = u_data["referrer_id"]
            add_user_xu(referrer_id, 5)
            update_user_field(user_id, "reward_given", 1)
            try:
                await context.bot.send_message(chat_id=referrer_id, text="🎉 <b>Có người vừa join kênh qua link của bạn! (+5 xu).</b>", parse_mode="HTML")
            except Exception:
                pass
        await send_main_menu(update, context)
        return

    keyboard = [
        [InlineKeyboardButton("📢 Tham gia Kênh", url="https://t.me/nhomsharemodallgame")],
        [InlineKeyboardButton("✅ Tôi đã tham gia", callback_data="check_joined")]
    ]
    if update.message:
        await update.message.reply_text("<b>⚠️ Bạn cần tham gia kênh @nhomsharemodallgame trước khi sử dụng bot!</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def check_joined_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_CHAT_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            update_user_field(user_id, "joined", 1)
            u_data = get_user(user_id)
            if u_data["has_been_referred"] == 1 and u_data["reward_given"] == 0:
                referrer_id = u_data["referrer_id"]
                add_user_xu(referrer_id, 5)
                update_user_field(user_id, "reward_given", 1)
                try:
                    await context.bot.send_message(chat_id=referrer_id, text="🎉 <b>Có người vừa join kênh qua link của bạn! (+5 xu).</b>", parse_mode="HTML")
                except Exception:
                    pass
            try:
                await query.message.delete()
            except Exception:
                pass
            await send_main_menu_callback(query, context)
        else:
            await query.answer("❌ Bạn chưa tham gia kênh!", show_alert=True)
    except Exception:
        await query.answer("❌ Lỗi kiểm tra kênh!", show_alert=True)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user(user_id)
    g1 = get_stock_info("goi_500skin")
    g2 = get_stock_info("goi_anime_1m")
    g3 = get_stock_info("goi_rand_23s")
    
    text = (
        "⚔️ <b>HỆ THỐNG ĐỔI ACC LIÊN QUÂN MOBILE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Acc Off 3T (>500 Skin, 1 Skin 3s):</b> <code>{g1['stock']}</code> acc <i>({g1['price']} xu)</i>\n"
        f"🎌 <b>Random Anime (Off >1T, Uy tín >90):</b> <code>{g2['stock']}</code> acc <i>({g2['price']} xu)</i>\n"
        f"🎲 <b>Random 2s-3s (Uy tín >90):</b> <code>{g3['stock']}</code> acc <i>({g3['price']} xu)</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Số dư tài khoản:</b> <code>{u_data['xu']} xu</code>\n"
        "📌 <i>Cách kiếm thêm xu: Bấm nút 'Kiếm Xu' để lấy link mời bạn bè (1 Ref = 5 xu) hoặc nhập Code từ Admin!</i>"
    )
    keyboard = [
        [InlineKeyboardButton(f"👑 Acc 500+ Skin (Kho: {g1['stock']})", callback_data="doi_goi_500skin")],
        [InlineKeyboardButton(f"🎌 Random Anime Off >1T (Kho: {g2['stock']})", callback_data="doi_goi_anime_1m")],
        [InlineKeyboardButton(f"🎲 Random 2s-3s Uy tín (Kho: {g3['stock']})", callback_data="doi_goi_rand_23s")],
        [InlineKeyboardButton("🎁 Kiếm Xu (Lấy Link Ref)", callback_data="kiem_xu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def send_main_menu_callback(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    u_data = get_user(user_id)
    g1 = get_stock_info("goi_500skin")
    g2 = get_stock_info("goi_anime_1m")
    g3 = get_stock_info("goi_rand_23s")
    
    text = (
        "⚔️ <b>HỆ THỐNG ĐỔI ACC LIÊN QUÂN MOBILE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Acc Off 3T (>500 Skin, 1 Skin 3s):</b> <code>{g1['stock']}</code> acc <i>({g1['price']} xu)</i>\n"
        f"🎌 <b>Random Anime (Off >1T, Uy tín >90):</b> <code>{g2['stock']}</code> acc <i>({g2['price']} xu)</i>\n"
        f"🎲 <b>Random 2s-3s (Uy tín >90):</b> <code>{g3['stock']}</code> acc <i>({g3['price']} xu)</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Số dư tài khoản:</b> <code>{u_data['xu']} xu</code>\n"
        "📌 <i>Cách kiếm thêm xu: Bấm nút 'Kiếm Xu' để lấy link mời bạn bè (1 Ref = 5 xu) hoặc nhập Code từ Admin!</i>"
    )
    keyboard = [
        [InlineKeyboardButton(f"👑 Acc 500+ Skin (Kho: {g1['stock']})", callback_data="doi_goi_500skin")],
        [InlineKeyboardButton(f"🎌 Random Anime Off >1T (Kho: {g2['stock']})", callback_data="doi_goi_anime_1m")],
        [InlineKeyboardButton(f"🎲 Random 2s-3s Uy tín (Kho: {g3['stock']})", callback_data="doi_goi_rand_23s")],
        [InlineKeyboardButton("🎁 Kiếm Xu (Lấy Link Ref)", callback_data="kiem_xu")]
    ]
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "check_joined":
        await check_joined_callback(update, context)
        return

    if data.startswith("add_stock_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Bạn không có quyền này!", show_alert=True)
            return
        item_type = data.replace("add_stock_", "")
        admin_states[user_id] = {"action": "add_stock", "item": item_type}
        await query.answer()
        await query.message.reply_text("📦 <b>Nhập số lượng muốn cộng thêm vào kho:</b>", parse_mode="HTML")
        return

    if data.startswith("set_price_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Bạn không có quyền này!", show_alert=True)
            return
        item_type = data.replace("set_price_", "")
        admin_states[user_id] = {"action": "set_price", "item": item_type}
        await query.answer()
        await query.message.reply_text("💵 <b>Nhập mức giá mới (số xu):</b>", parse_mode="HTML")
        return

    u_data = get_user(user_id)

    for item_key in ["goi_500skin", "goi_anime_1m", "goi_rand_23s"]:
        if data == f"doi_{item_key}":
            info = get_stock_info(item_key)
            price = info["price"]
            if info["stock"] <= 0:
                await query.answer("❌ Kho đã hết hàng!", show_alert=True)
            elif u_data["xu"] < price:
                await query.answer(f"❌ Không đủ {price} xu!", show_alert=True)
            else:
                if sub_stock_count(item_key, 1):
                    add_user_xu(user_id, -price)
                    fake_acc = generate_fake_account(item_key)
                    await query.answer("🎉 Đổi thành công!", show_alert=False)
                    await context.bot.send_message(chat_id=user_id, text=f"✅ <b>GIAO DỊCH THÀNH CÔNG</b>\n\n{fake_acc}", parse_mode="HTML")
                else:
                    await query.answer("❌ Kho đã hết hàng!", show_alert=True)
            return
            
    if data == "kiem_xu":
        ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        await query.answer("Đã tạo link!", show_alert=True)
        await context.bot.send_message(chat_id=user_id, text=f"🔗 <b>Link giới thiệu (1 Ref = 5 xu):</b>\n<code>{ref_link}</code>\n\n💡 <i>Hoặc bạn có thể săn Giftcode từ Admin để nhập nhận xu miễn phí!</i>", parse_mode="HTML")

# --- LỆNH TẠO CODE (Dành cho Admin theo các bước) ---
async def admin_taocode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    admin_states[ADMIN_ID] = {"action": "create_code_step1"}
    await update.message.reply_text("🎟️ <b>TẠO GIFTCODE MỚI</b>\n\n👉 Bước 1: Nhập tên mã code bạn muốn tạo (Ví dụ: <code>Minhducvip</code>):", parse_mode="HTML")

# --- LỆNH NHẬP CODE (Dành cho User) ---
async def nhap_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("❌ Vui lòng nhập mã code theo cú pháp: <code>/nhapcode [Mã_Code]</code>", parse_mode="HTML")
        return
    
    code_input = args[0].strip()
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
    
    # Kiểm tra code có tồn tại không
    cursor.execute("SELECT reward_xu, max_uses, used_count FROM giftcodes WHERE code = ?", (code_input,))
    code_row = cursor.fetchone()
    
    if not code_row:
        conn.close()
        await update.message.reply_text("❌ Mã giftcode không tồn tại hoặc đã hết hạn!")
        return
        
    reward_xu, max_uses, used_count = code_row
    
    # Kiểm tra user này đã nhập code này chưa
    cursor.execute("SELECT 1 FROM user_redeemed_codes WHERE user_id = ? AND code = ?", (user_id, code_input))
    if cursor.fetchone():
        conn.close()
        await update.message.reply_text("❌ Bạn đã sử dụng mã giftcode này rồi, không thể dùng lại!")
        return
        
    # Kiểm tra số lượt dùng còn lại
    if used_count >= max_uses:
        conn.close()
        await update.message.reply_text("❌ Mã giftcode này đã hết lượt sử dụng!")
        return
        
    # Thực hiện cộng xu thật và cập nhật database
    cursor.execute("UPDATE giftcodes SET used_count = used_count + 1 WHERE code = ?", (code_input,))
    cursor.execute("INSERT INTO user_redeemed_codes (user_id, code) VALUES (?, ?)", (user_id, code_input))
    conn.commit()
    conn.close()
    
    add_user_xu(user_id, reward_xu)
    await update.message.reply_text(f"🎉 <b>NHẬP CODE THÀNH CÔNG!</b>\n\n🎁 Bạn nhận được: <b>+{reward_xu} xu</b> vào tài khoản.", parse_mode="HTML")

async def admin_addxu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Cú pháp: /addxu [ID] [Số xu]")
        return
    try:
        target_id = int(args[0])
        amount = int(args[1])
        add_user_xu(target_id, amount)
        await update.message.reply_text("✅ Đã thêm xu!")
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🎁 Bạn được cộng <b>{amount} xu</b> từ Admin!", parse_mode="HTML")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ ID và số xu phải là số!")

async def admin_themkho_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    g1 = get_stock_info("goi_500skin")
    g2 = get_stock_info("goi_anime_1m")
    g3 = get_stock_info("goi_rand_23s")
    keyboard = [
        [InlineKeyboardButton(f"👑 Thêm Acc 500+ Skin (Kho: {g1['stock']})", callback_data="add_stock_goi_500skin")],
        [InlineKeyboardButton(f"🎌 Thêm Random Anime (Kho: {g2['stock']})", callback_data="add_stock_goi_anime_1m")],
        [InlineKeyboardButton(f"🎲 Thêm Random 2s-3s (Kho: {g3['stock']})", callback_data="add_stock_goi_rand_23s")]
    ]
    await update.message.reply_text("📦 <b>CHỌN KHO ĐỂ CỘNG THÊM STOCK:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_chinhgia_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    g1 = get_stock_info("goi_500skin")
    g2 = get_stock_info("goi_anime_1m")
    g3 = get_stock_info("goi_rand_23s")
    keyboard = [
        [InlineKeyboardButton(f"👑 Giá 500+ Skin ({g1['price']} xu)", callback_data="set_price_goi_500skin")],
        [InlineKeyboardButton(f"🎌 Giá Random Anime ({g2['price']} xu)", callback_data="set_price_goi_anime_1m")],
        [InlineKeyboardButton(f"🎲 Giá Random 2s-3s ({g3['price']} xu)", callback_data="set_price_goi_rand_23s")]
    ]
    await update.message.reply_text("💵 <b>CHỌN GÓI ĐỂ CHỈNH GIÁ:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_xemkho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    g1 = get_stock_info("goi_500skin")
    g2 = get_stock_info("goi_anime_1m")
    g3 = get_stock_info("goi_rand_23s")
    await update.message.reply_text(
        "📦 <b>THỐNG KÊ KHO & GIÁ HIỆN TẠI:</b>\n\n"
        f"👑 Acc 500+ Skin: {g1['stock']} acc - {g1['price']} xu\n"
        f"🎌 Random Anime Off >1T: {g2['stock']} acc - {g2['price']} xu\n"
        f"🎲 Random 2s-3s Uy tín: {g3['stock']} acc - {g3['price']} xu",
        parse_mode="HTML"
    )

# --- XỬ LÝ NHẬP LIỆU TEXT CỦA ADMIN (Kho, Giá, Tạo Code theo từng bước) ---
async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
        
    text_input = update.message.text.strip()
    
    if user_id in admin_states:
        state = admin_states[user_id]
        action = state["action"]
        
        # Xử lý quy trình tạo code 3 bước
        if action == "create_code_step1":
            admin_states[user_id] = {"action": "create_code_step2", "code_name": text_input}
            await update.message.reply_text(f"🎟️ Mã code đã chọn: <b>{text_input}</b>\n\n👉 Bước 2: Nhập số xu người dùng sẽ nhận được (Ví dụ: <code>10</code>):", parse_mode="HTML")
            return
            
        elif action == "create_code_step2":
            try:
                xu_val = int(text_input)
                code_name = state["code_name"]
                admin_states[user_id] = {"action": "create_code_step3", "code_name": code_name, "reward_xu": xu_val}
                await update.message.reply_text(f"🎟️ Mã: <b>{code_name}</b> | Số xu: <b>{xu_val}</b>\n\n👉 Bước 3: Nhập số lượng người dùng tối đa được sử dụng code này (Ví dụ: <code>10</code>):", parse_mode="HTML")
            except ValueError:
                await update.message.reply_text("❌ Số xu phải là số nguyên! Vui lòng nhập lại số xu:")
            return
            
        elif action == "create_code_step3":
            try:
                max_uses_val = int(text_input)
                code_name = state["code_name"]
                reward_xu = state["reward_xu"]
                
                # Lưu vào Database
                conn = sqlite3.connect("bot_lienquan.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO giftcodes (code, reward_xu, max_uses, used_count) VALUES (?, ?, ?, 0)", (code_name, reward_xu, max_uses_val))
                conn.commit()
                conn.close()
                
                del admin_states[user_id]
                await update.message.reply_text(f"✅ <b>TẠO GIFTCODE THÀNH CÔNG!</b>\n\n🎟️ Mã: <code>{code_name}</code>\n🎁 Phần thưởng: <b>{reward_xu} xu</b>\n👥 Số lượng lượt dùng: <b>{max_uses_val} người</b>", parse_mode="HTML")
            except ValueError:
                await update.message.reply_text("❌ Số lượng người dùng phải là số nguyên! Nhập lại:")
            return

        # Xử lý kho và giá
        item_type = state.get("item")
        try:
            value = int(text_input)
            if action == "add_stock":
                add_stock_count(item_type, value)
                new_info = get_stock_info(item_type)
                del admin_states[user_id]
                await update.message.reply_text(f"✅ Đã cộng thêm {value} vào kho! Tổng kho hiện tại: <b>{new_info['stock']}</b>", parse_mode="HTML")
            elif action == "set_price":
                update_item_price(item_type, value)
                new_info = get_stock_info(item_type)
                del admin_states[user_id]
                await update.message.reply_text(f"✅ Đã cập nhật giá mới thành: <b>{new_info['price']} xu</b>", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Vui lòng nhập một con số nguyên hợp lệ!")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addxu", admin_addxu))
    application.add_handler(CommandHandler("taocode", admin_taocode))
    application.add_handler(CommandHandler("nhapcode", nhap_code_command))
    application.add_handler(CommandHandler("themkho", admin_themkho_menu))
    application.add_handler(CommandHandler("chinhgia", admin_chinhgia_menu))
    application.add_handler(CommandHandler("kho", admin_xemkho))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text_input))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
 
