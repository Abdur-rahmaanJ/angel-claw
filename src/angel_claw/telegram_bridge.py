import logging
import os
import json
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from .config import settings
from .agent import Agent
from .cron import cron_manager

logger = logging.getLogger("angel-claw-telegram")

class TelegramBridge:
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or os.path.join(settings.memory_persist_dir, "telegram")
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)
        self.pairings_file = os.path.join(self.persist_dir, "pairings.json")
        self.pairings = self._load_pairings()
        self.token = settings.telegram_token
        self.app = None
        cron_manager.register_proactive_handler(self.send_proactive)

    def _load_pairings(self):
        if os.path.exists(self.pairings_file):
            try:
                with open(self.pairings_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading Telegram pairings: {e}")
        return {}

    def _save_pairings(self):
        try:
            with open(self.pairings_file, "w") as f:
                json.dump(self.pairings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving Telegram pairings: {e}")

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if chat_id in self.pairings:
            await update.message.reply_text(f"Welcome back! You are paired with session: {self.pairings[chat_id]}")
        else:
            await update.message.reply_text(
                "Welcome to Angel Claw! 🐾\n\n"
                "To get started, you need to pair this chat with an Angel Claw session.\n"
                "Use the command: `/pair <your-session-id>`\n\n"
                "You can find your session ID in your CLI logs or use 'cli-default' for your main session."
            )

    async def pair_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if not context.args:
            await update.message.reply_text("Please provide a session ID: `/pair <session-id>`")
            return
        
        session_id = context.args[0]
        self.pairings[chat_id] = session_id
        self._save_pairings()
        await update.message.reply_text(f"Successfully paired! I am now your Angel Claw for session: `{session_id}`")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if chat_id not in self.pairings:
            await update.message.reply_text("This chat is not paired. Use `/pair <session-id>` to start.")
            return

        session_id = self.pairings[chat_id]
        user_input = update.message.text
        
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        try:
            agent = Agent(session_id)
            response = await agent.chat(user_input)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in Telegram chat: {e}")
            await update.message.reply_text(f"⚠️ Error: {e}")

    async def run(self):
        if not self.token:
            logger.warning("TELEGRAM_TOKEN not set. Telegram bridge will not start.")
            return

        self.app = ApplicationBuilder().token(self.token).build()
        
        self.app.add_handler(CommandHandler("start", self.start_cmd))
        self.app.add_handler(CommandHandler("pair", self.pair_cmd))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        
        logger.info("Telegram bridge starting...")
        # Note: run_polling is blocking, we might want to run it in a separate thread if needed,
        # but here we'll use it as the main entry point for the bridge.
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        # Keep running
        while True:
            await asyncio.sleep(3600)

    async def send_proactive(self, message: str, user_id: str, session_id: str):
        if not self.app:
            return

        # Find all chat_ids paired with this session_id
        for chat_id, paired_sid in self.pairings.items():
            if paired_sid == session_id:
                try:
                    await self.app.bot.send_message(chat_id=chat_id, text=message)
                    logger.info(f"Sent proactive message to Telegram chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send proactive message to Telegram chat {chat_id}: {e}")

telegram_bridge = TelegramBridge()
