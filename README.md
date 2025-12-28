# OAuth Integrations Backend

A FastAPI-based backend that provides OAuth2 integrations for third-party services such as **Notion**, **HubSpot**, and **Airtable**.

The service handles:
- OAuth authorization flows
- Secure state validation (CSRF protection)
- Token exchange & storage
- Fetching integration-specific metadata
- Redis-backed temporary storage

---

## Tech Stack

- **Python 3.12**
- **FastAPI**
- **Redis**
- **Docker & Docker Compose**
- **Pydantic**
- **httpx / requests**

---

## Project Structure

backend/
├── integrations/
│ ├── airtable.py
│ ├── hubspot.py
│ ├── notion.py
│ ├── base.py
│ └── integrations_map.py
├── redis_client.py
├── settings.py
├── main.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env


---

## Environment Variables

Create a `.env` file in the `backend/` directory.

### Example `.env`

```env
# App
APP_ENV=development

# Redis
REDIS_URL=redis://redis:6379/0

# Notion
NOTION_CLIENT_ID=your_client_id
NOTION_CLIENT_SECRET=your_client_secret
NOTION_AUTH_URL=https://api.notion.com/v1/oauth/authorize?owner=user&response_type=code
NOTION_REDIRECT_URI=http://localhost:8000/integrations/notion/oauth2callback

# HubSpot
HUBSPOT_CLIENT_ID=your_client_id
HUBSPOT_CLIENT_SECRET=your_client_secret
HUBSPOT_AUTH_URL=https://app.hubspot.com/oauth/authorize
HUBSPOT_REDIRECT_URI=http://localhost:8000/integrations/hubspot/oauth2callback

# Airtable
AIRTABLE_CLIENT_ID=your_client_id
AIRTABLE_CLIENT_SECRET=your_client_secret
AIRTABLE_AUTH_URL=https://airtable.com/oauth2/v1/authorize
AIRTABLE_REDIRECT_URI=http://localhost:8000/integrations/airtable/oauth2callback
```

---

## Available Integrations

| Service   | OAuth      | Fetch Items |
|-----------|------------|-------------|
| Notion    | Yes        | Yes         |
| HubSpot   | Yes        | Yes         |
| Airtable  | Yes (PKCE) | Yes         |


---


## API Endpoints

- POST /integrations/{provider}/authorize
- GET /integrations/{provider}/oauth2callback
- POST /integrations/{provider}/credentials
- POST /integrations/{provider}/load

---

## OAuth Flow Overview

1. Client calls `/authorize`
2. User is redirected to provider OAuth page
3. Provider redirects back to `/oauth2callback`
4. State is validated (CSRF protection)
5. Authorization code is exchanged for tokens
6. Credentials are stored temporarily in Redis
7. Client retrieves credentials and loads items

---

## Design Notes

- Redis is used only for temporary storage
- OAuth state validation prevents CSRF attacks
- Integrations implement a shared `OAuthIntegration` base class
- Docker Compose is intended for local development
- Use managed Redis (e.g. Upstash) in production

---
