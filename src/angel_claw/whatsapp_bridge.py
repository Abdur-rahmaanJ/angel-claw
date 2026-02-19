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
from neonize.utils.jid import build_jid
from .config import settings
from .agent import Agent
from .cron import cron_manager

# Set neonize logging to warning to avoid too much noise
logging.getLogger("neonize").setLevel(logging.CRITICAL)
logging.getLogger("whatsmeow").setLevel(logging.CRITICAL)
logging.getLogger("Whatsmeow").setLevel(logging.CRITICAL)
logger = logging.getLogger("angel-claw-whatsapp")

class WhatsAppBridge:
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or os.path.join(settings.memory_persist_dir, "whatsapp")
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)
            
        self.pairings_file = os.path.join(self.persist_dir, "pairings.json")
        self.db_file = os.path.join(self.persist_dir, "session.db")
        self.pairings = self._load_pairings()
        self.enabled = settings.whatsapp_enabled
        self.client = None
        self.main_thread = None
        self.sender_thread = None
        self.out_queue = queue.Queue()
        self.process_loop = None
        
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
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading WhatsApp pairings: {e}")
        return {}

    def _save_pairings(self):
        try:
            with open(self.pairings_file, "w") as f:
                json.dump(self.pairings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving WhatsApp pairings: {e}")

    async def run(self):
        if not self.enabled:
            return

        has_session = os.path.exists(self.db_file)
        import sys
        is_login_cmd = "login-whatsapp" in sys.argv

        if not has_session and not is_login_cmd:
            logger.warning("WhatsApp session not found. Please run 'angel-claw login-whatsapp' to link your account.")
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
                    logger.warning("QR Code requested but not in login mode. Session may have expired.")

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
                        print("\n" + "="*40 + "\n   SCAN THIS QR CODE WITH WHATSAPP\n" + "="*40 + "\n")
                        qr_gen.print_ascii()
                        print("\nWaiting for scan...\n")
                    except queue.Empty: pass
                    if connected_event.is_set():
                        print("\n✅ Successfully linked! You can now exit (Ctrl+C).")
                        while True: time.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError): pass
            return

        await asyncio.sleep(0.1) 

    def _sender_worker(self):
        """Worker thread that drains the outgoing message queue."""
        while True:
            try:
                jid, message = self.out_queue.get(timeout=1)
                
                # Wait for stable connection
                while not self.client or not getattr(self.client, 'is_logged_in', False):
                    time.sleep(2)

                success = False
                for attempt in range(3):
                    try:
                        # Small delay to ensure Go bridge is ready for usync
                        if attempt > 0: time.sleep(3)
                        
                        self.client.send_message(jid, message)
                        success = True
                        break
                    except Exception as e:
                        logger.warning(f"WhatsApp send attempt {attempt+1} failed: {e}")
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
            # Get the JID and extract the clean user ID (phone number)
            chat_jid = message.Info.MessageSource.Chat
            sender_id = chat_jid.User.split("@")[0]
            
            # Extract text
            text = ""
            if message.Message.conversation:
                text = message.Message.conversation
            elif message.Message.extendedTextMessage and message.Message.extendedTextMessage.text:
                text = message.Message.extendedTextMessage.text
            
            if not text: return
            
            # Use 'Bot: ' prefix check instead of IsFromMe
            # This allows responding to 'Message to Yourself' where IsFromMe is always True
            if text.startswith("Bot: "):
                return

            # Only allow private chats (users and hidden users)
            # This ignores groups (@g.us), status updates (@broadcast), and newsletters (@newsletter)
            if chat_jid.Server not in ("s.whatsapp.net", "lid"):
                return

            # Explicitly ignore status updates if they somehow bypass the server check
            if sender_id == "status":
                return

            logger.info(f"Incoming WhatsApp from {sender_id}: {text}")
            
            # Always reply to the Chat JID
            threading.Thread(
                target=lambda: asyncio.run(self._process_agent_response(client, chat_jid, sender_id, text)),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {e}")

    async def _process_agent_response(self, client: NewClient, sender_jid: Any, sender_id: str, text: str):
        if text.startswith("/"):
            await self._handle_command(client, sender_jid, sender_id, text)
        else:
            await self._handle_chat(client, sender_jid, sender_id, text)

    async def _handle_command(self, client: NewClient, sender_jid: Any, sender_id: str, text: str):
        parts = text.split()
        cmd = parts[0].lower()
        if cmd == "/pair" and len(parts) > 1:
            self.pairings[sender_id] = parts[1]
            self._save_pairings()
            self.out_queue.put((sender_jid, f"Bot: ✅ Paired with session: `{parts[1]}`"))
        elif cmd == "/start":
            self.out_queue.put((sender_jid, "Bot: 👋 Welcome to Angel Claw!\nUse `/pair <session-id>` to connect your session."))

    async def _handle_chat(self, client: NewClient, sender_jid: Any, sender_id: str, text: str):
        if sender_id not in self.pairings:
            logger.warning(f"Unpaired message from {sender_id}")
            self.out_queue.put((sender_jid, "Bot: ⚠️ Chat not paired. Use `/pair <session-id>` to start."))
            return

        session_id = self.pairings[sender_id]
        logger.info(f"Processing message for session {session_id} from {sender_id}")
        try:
            agent = Agent(session_id)
            response = await agent.chat(text)
            logger.info(f"Sending response to {sender_id}")
            self.out_queue.put((sender_jid, f"Bot: {response}"))
        except Exception as e:
            logger.error(f"Error in WhatsApp chat: {e}", exc_info=True)
            self.out_queue.put((sender_jid, f"Bot: ⚠️ Error processing your request."))

    def send_proactive(self, message: str, user_id: str, session_id: str):
        logger.info(f"WhatsApp send_proactive triggered for session: {session_id}")
        logger.debug(f"Current pairings: {self.pairings}")
        
        for sender_id, paired_sid in self.pairings.items():
            if paired_sid == session_id:
                logger.info(f"Match found! Sending reminder to WhatsApp ID: {sender_id}")
                sender_jid = build_jid(f"{sender_id}")
                self.out_queue.put((sender_jid, f"Bot: {message}"))

    async def close(self): pass

whatsapp_bridge = WhatsAppBridge()
