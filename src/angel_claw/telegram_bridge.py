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
        # Use standardized path for package deployment
        self.persist_dir = persist_dir or settings.telegram_persist_dir
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
        logger.info(f"Received /pair command from {chat_id}")
        
        try:
            if not context.args:
                await update.message.reply_text(
                    "Please provide a pairing token: `/pair <token>`"
                )
                return

            token = context.args[0]
            # Immediate acknowledgement
            await update.message.reply_text(f"🔄 Validating token `{token}`...")
            
            logger.info(f"Attempting to pair chat {chat_id} with token: {token}")
            
            # Validate token via engine
            user_id = self.engine.validate_pair_token(token)
            if user_id:
                logger.info(f"Token valid. Pairing chat {chat_id} with user {user_id}")
                # Store in database
                user_context = UserContext(
                    user_id=user_id,
                    email="telegram-user@local",
                    roles=["user"],
                    channel_type="telegram",
                    channel_identifier=chat_id
                )
                self.engine.pair_channel(user_context, "telegram", chat_id)
                
                # Also store in local pairings
                self.pairings[chat_id] = user_id
                self._save_pairings()
                
                await update.message.reply_text(
                    "✅ Successfully paired! I am now your Angel Claw.\n"
                    "You can now send me messages directly."
                )
            else:
                logger.warning(f"Invalid token attempt from {chat_id}: {token}")
                # Backward compatibility
                if len(token) > 10: 
                    session_id = token
                    self.pairings[chat_id] = session_id
                    self._save_pairings()
                    await update.message.reply_text(
                        f"✅ Legacy paired with session: `{session_id}`"
                    )
                else:
                    await update.message.reply_text(
                        "❌ Invalid or expired pairing token.\n"
                        "Please generate a new 8-digit token from your web dashboard."
                    )
        except Exception as e:
            logger.error(f"Error during pairing for chat {chat_id}: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ An error occurred during pairing: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_chat or update.effective_chat.type != "private":
            return
        
        if not update.message or not update.message.text:
            return

        # Explicitly skip commands that might have leaked through filters
        if update.message.text.startswith('/'):
            logger.debug(f"Skipping command-like message in handle_message: {update.message.text}")
            return

        chat_id = str(update.effective_chat.id)
        logger.info(f"Handling message from {chat_id}: {update.message.text[:50]}...")
        
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

        from telegram.request import HTTPXRequest
        import telegram

        # Use a longer timeout for slow networks
        trequest = HTTPXRequest(connect_timeout=20, read_timeout=20)
        self.app = ApplicationBuilder().token(self.token).request(trequest).build()

        self.app.add_handler(CommandHandler("start", self.start_cmd))
        self.app.add_handler(CommandHandler("pair", self.pair_cmd))
        self.app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )

        logger.info("Telegram bridge starting...")
        
        max_retries = 5
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling()
                logger.info("Telegram bridge started successfully.")
                break
            except (telegram.error.TimedOut, telegram.error.NetworkError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Telegram initialization timed out (attempt {attempt+1}/{max_retries}). Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Telegram bridge failed to start after {max_retries} attempts: {e}")
                    return
            except Exception as e:
                logger.error(f"Unexpected error starting Telegram bridge: {e}", exc_info=True)
                return

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
