import os
import logging
import sqlite3
import asyncio
import random
from flask import Flask, request
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

TOKEN = "8483501766:AAFSg-dWNLZjmKNQxMKQzZh2KOoyA_YBL5E"
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "@nhomsharemodallgame")
PORT = int(os.getenv("PORT", "8080"))
ADMIN_ID = 7907990385  # ID Admin của ông

# Lưu trạng thái Admin đang thao tác gì (thêm stock hay chỉnh giá)
admin_states = {}

# --- KHỞI TẠO CƠ SỞ DỮ LIỆU SQLITE (KHO ẢO, GIÁ TIỀN, USER) ---
def init_db():
    conn = sqlite3.connect("bot_lienquan.db")
    cursor = conn.cursor()
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_stocks (
            item_type TEXT PRIMARY KEY,
            stock_count INTEGER DEFAULT 0,
            price INTEGER DEFAULT 50
        )
    """)
    # Khởi tạo mặc định 2 kho nếu chưa có (kèm giá mặc định)
    cursor.execute("INSERT OR IGNORE INTO virtual_stocks (item_type, stock_count, price) VALUES ('chu_off', 0, 50)")
    cursor.execute("INSERT OR IGNORE INTO virtual_stocks (item_type, stock_count, price) VALUES ('random_23s', 0, 30)")
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
    if item_type == "chu_off":
        return f"🔒 <b>Tài khoản Chủ Off >3 Tháng (Ao):</b>\nUsername: <code>acc_off_{acc_id}@gmail.com</code>\nPassword: <code>{password}</code>\n⚠️ <i>Lưu ý: Đổi mật khẩu ngay sau khi nhận!</i>"
    else:
        return f"🎲 <b>Tài khoản Random 2s-3s (Ao):</b>\nUsername: <code>rand_{acc_id}@gmail.com</code>\nPassword: <code>{password}</code>\n⚠️ <i>Lưu ý: Đổi mật khẩu ngay sau khi nhận!</i>"

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

flask_app = Flask(__name__)
application = Application.builder().token(TOKEN).updater(None).build()

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
            add_user_xu(referrer_id, 5)  # Thưởng 5 xu cho ref
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
                add_user_xu(referrer_id, 5)  # Thưởng 5 xu cho ref
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
        await query.answer("❌ Lỗi kiểm tra!", show_alert=True)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user(user_id)
    
    chu_off_info = get_stock_info("chu_off")
    rand_23s_info = get_stock_info("random_23s")
    
    text = (
        "⚔️ <b>HỆ THỐNG ĐỔI ACC LIÊN QUÂN MOBILE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 <b>Acc Chủ Off >3 Tháng:</b> <code>{chu_off_info['stock']}</code> acc <i>(Giá: {chu_off_info['price']} xu)</i>\n"
        f"🎲 <b>Random 2s - 3s Uy Tín Cao:</b> <code>{rand_23s_info['stock']}</code> acc <i>(Giá: {rand_23s_info['price']} xu)</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Số dư tài khoản:</b> <code>{u_data['xu']} xu</code>\n"
        "📌 <i>Cách kiếm thêm xu: Bấm nút 'Kiếm Xu' bên dưới để lấy link mời bạn bè (1 Ref = 5 xu).</i>"
    )
    keyboard = [
        [InlineKeyboardButton(f"🔒 Đổi Acc Chủ Off >3 Tháng ({chu_off_info['stock']} còn)", callback_data="doi_chu_off")],
        [InlineKeyboardButton(f"🎲 Đổi Random 2s-3s Uy Tín ({rand_23s_info['stock']} còn)", callback_data="doi_random")],
        [InlineKeyboardButton("🎁 Kiếm Xu (Lấy Link Ref)", callback_data="kiem_xu")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def send_main_menu_callback(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    u_data = get_user(user_id)
    
    chu_off_info = get_stock_info("chu_off")
    rand_23s_info = get_stock_info("random_23s")
    
    text = (
        "⚔️ <b>HỆ THỐNG ĐỔI ACC LIÊN QUÂN MOBILE</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 <b>Acc Chủ Off >3 Tháng:</b> <code>{chu_off_info['stock']}</code> acc <i>(Giá: {chu_off_info['price']} xu)</i>\n"
        f"🎲 <b>Random 2s - 3s Uy Tín Cao:</b> <code>{rand_23s_info['stock']}</code> acc <i>(Giá: {rand_23s_info['price']} xu)</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Số dư tài khoản:</b> <code>{u_data['xu']} xu</code>\n"
        "📌 <i>Cách kiếm thêm xu: Bấm nút 'Kiếm Xu' bên dưới để lấy link mời bạn bè (1 Ref = 5 xu).</i>"
    )
    keyboard = [
        [InlineKeyboardButton(f"🔒 Đổi Acc Chủ Off >3 Tháng ({chu_off_info['stock']} còn)", callback_data="doi_chu_off")],
        [InlineKeyboardButton(f"🎲 Đổi Random 2s-3s Uy Tín ({rand_23s_info['stock']} còn)", callback_data="doi_random")],
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

    # Xử lý chọn kho để tăng stock ảo (Chỉ Admin)
    if data.startswith("add_stock_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Bạn không có quyền này!", show_alert=True)
            return
        
        item_type = data.replace("add_stock_", "")
        admin_states[user_id] = {"action": "add_stock", "item": item_type}
        
        kho_name = "Acc Chủ Off >3 Tháng" if item_type == "chu_off" else "Random 2s-3s Uy Tín"
        await query.answer()
        await query.message.reply_text(
            f"📦 <b>Đã chọn kho: {kho_name}</b>\n\n"
            "👉 Bây giờ bạn hãy **nhập số lượng muốn thêm** vào stock (Ví dụ: gõ <code>50</code>):",
            parse_mode="HTML"
        )
        return

    # Xử lý chọn kho để chỉnh giá (Chỉ Admin)
    if data.startswith("set_price_"):
        if user_id != ADMIN_ID:
            await query.answer("❌ Bạn không có quyền này!", show_alert=True)
            return
        
        item_type = data.replace("set_price_", "")
        admin_states[user_id] = {"action": "set_price", "item": item_type}
        
        kho_name = "Acc Chủ Off >3 Tháng" if item_type == "chu_off" else "Random 2s-3s Uy Tín"
        await query.answer()
        await query.message.reply_text(
            f"💵 <b>Đã chọn kho chỉnh giá: {kho_name}</b>\n\n"
            "👉 Bây giờ bạn hãy **nhập mức giá mới bằng số xu** (Ví dụ: gõ <code>60</code>):",
            parse_mode="HTML"
        )
        return

    u_data = get_user(user_id)

    if data == "doi_chu_off":
        chu_off_info = get_stock_info("chu_off")
        price = chu_off_info["price"]
        if chu_off_info["stock"] <= 0:
            await query.answer("❌ Kho Acc Chủ Off >3 Tháng đã hết hàng!", show_alert=True)
        elif u_data["xu"] < price:
            await query.answer(f"❌ Bạn không đủ {price} xu để đổi!", show_alert=True)
        else:
            if sub_stock_count("chu_off", 1):
                add_user_xu(user_id, -price)
                fake_acc = generate_fake_account("chu_off")
                await query.answer("🎉 Đổi thành công!", show_alert=False)
                await context.bot.send_message(chat_id=user_id, text=f"✅ <b>GIAO DỊCH THÀNH CÔNG</b>\n\n{fake_acc}", parse_mode="HTML")
            else:
                await query.answer("❌ Kho đã hết hàng!", show_alert=True)

    elif data == "doi_random":
        rand_23s_info = get_stock_info("random_23s")
        price = rand_23s_info["price"]
        if rand_23s_info["stock"] <= 0:
            await query.answer("❌ Kho Random 2s-3s đã hết hàng!", show_alert=True)
        elif u_data["xu"] < price:
            await query.answer(f"❌ Bạn không đủ {price} xu để đổi!", show_alert=True)
        else:
            if sub_stock_count("random_23s", 1):
                add_user_xu(user_id, -price)
                fake_acc = generate_fake_account("random_23s")
                await query.answer("🎉 Đổi thành công!", show_alert=False)
                await context.bot.send_message(chat_id=user_id, text=f"✅ <b>GIAO DỊCH THÀNH CÔNG</b>\n\n{fake_acc}", parse_mode="HTML")
            else:
                await query.answer("❌ Kho đã hết hàng!", show_alert=True)
            
    elif data == "kiem_xu":
        ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        await query.answer("Đã tạo link!", show_alert=True)
        await context.bot.send_message(chat_id=user_id, text=f"🔗 <b>Link giới thiệu của bạn (1 Ref = 5 xu):</b>\n<code>{ref_link}</code>", parse_mode="HTML")

# --- CÁC LỆNH ADMIN ---
async def admin_addxu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Dùng cú pháp: /addxu [ID] [Số xu]")
        return
    try:
        target_id = int(args[0])
        amount = int(args[1])
        add_user_xu(target_id, amount)
        await update.message.reply_text("✅ Đã thêm xu hoàn tất!")
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🎁 Bạn được cộng <b>{amount} xu</b> từ Admin!", parse_mode="HTML")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("❌ ID và số xu phải là số!")

async def admin_themkho_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    chu_off_info = get_stock_info("chu_off")
    rand_23s_info = get_stock_info("random_23s")
    
    keyboard = [
        [InlineKeyboardButton(f"🔒 Thêm Stock Chủ Off >3 Tháng (Kho: {chu_off_info['stock']})", callback_data="add_stock_chu_off")],
        [InlineKeyboardButton(f"🎲 Thêm Stock Random 2s-3s (Kho: {rand_23s_info['stock']})", callback_data="add_stock_random_23s")]
    ]
    await update.message.reply_text(
        "📦 <b>BẠN MUỐN TĂNG STOCK CHO KHO NÀO?</b>\n"
        "Hãy bấm vào nút bên dưới:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def admin_chinhgia_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    chu_off_info = get_stock_info("chu_off")
    rand_23s_info = get_stock_info("random_23s")
    
    keyboard = [
        [InlineKeyboardButton(f"🔒 Chỉnh Giá Chủ Off >3 Tháng (Giá hiện tại: {chu_off_info['price']} xu)", callback_data="set_price_chu_off")],
        [InlineKeyboardButton(f"🎲 Chỉnh Giá Random 2s-3s (Giá hiện tại: {rand_23s_info['price']} xu)", callback_data="set_price_random_23s")]
    ]
    await update.message.reply_text(
        "💵 <b>BẠN MUỐN CHỈNH GIÁ CHO KHO NÀO?</b>\n"
        "Hãy bấm vào nút bên dưới để tùy chỉnh:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def admin_xemkho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    chu_off_info = get_stock_info("chu_off")
    rand_23s_info = get_stock_info("random_23s")
    await update.message.reply_text(
        "📦 <b>THỐNG KÊ KHO HÀNG & GIÁ HIỆN TẠI:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 <b>Acc Chủ Off >3 Tháng:</b>\n"
        f" - Tồn kho: <b>{chu_off_info['stock']}</b> acc\n"
        f" - Giá bán: <b>{chu_off_info['price']} xu</b>\n\n"
        f"🎲 <b>Random 2s-3s Uy Tín:</b>\n"
        f" - Tồn kho: <b>{rand_23s_info['stock']}</b> acc\n"
        f" - Giá bán: <b>{rand_23s_info['price']} xu</b>",
        parse_mode="HTML"
    )

# Xử lý nội dung Admin nhập vào sau khi bấm Thêm Kho hoặc Chỉnh Giá
async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    if user_id in admin_states:
        state = admin_states[user_id]
        action = state["action"]
        item_type = state["item"]
        text_input = update.message.text.strip()
        
        try:
            value = int(text_input)
            kho_name = "Acc Chủ Off >3 Tháng" if item_type == "chu_off" else "Random 2s-3s Uy Tín"
            
            if action == "add_stock":
                add_stock_count(item_type, value)
                new_info = get_stock_info(item_type)
                del admin_states[user_id]
                await update.message.reply_text(
                    f"✅ <b>ĐÃ THÊM STOCK THÀNH CÔNG!</b>\n"
                    f"📁 Kho: <b>{kho_name}</b>\n"
                    f"➕ Cộng thêm: <b>+{value}</b>\n"
                    f"📊 Tổng tồn kho mới: <b>{new_info['stock']} acc</b>",
                    parse_mode="HTML"
                )
            elif action == "set_price":
                update_item_price(item_type, value)
                new_info = get_stock_info(item_type)
                del admin_states[user_id]
                await update.message.reply_text(
                    f"✅ <b>CẬP NHẬT GIÁ THÀNH CÔNG!</b>\n"
                    f"📁 Kho: <b>{kho_name}</b>\n"
                    f"💵 Giá mới: <b>{new_info['price']} xu</b>",
                    parse_mode="HTML"
                )
        except ValueError:
            await update.message.reply_text("❌ Vui lòng chỉ nhập một con số nguyên hợp lệ (Ví dụ: <code>50</code>)", parse_mode="HTML")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("addxu", admin_addxu))
application.add_handler(CommandHandler("themkho", admin_themkho_menu))
application.add_handler(CommandHandler("chinhgia", admin_chinhgia_menu))
application.add_handler(CommandHandler("kho", admin_xemkho))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text_input))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    async def run_update():
        if not application.running:
            await application.initialize()
        await application.process_update(update)
    
    future = asyncio.run_coroutine_threadsafe(run_update(), loop)
    future.result()
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def index():
    return "Bot Liên Quân running 24/7!", 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
