# -*- coding: utf-8 -*-
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import re
import requests
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters
)
from telethon.sync import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN, CHANNEL_USERNAME

CHANNEL_LIST = ['@qtdz9', '@m3333m']
user_posting_state = {}
user_query_state = {}
WHITELIST_IDS = []

client = TelegramClient('anon', API_ID, API_HASH)
client.start()

def extract_bin(text):
    matches = re.findall(r'(?<!\d)(\d{6,8})(?!\d)', text)
    return matches[0] if matches else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 骗子查询", callback_data="query_report")],
        [InlineKeyboardButton("✍️ 我要投稿", callback_data="post_report")],
        [InlineKeyboardButton("💳 卡头查询", callback_data="bin_check")],
        [InlineKeyboardButton("📌 骗子曝光频道", url="https://t.me/qtdz9")],
        [InlineKeyboardButton("👥 官方交流群", url="https://t.me/xydbcn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("欢迎使用骗子查询与投稿机器人，请选择：", reply_markup=reply_markup)
from telegram.error import BadRequest

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        # 尽量第一时间先回复，否则就忽略异常
        await query.answer()
    except BadRequest:
        pass                      # 超时了就算了，继续后面的逻辑

    user_id = query.from_user.id
    if query.data == "post_report":
        user_posting_state[user_id] = True
        await query.message.reply_text("请发送你的投稿内容（包含图片 + 诈骗昵称、账号、金额、事件）")
    elif query.data == "query_report":
        user_query_state[user_id] = True
        await query.message.reply_text("请输入你要查询的用户名，例如 @abc123")
    elif query.data == "bin_check":
        await query.message.reply_text("请输入 6~8 位卡号头（例如：415953）")
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.reply_to_message:
        user = msg.reply_to_message.from_user
        await msg.reply_text(f"👤 用户名：@{user.username}\n🆔 Telegram ID：`{user.id}`", parse_mode=ParseMode.MARKDOWN)
    elif context.args:
        uname = context.args[0].lstrip('@')
        try:
            user = await context.bot.get_chat(f"@{uname}")
            await msg.reply_text(f"👤 用户名：@{user.username}\n🆔 Telegram ID：`{user.id}`", parse_mode=ParseMode.MARKDOWN)
        except:
            await msg.reply_text("⚠️ 查询失败，用户名无效或无权限访问。")
    else:
        user = msg.from_user
        await msg.reply_text(f"你的 Telegram ID 是：`{user.id}`", parse_mode=ParseMode.MARKDOWN)

async def get_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法：/uid @用户名")
        return
    uname = context.args[0].lstrip('@')
    try:
        user = await client.get_entity(uname)
        await update.message.reply_text(f"👤 用户名：@{uname}\n🆔 Telegram ID：`{user.id}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ 查询失败：{e}")

async def handle_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    bin_code = extract_bin(text)
    if not bin_code:
        return

    try:
        url = f"https://lookup.binlist.net/{bin_code}"
        headers = {"Accept-Version": "3"}
        resp = requests.get(url, headers=headers, timeout=5, verify=False)

        if resp.status_code != 200:
            await update.message.reply_text(f"❌ 查询失败，接口返回错误码：{resp.status_code}")
            return

        data = resp.json()
        scheme = data.get("scheme", "未知")
        card_type = data.get("type", "未知类型")
        bank = data.get("bank", {}).get("name", "未知银行")
        country = data.get("country", {}).get("name", "未知国家")
        emoji = data.get("country", {}).get("emoji", "")

        msg = (
            f"💳 卡号头：`{bin_code}`\n"
            f"🏦 银行：{bank}\n"
            f"🌍 国家：{emoji} {country}\n"
            f"🔁 类型：{scheme} {card_type}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱️ 查询超时，请稍后再试")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 查询失败：{str(e)}")

async def query_or_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return

    user_id = update.message.from_user.id
    text = update.message.caption or update.message.text or ""
    photos = update.message.photo

    if user_posting_state.get(user_id):
        if not photos or not text:
            await update.message.reply_text("❌ 投稿失败，请发送文字和至少一张图片。")
            return
        if not all(k in text for k in ["昵称", "账号", "@", "金额", "事件"]):
            await update.message.reply_text("❌ 请包含：昵称、账号（@）、金额、事件")
            return
        media = [InputMediaPhoto(p.file_id) for p in photos]
        await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=f"📢 新投稿：\n\n{text}")
        await context.bot.send_media_group(chat_id=CHANNEL_USERNAME, media=media)
        await update.message.reply_text("✅ 投稿成功，感谢你的贡献")
        user_posting_state[user_id] = False
        return

    if user_query_state.get(user_id):
        for ch in CHANNEL_LIST:
            msgs = client.iter_messages(ch, search=text, limit=3)
            async for msg in msgs:
                if text.lower() in (msg.message or "").lower():
                    await update.message.reply_text(f"在频道 {ch} 中发现记录：\n\n{msg.message}")
                    user_query_state[user_id] = False
                    return
        await update.message.reply_text("暂无记录")
        user_query_state[user_id] = False

async def detect_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id in WHITELIST_IDS:
        return
    username = user.username
    if not username:
        return
    for ch in CHANNEL_LIST:
        msgs = client.iter_messages(ch, search=f"@{username}", limit=1)
        async for msg in msgs:
            if f"@{username}" in (msg.message or ""):
                await update.message.reply_text("⚠️ 此用户在曝光名单中，将被封禁。")
                await context.bot.ban_chat_member(update.message.chat_id, user.id)
                return

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("uid", get_uid))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & filters.ChatType.PRIVATE, query_or_post))
    app.add_handler(MessageHandler(filters.TEXT, handle_bin))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, detect_group_message))

    # 全局错误处理器
    async def error_handler(update, context):
        print(f"[ERROR] {context.error}")   # 生产环境可写日志文件
    app.add_error_handler(error_handler)

    print("✅ Bot 正在运行中...")
    app.run_polling()

