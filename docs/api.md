# Developer API Reference

Angel Claw provides a RESTful API for integrating your agent into external applications and services.

---

## 1. Authentication

All API requests must be authenticated using a **Bearer Token**.

### Obtaining a Token
1.  Log in to the Angel Claw Web Dashboard.
2.  Navigate to **Settings** -> **API Keys**.
3.  Click **Generate New Key**.
4.  Copy the key (it will only be shown once).

### Using the Token
Include the token in your `Authorization` header:
```http
Authorization: Bearer ac_v1_your_key_here
```

---

## 2. API Endpoints

### Chat
Send a message to the agent and receive a response.

- **URL**: `/chat`
- **Method**: `POST`
- **Payload**:
  ```json
  {
    "message": "Hello, what is my schedule today?",
    "session_id": "optional-custom-session-id"
  }
  ```
- **Response**:
  ```json
  {
    "response": "Hello! You have a meeting at 2 PM.",
    "session_id": "optional-custom-session-id"
  }
  ```

### Webhook Trigger
Trigger a proactive response from the agent via an external webhook.

- **URL**: `/webhook`
- **Method**: `POST`
- **Header**: `X-Webhook-Key` (Optional, configured in `.env`)
- **Payload**:
  ```json
  {
    "message": "Deployment failed on production",
    "user_id": "alice",
    "session_id": "monitoring-alerts"
  }
  ```
- **Result**: The agent will process the message and proactively notify the user via Telegram/WhatsApp.

---

## 3. Health Check

Verify the status of the Gateway server.

- **URL**: `/health`
- **Method**: `GET`
- **Response**: `{"status": "healthy"}`
