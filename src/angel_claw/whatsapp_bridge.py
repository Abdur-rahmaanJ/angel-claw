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
from neonize.utils import log as nlog
from .config import settings
from .agent import Agent
from .cron import cron_manager

# Set neonize logging to warning to avoid too much noise for normal ops
logging.getLogger("neonize").setLevel(logging.WARNING)
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
        self.thread = None
        
        # Register for proactive reminders
        cron_manager.register_proactive_handler(self.send_proactive)

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
        """
        Main entry point. 
        For 'angel-claw chat', this is called as an async task but we offload 
        the blocking Neonize client to a thread immediately.
        """
        if not self.enabled:
            logger.info("WhatsApp bridge is disabled.")
            return

        # Check if we have an existing session
        has_session = os.path.exists(self.db_file)
        
        import sys
        is_login_cmd = "login-whatsapp" in sys.argv

        if not has_session and not is_login_cmd:
            logger.warning("WhatsApp session not found. Please run 'angel-claw login-whatsapp' to link your account.")
            return

        # We use a Queue to communicate QR codes back to the main thread if needed
        qr_queue = queue.Queue()
        connected_event = threading.Event()

        def _sync_client_runner():
            logger.info(f"Starting WhatsApp bridge (Threaded Sync Mode)...")
            # If logging in, enable debug
            if is_login_cmd:
                logging.getLogger("neonize").setLevel(logging.DEBUG)
            
            self.client = NewClient(self.db_file)

            @self.client.event(QREv)
            def on_qr(_: NewClient, qr: QREv):
                # Put QR in queue for main thread to display
                try:
                    qr_str = qr if isinstance(qr, str) else qr.Code
                except AttributeError:
                    qr_str = str(qr)
                qr_queue.put(qr_str)

            @self.client.event(ConnectedEv)
            def on_connected(_: NewClient, __: ConnectedEv):
                logger.info("⚡ WhatsApp Connected!")
                connected_event.set()

            @self.client.event(MessageEv)
            def on_message(client: NewClient, message: MessageEv):
                # Run message handling logic
                # Since this is in a thread, we can call a helper
                self._handle_message_sync(client, message)

            # connect() is blocking in the synchronous client
            try:
                self.client.connect()
            except Exception as e:
                logger.error(f"WhatsApp client disconnected: {e}")

        # Start the thread
        self.thread = threading.Thread(target=_sync_client_runner, daemon=True)
        self.thread.start()

        # If this is the login command, we block and wait for QR/Connection
        if is_login_cmd:
            print("\n" + "="*40)
            print("   Waiting for WhatsApp QR Code...")
            print("="*40 + "\n")
            try:
                # Wait for QR
                while not connected_event.is_set():
                    try:
                        qr_code_data = qr_queue.get(timeout=1)
                        import qrcode
                        qr_gen = qrcode.QRCode()
                        qr_gen.add_data(qr_code_data)
                        print("\n" + "="*40)
                        print("   SCAN THIS QR CODE WITH WHATSAPP")
                        print("="*40 + "\n")
                        qr_gen.print_ascii()
                        print("\n" + "="*40)
                        print("   Waiting for scan...")
                        print("="*40 + "\n")
                    except queue.Empty:
                        pass
                    
                    # Check connection
                    if connected_event.is_set():
                        print("\n✅ Successfully linked! You can now exit (Ctrl+C) and use 'angel-claw chat'.")
                        # Keep alive to show logs until user exits
                        while True:
                            time.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nLogin process interrupted.")
            return

        # If NOT login command (background mode), we just return immediately 
        # and let the thread run in the background.
        logger.info("WhatsApp bridge running in background thread.")
        # We need a small sleep to ensure thread starts before main loop continues heavily
        import asyncio
        await asyncio.sleep(0.5) 

    def _handle_message_sync(self, client: NewClient, message: MessageEv):
        """Handle messages in the sync thread."""
        try:
            text = message.Message.conversation or message.Message.extendedTextMessage.text
            if not text:
                return
            
            sender_jid = message.Info.MessageSource.Chat
            
            # Ignore group chats (JIDs ending in @g.us)
            if str(sender_jid).endswith("@g.us"):
                logger.debug(f"Ignoring group chat message from {sender_jid}")
                return

            sender_id = str(sender_jid).split("@")[0]

            # We need to bridge back to Async Agent. 
            # Since we are in a sync thread, we run a mini-asyncio runner for the agent chat
            # OR we can simply schedule it if we had access to the main loop.
            # For robustness, we'll run a one-off async call here.
            
            asyncio.run(self._process_agent_response(client, sender_jid, sender_id, text))
            
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {e}")

    async def _process_agent_response(self, client: NewClient, sender_jid: Any, sender_id: str, text: str):
        # Double check it's not a group (JID ending in @g.us)
        if str(sender_jid).endswith("@g.us"):
            return

        # Determine if it's a command or chat
        if text.startswith("/"):
            await self._handle_command(client, sender_jid, sender_id, text)
        else:
            await self._handle_chat(client, sender_jid, sender_id, text)

    async def _handle_command(self, client: NewClient, sender_jid: Any, sender_id: str, text: str):
        parts = text.split()
        cmd = parts[0].lower()
        response = ""
        
        if cmd == "/pair" and len(parts) > 1:
            session_id = parts[1]
            self.pairings[sender_id] = session_id
            self._save_pairings()
            response = f"✅ Paired with session: `{session_id}`"
        elif cmd == "/start":
            response = "👋 Welcome to Angel Claw!\nUse `/pair <session-id>` to connect your session."
        else:
            response = f"Unknown command: {cmd}"
            
        client.send_message(sender_jid, response)

    async def _handle_chat(self, client: NewClient, sender_jid: Any, sender_id: str, text: str):
        if sender_id not in self.pairings:
            client.send_message(sender_jid, "⚠️ Chat not paired. Use `/pair <session-id>` to start.")
            return

        session_id = self.pairings[sender_id]
        try:
            agent = Agent(session_id)
            response = await agent.chat(text)
            client.send_message(sender_jid, f"Bot: {response}")
        except Exception as e:
            logger.error(f"Error in WhatsApp chat: {e}")
            client.send_message(sender_jid, f"⚠️ Error: {e}")

    def send_proactive(self, message: str, user_id: str, session_id: str):
        if not self.client or not self.client.is_logged_in():
            return

        for sender_id, paired_sid in self.pairings.items():
            if paired_sid == session_id:
                sender_jid = f"{sender_id}@s.whatsapp.net"
                try:
                    self.client.send_message(sender_jid, f"Bot: {message}")
                except Exception as e:
                    logger.error(f"Failed to send proactive WhatsApp message: {e}")

    async def close(self):
        # Sync client doesn't have a clean stop from another thread easily
        # but daemon thread will die with process
        pass

whatsapp_bridge = WhatsAppBridge()
