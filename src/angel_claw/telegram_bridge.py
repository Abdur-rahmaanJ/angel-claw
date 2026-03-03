import logging
import os
import json
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from .config import settings
from .engine import AngelClawEngine
from .cron import cron_manager
from .models import UserContext

logger = logging.getLogger("angel-claw-telegram")


class TelegramBridge:
    def __init__(self, persist_dir: str = None):
        # We still keep persist_dir and pairings for backward compat or local mode
        self.persist_dir = persist_dir or os.path.join(
            settings.memory_persist_dir, "telegram"
        )
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)
        self.pairings_file = os.path.join(self.persist_dir, "pairings.json")
        self.pairings = self._load_pairings()
        self.token = settings.telegram_token
        self.app = None
        self.engine = AngelClawEngine()
        self._shutdown_event = asyncio.Event()
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
        # Try finding in database first if in shopyo mode
        if settings.auth_mode == "shopyo":
             # This is a bit complex as we need to find user by channel
             # For now we'll rely on the /pair command to establish the link
             pass

        if chat_id in self.pairings:
            await update.message.reply_text(
                f"Welcome back! You are paired with user: {self.pairings[chat_id]}"
            )
        else:
            await update.message.reply_text(
                "Welcome to Angel Claw! 🐾\n\n"
                "To get started, you need to pair this chat with your Angel Claw account.\n"
                "Use the command: `/pair <your-token>`\n\n"
                "You can generate a token in the Angel Claw web interface."
            )

    async def pair_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if not context.args:
            await update.message.reply_text(
                "Please provide a pairing token: `/pair <token>`"
            )
            return

        token = context.args[0]
        
        # Validate token via engine
        try:
            user_id = self.engine.validate_pair_token(token)
            if user_id:
                # Store in database
                user_context = UserContext(
                    user_id=user_id,
                    email="telegram-user@local", # Placeholder
                    roles=["user"],
                    channel_type="telegram",
                    channel_identifier=chat_id
                )
                self.engine.pair_channel(user_context, "telegram", chat_id)
                
                # Also store in local pairings for quick lookups and compatibility
                self.pairings[chat_id] = user_id
                self._save_pairings()
                
                await update.message.reply_text(
                    f"Successfully paired! I am now your Angel Claw."
                )
            else:
                # Backward compatibility: treat token as session_id if validation fails
                # but only if not in strict shopyo mode? 
                # For now, let's allow legacy pairing if token doesn't look like a secure token
                if len(token) < 20: 
                    session_id = token
                    self.pairings[chat_id] = session_id
                    self._save_pairings()
                    await update.message.reply_text(
                        f"Legacy paired with session: `{session_id}`"
                    )
                else:
                    await update.message.reply_text(
                        "Invalid or expired pairing token."
                    )
        except Exception as e:
            logger.error(f"Error during pairing: {e}")
            await update.message.reply_text(f"Error during pairing: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_chat or update.effective_chat.type != "private":
            return
        chat_id = str(update.effective_chat.id)
        
        user_id = self.pairings.get(chat_id)
        if not user_id:
             # Try to find in DB
             if settings.auth_mode == "shopyo":
                 try:
                     from modules.agent.models import Channel
                     from init import db
                     # Note: this needs app context!
                     channel = Channel.query.filter_by(
                         channel_type="telegram",
                         channel_identifier=chat_id
                     ).first()
                     if channel:
                         user_id = channel.user_id
                         self.pairings[chat_id] = user_id
                         self._save_pairings()
                 except:
                     pass

        if not user_id:
            await update.message.reply_text(
                "This chat is not paired. Use `/pair <token>` to start."
            )
            return

        user_input = update.message.text

        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            # We use chat_id as session_id (channel_identifier) for telegram
            user_context = UserContext(
                user_id=user_id,
                email=f"telegram_{chat_id}@angelclaw.local",
                roles=["user"],
                channel_type="telegram",
                channel_identifier=chat_id
            )
            response = await self.engine.execute(user_context, user_input)
            await update.message.reply_text(response.content)
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
        self.app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )

        logger.info("Telegram bridge starting...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

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
                    logger.error(
                        f"Failed to send proactive message to Telegram chat {chat_id}: {e}"
                    )

    async def close(self):
        """Gracefully shutdown the Telegram bridge."""
        logger.info("Shutting down Telegram bridge...")
        self._shutdown_event.set()

        if self.app:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.warning(f"Error during Telegram bridge shutdown: {e}")

        logger.info("Telegram bridge shut down.")


telegram_bridge = TelegramBridge()
