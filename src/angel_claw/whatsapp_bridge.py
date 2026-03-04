import os
import json
import logging
import threading
import queue
import time
import asyncio
from typing import Optional, Dict, Any

# Use Synchronous Client for everything to avoid asyncio loop conflicts
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv, QREv
from neonize.utils.jid import build_jid, Jid2String
from .config import settings
from .engine import AngelClawEngine
from .cron import cron_manager
from .models import UserContext

# Set neonize logging to warning to avoid too much noise
logging.getLogger("neonize").setLevel(logging.CRITICAL)
logging.getLogger("whatsmeow").setLevel(logging.CRITICAL)
logging.getLogger("Whatsmeow").setLevel(logging.CRITICAL)
logger = logging.getLogger("angel-claw-whatsapp")


class WhatsAppBridge:
    def __init__(self, persist_dir: str = None):
        # Use standardized path for package deployment
        self.persist_dir = persist_dir or settings.whatsapp_persist_dir
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)

        self.pairings_file = os.path.join(self.persist_dir, "pairings.json")
        self.db_file = os.path.join(self.persist_dir, "session.db")
        self.pairings = self._load_pairings()
        self._pairings_lock = threading.Lock()
        self.enabled = settings.whatsapp_enabled
        self.client = None
        self.main_thread = None
        self.sender_thread = None
        self.out_queue = queue.Queue()
        self.process_loop = None
        self.engine = AngelClawEngine()

        # Register for proactive reminders
        cron_manager.register_proactive_handler(self.send_proactive)

    def _start_process_loop(self):
        """Starts a background thread with an asyncio loop for agent processing."""

        def _runner():
            self.process_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.process_loop)
            self.process_loop.run_forever()

        threading.Thread(target=_runner, daemon=True).start()

    def _load_pairings(self):
        if os.path.exists(self.pairings_file):
            try:
                with open(self.pairings_file, "r") as f:
                    data = json.load(f)
                    return {k: v for k, v in data.items() if "\n" not in k}
            except Exception as e:
                logger.error(f"Error loading WhatsApp pairings: {e}")
        return {}

    def _save_pairings(self):
        with self._pairings_lock:
            try:
                with open(self.pairings_file, "w") as f:
                    json.dump(self.pairings, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving WhatsApp pairings: {e}")

    def _get_pairing(self, sender_id: str) -> Optional[str]:
        with self._pairings_lock:
            return self.pairings.get(sender_id)

    def _set_pairing(self, sender_id: str, user_id: str):
        with self._pairings_lock:
            self.pairings[sender_id] = user_id
            self._save_pairings()

    def _get_all_pairings(self) -> Dict[str, str]:
        with self._pairings_lock:
            return dict(self.pairings)

    async def run(self):
        if not self.enabled:
            return

        has_session = os.path.exists(self.db_file)
        import sys

        is_login_cmd = "login-whatsapp" in sys.argv

        if not has_session and not is_login_cmd:
            logger.warning(
                "WhatsApp session not found. Please run 'angel-claw login-whatsapp' to link your account."
            )
            return

        qr_queue = queue.Queue()
        connected_event = threading.Event()

        def _sync_client_runner():
            logger.info("Initializing WhatsApp client...")
            self.client = NewClient(self.db_file)

            @self.client.event(QREv)
            def on_qr(_: NewClient, qr: QREv):
                if is_login_cmd:
                    try:
                        qr_str = qr if isinstance(qr, str) else qr.Code
                    except AttributeError:
                        qr_str = str(qr)
                    qr_queue.put(qr_str)
                else:
                    logger.warning(
                        "QR Code requested but not in login mode. Session may have expired."
                    )

            @self.client.event(ConnectedEv)
            def on_connected(_: NewClient, __: ConnectedEv):
                logger.info("⚡ WhatsApp Connected and Authenticated!")
                connected_event.set()

            @self.client.event(MessageEv)
            def on_message(client: NewClient, message: MessageEv):
                logger.debug(f"Received raw message event: {message}")
                self._handle_message_sync(client, message)

            try:
                logger.info("Connecting to WhatsApp servers...")
                self.client.connect()
            except Exception as e:
                logger.error(f"WhatsApp connection failed: {e}")

        # Start Main Client Thread
        self.main_thread = threading.Thread(target=_sync_client_runner, daemon=True)
        self.main_thread.start()

        # Start Outgoing Sender Thread
        self.sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()

        # Start Agent Processing Loop
        self._start_process_loop()

        if is_login_cmd:
            print("\nWaiting for WhatsApp QR Code...")
            try:
                while not connected_event.is_set():
                    try:
                        qr_code_data = qr_queue.get(timeout=1)
                        import qrcode

                        qr_gen = qrcode.QRCode()
                        qr_gen.add_data(qr_code_data)
                        print(
                            "\n"
                            + "=" * 40
                            + "\n   SCAN THIS QR CODE WITH WHATSAPP\n"
                            + "=" * 40
                            + "\n"
                        )
                        qr_gen.print_ascii()
                        print("\nWaiting for scan...\n")
                    except queue.Empty:
                        pass
                    if connected_event.is_set():
                        print("\n✅ Successfully linked! You can now exit (Ctrl+C).")
                        while True:
                            time.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            return

        await asyncio.sleep(0.1)

    def _sender_worker(self):
        """Worker thread that drains the outgoing message queue."""
        while True:
            try:
                jid, message = self.out_queue.get(timeout=1)

                # Wait for stable connection
                if settings.debug:
                    print(
                        f"\n[DEBUG WhatsApp] Outgoing message to {jid} queued.",
                        flush=True,
                    )

                while not self.client or not getattr(
                    self.client, "is_logged_in", False
                ):
                    if settings.debug:
                        print(
                            f"\n[DEBUG WhatsApp] Waiting for connection to send message...",
                            flush=True,
                        )
                    time.sleep(2)

                success = False
                for attempt in range(3):
                    try:
                        # Small delay to ensure Go bridge is ready for usync
                        if attempt > 0:
                            time.sleep(3)

                        self.client.send_message(jid, message)
                        if settings.debug:
                            print(
                                f"\n[DEBUG WhatsApp] Message sent successfully to {jid}.",
                                flush=True,
                            )
                        success = True
                        break
                    except Exception as e:
                        logger.warning(
                            f"WhatsApp send attempt {attempt + 1} failed: {e}"
                        )
                        if settings.debug:
                            print(
                                f"\n[DEBUG WhatsApp] Send attempt {attempt + 1} failed: {e}",
                                flush=True,
                            )
                        # Exponential backoff
                        time.sleep(2 * (attempt + 1))

                if not success:
                    logger.error(f"Failed to send message to {jid} after 3 attempts.")

                self.out_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in WhatsApp sender worker: {e}")

    def _handle_message_sync(self, client: NewClient, message: MessageEv):
        try:
            # Get the JID and extract the clean user ID (phone number or LID)
            chat_jid = message.Info.MessageSource.Chat

            # Only allow private chats (users and hidden users)
            # This ignores groups (@g.us), status updates (@broadcast), and newsletters (@newsletter)
            if chat_jid.Server not in ("s.whatsapp.net", "lid"):
                return

            sender_id = Jid2String(chat_jid)

            # Extract text
            text = ""
            if message.Message.conversation:
                text = message.Message.conversation
            elif (
                message.Message.extendedTextMessage
                and message.Message.extendedTextMessage.text
            ):
                text = message.Message.extendedTextMessage.text

            if not text:
                return

            # Use 'Bot: ' prefix check instead of IsFromMe
            # This allows responding to 'Message to Yourself' where IsFromMe is always True
            if text.startswith("Bot: "):
                return

            # Explicitly ignore status updates if they somehow bypass the server check
            if chat_jid.User == "status":
                return

            logger.info(f"Incoming WhatsApp from {sender_id}: {text}")

            # Always reply to the Chat JID
            threading.Thread(
                target=lambda: asyncio.run(
                    self._process_agent_response(client, chat_jid, sender_id, text)
                ),
                daemon=True,
            ).start()

        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {e}")

    async def _process_agent_response(
        self, client: NewClient, sender_jid: Any, sender_id: str, text: str
    ):
        if text.startswith("/"):
            await self._handle_command(client, sender_jid, sender_id, text)
        else:
            await self._handle_chat(client, sender_jid, sender_id, text)

    async def _handle_command(
        self, client: NewClient, sender_jid: Any, sender_id: str, text: str
    ):
        parts = text.split()
        cmd = parts[0].lower()
        if cmd == "/pair" and len(parts) > 1:
            token = parts[1]

            # Validate token via engine
            try:
                user_id = self.engine.validate_pair_token(token)
                if user_id:
                    # Store in database
                    user_context = UserContext(
                        user_id=user_id,
                        email="whatsapp-user@local",  # Placeholder
                        roles=["user"],
                        channel_type="whatsapp",
                        channel_identifier=sender_id,
                    )
                    self.engine.pair_channel(user_context, "whatsapp", sender_id)

                    # Also store in local pairings
                    self._set_pairing(sender_id, user_id)

                    self.out_queue.put(
                        (
                            sender_jid,
                            f"Bot: ✅ Successfully paired! I am now your Angel Claw.",
                        )
                    )
                else:
                    # Backward compatibility: legacy session_id pairing
                    if len(token) < 20:
                        session_id = token
                        
                        # Store in database for UI status
                        user_context = UserContext(
                            user_id=session_id, # In legacy, token was user_id
                            email="whatsapp-user@local",
                            roles=["user"],
                            channel_type="whatsapp",
                            channel_identifier=sender_id,
                        )
                        self.engine.pair_channel(user_context, "whatsapp", sender_id)

                        self._set_pairing(sender_id, session_id)
                        self.out_queue.put(
                            (sender_jid, f"Bot: ✅ Legacy paired with session: `{session_id}`")
                        )
                    else:
                        self.out_queue.put(
                            (sender_jid, "Bot: ❌ Invalid or expired pairing token.")
                        )
            except Exception as e:
                logger.error(f"Error during WhatsApp pairing: {e}")
                self.out_queue.put((sender_jid, f"Bot: ⚠️ Error during pairing: {e}"))
        elif cmd == "/start":
            self.out_queue.put(
                (
                    sender_jid,
                    "Bot: 👋 Welcome to Angel Claw!\nUse `/pair <token>` to connect your account.",
                )
            )

    async def _handle_chat(
        self, client: NewClient, sender_jid: Any, sender_id: str, text: str
    ):
        # sender_id is already a clean string from Jid2String
        user_id = self._get_pairing(sender_id)

        # Fallback for old pairings that only stored the phone number
        if not user_id and "@" in sender_id:
            phone_number = sender_id.split("@")[0]
            user_id = self._get_pairing(phone_number)

        if not user_id:
            logger.warning(f"Unpaired message from {sender_id}")
            self.out_queue.put(
                (
                    sender_jid,
                    "Bot: ⚠️ Chat not paired. Use `/pair <token>` to start.",
                )
            )
            return

        logger.info(f"Processing message for user {user_id} from {sender_id}")
        try:
            user_context = UserContext(
                user_id=str(user_id),
                email=f"whatsapp_{sender_id}@angelclaw.local",
                roles=["user"],
                channel_type="whatsapp",
                channel_identifier=sender_id,
            )
            response = await self.engine.execute(user_context, text)
            logger.info(f"Sending response to {sender_id}")
            self.out_queue.put((sender_jid, f"Bot: {response.content}"))
        except Exception as e:
            logger.error(f"Error in WhatsApp chat: {e}", exc_info=True)
            self.out_queue.put((sender_jid, f"Bot: ⚠️ Error processing your request."))

    def send_proactive(self, message: str, user_id: str, session_id: str):
        pairings = self._get_all_pairings()

        if settings.debug:
            print(
                f"\n[DEBUG WhatsApp] send_proactive: checking session '{session_id}' against {len(pairings)} pairings.",
                flush=True,
            )

        logger.info(f"WhatsApp send_proactive triggered for session: {session_id}")
        logger.debug(f"Current pairings: {pairings}")

        # We collect target JIDs first to avoid duplicates if possible
        target_jids = []
        for sender_id_str, paired_val in pairings.items():
            # Match if sender_id is the session_id OR if the paired user matches
            if sender_id_str == session_id or paired_val == user_id:
                # Extra safety: skip multiline keys if they somehow made it in
                if "\n" in str(sender_id_str):
                    continue

                if settings.debug:
                    print(
                        f"\n[DEBUG WhatsApp] Match found! Sender: {sender_id_str}",
                        flush=True,
                    )

                # Parse full JID string (User@Server)
                if "@" in str(sender_id_str):
                    user_part, server_part = str(sender_id_str).split("@", 1)
                    sender_jid = build_jid(user_part, server_part)
                else:
                    # Fallback for old pairings
                    sender_jid = build_jid(str(sender_id_str))

                target_jids.append(sender_jid)

        # Send to all matched targets
        for jid in target_jids:
            logger.info(f"Enqueuing proactive message to JID: {jid.User}@{jid.Server}")
            self.out_queue.put((jid, f"Bot: {message}"))

    async def close(self):
        """Properly close WhatsApp bridge resources."""
        logger.info("Closing WhatsApp bridge...")

        if self.process_loop and self.process_loop.is_running():
            self.process_loop.call_soon_threadsafe(self.process_loop.stop)

        if self.client:
            try:
                self.client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting WhatsApp client: {e}")

        logger.info("WhatsApp bridge closed.")


whatsapp_bridge = WhatsAppBridge()
