import os
import json
import logging
import asyncio
import threading
import queue
from typing import Optional, Dict, Any
from neonize.aioze.client import NewAClient
from neonize.aioze.events import MessageEv, ConnectedEv, QREv
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

        # If it's the login command, run it in a separate thread for blocking behavior
        if is_login_cmd:
            from neonize.client import NewClient
            from neonize.events import QREv as SQREv, ConnectedEv as SConnectedEv

            qr_queue = queue.Queue()
            connected_event = threading.Event()

            def _neonize_thread_runner():
                logger.info("Starting WhatsApp login (Sync Mode in Thread)...")
                # Temporarily enable debug for neonize in this thread to see all output
                logging.getLogger("neonize").setLevel(logging.DEBUG)
                s_client = NewClient(self.db_file)

                @s_client.event(SQREv)
                def on_qr_sync(_: NewClient, qr: SQREv):
                    logger.debug("QR Event received in thread.")
                    try:
                        qr_str = qr if isinstance(qr, str) else qr.Code
                    except AttributeError:
                        qr_str = str(qr)
                    qr_queue.put(qr_str)

                @s_client.event(SConnectedEv)
                def on_connected_sync(_: NewClient, __: SConnectedEv):
                    logger.info("⚡ WhatsApp Connected in thread!")
                    connected_event.set()
                
                s_client.connect() # This is a blocking call until disconnected or stopped
                logger.info("Neonize thread client disconnected.")

            # Start Neonize in a new thread
            thread = threading.Thread(target=_neonize_thread_runner, daemon=True)
            thread.start()

            # Main loop to check for QR and connection status
            print("\n" + "="*40)
            print("   Waiting for WhatsApp QR Code...")
            print("="*40 + "\n")
            try:
                qr_code_data = qr_queue.get(timeout=90) # Wait up to 90 seconds for QR
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
                connected_event.wait(timeout=300) # Wait up to 5 minutes for connection
                if connected_event.is_set():
                    print("\n✅ Successfully linked! You can now exit (Ctrl+C) and use 'angel-claw chat'.")
                else:
                    print("\n❌ WhatsApp linking timed out or failed. Check your internet connection or try again.")
            except queue.Empty:
                print("\n❌ Timed out waiting for QR code from WhatsApp. Check your internet connection or try again.")
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nLogin process interrupted.")
            finally:
                # Restore original neonize logging level
                logging.getLogger("neonize").setLevel(logging.WARNING)
                # Ensure the thread client is disconnected if connect() was blocking
                # No direct way to stop from outside without s_client.stop() inside the thread
                pass 
            return

        # Async Mode for background operation
        logger.info(f"Starting WhatsApp bridge (Async Mode)...")
        self.client = NewAClient(self.db_file)

        @self.client.event(QREv)
        async def on_qr(_: NewAClient, qr: QREv):
            logger.debug("QR Event received (Async Mode, not expected to show QR here).")

        @self.client.event(ConnectedEv)
        async def on_connected(_: NewAClient, __: ConnectedEv):
            logger.info("⚡ WhatsApp Connected (Async Mode)!")

        @self.client.event(MessageEv)
        async def on_message(client: NewAClient, message: MessageEv):
            # Extract text
            text = message.Message.conversation or message.Message.extendedTextMessage.text
            if not text:
                return
            
            sender_jid = message.Info.MessageSource.Chat
            sender_id = str(sender_jid).split("@")[0] # Clean ID for pairings

            # Handle Commands
            if text.startswith("/"):
                await self._handle_command(client, sender_jid, sender_id, text)
            else:
                await self._handle_message(client, sender_jid, sender_id, text)

        # Connect
        logger.debug("Attempting to connect to WhatsApp in Async Mode...")
        await self.client.connect()
        logger.debug("client.connect() call finished for Async Mode.")
        
        # Keep process alive for async operations
        try:
            while True:
                await asyncio.sleep(60) # Keep async bridge alive
        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Async bridge loop interrupted.")
            pass


    async def _handle_command(self, client: NewAClient, sender_jid: Any, sender_id: str, text: str):
        parts = text.split()
        cmd = parts[0].lower()
        
        if cmd == "/pair" and len(parts) > 1:
            session_id = parts[1]
            self.pairings[sender_id] = session_id
            self._save_pairings()
            await client.send_message(sender_jid, f"✅ Paired with session: `{session_id}`")
        elif cmd == "/start":
            await client.send_message(sender_jid, "👋 Welcome to Angel Claw!\nUse `/pair <session-id>` to connect your session.\nScan the QR code in the server terminal to link.")
        else:
            await client.send_message(sender_jid, f"Unknown command: {cmd}")

    async def _handle_message(self, client: NewAClient, sender_jid: Any, sender_id: str, text: str):
        if sender_id not in self.pairings:
            await client.send_message(sender_jid, "⚠️ Chat not paired. Use `/pair <session-id>` to start.")
            return

        session_id = self.pairings[sender_id]
        try:
            agent = Agent(session_id)
            response = await agent.chat(text)
            await client.send_message(sender_jid, response)
        except Exception as e:
            logger.error(f"Error in WhatsApp chat: {e}")
            await client.send_message(sender_id, f"⚠️ Error: {e}")

    async def send_proactive(self, message: str, user_id: str, session_id: str):
        if not self.client or not (await self.client.is_connected): # Check is_connected property
            return

        # Route proactive reminders to paired WhatsApp chats
        for sender_id, paired_sid in self.pairings.items():
            if paired_sid == session_id:
                # Reconstruct JID
                sender_jid = f"{sender_id}@s.whatsapp.net"
                try:
                    await self.client.send_message(sender_jid, message)
                except Exception as e:
                    logger.error(f"Failed to send proactive WhatsApp message: {e}")

    async def close(self):
        # Explicitly stop the client if it's running in async mode
        if self.client and (await self.client.is_connected):
            await self.client.stop()
        pass

whatsapp_bridge = WhatsAppBridge()
