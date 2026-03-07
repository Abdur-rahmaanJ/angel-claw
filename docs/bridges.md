# Multi-Channel Bridges

Angel Claw is designed to be accessible wherever you are. This document explains how to configure and use our native messaging bridges.

---

## 1. Telegram Bridge

The Telegram bridge allows you to interact with your agent via a private bot.

### Configuration
1.  Create a bot on Telegram via [@BotFather](https://t.me/botfather).
2.  Obtain your **API Token**.
3.  Add it to your `.env` file: `TELEGRAM_TOKEN=your-token`.

### Secure Pairing
To link your Telegram account to your specific **UserRuntime**:
1.  Log in to the Angel Claw Web Dashboard.
2.  Go to the **Connections** section and generate a **Pairing Token**.
3.  On Telegram, send the command `/pair <token>` to your bot.
4.  Your account is now linked. All future messages will be routed to your private agent instance.

---

## 2. WhatsApp Bridge

The WhatsApp bridge utilizes the `neonize` library to interact with your agent via WhatsApp.

### Initial Login
WhatsApp requires an interactive QR code scan to authenticate:
1.  Run the CLI command: `angel-claw login-whatsapp`.
2.  A QR code will be generated in your terminal (or as a separate file).
3.  Scan the code using your WhatsApp mobile app (**Linked Devices** -> **Link a Device**).
4.  The session will be saved locally.

### Secure Pairing
Once logged in, follow the same pairing process as Telegram:
1.  Generate a **Pairing Token** on the Web Dashboard.
2.  Send the message `/pair <token>` to your bot on WhatsApp.

---

## 3. Proactive Notifications

Both bridges support **Proactive Triggers**. If you have a scheduled task (e.g., a reminder), the result will be sent to you automatically on all paired devices.

- **Note**: Ensure the Bridge Worker (`angel-claw bridges`) is running to receive proactive notifications.
