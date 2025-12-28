from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware

from integrations.integrations_map import get_integration

app = FastAPI()

origins = [
    "http://localhost:3000",  # React app address
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Ping": "Pong"}


@app.post("/integrations/{integration_name}/authorize")
async def authorize_integration(
    integration_name: str,
    user_id: str = Form(...),
    org_id: str = Form(...),
):
    integration = get_integration(integration_name)
    return await integration.authorize(user_id, org_id)


@app.get("/integrations/{integration_name}/oauth2callback")
async def oauth2callback_integration(
    integration_name: str,
    request: Request,
):
    integration = get_integration(integration_name)
    return await integration.oauth2callback(request)


@app.post("/integrations/{integration_name}/credentials")
async def get_integration_credentials(
    integration_name: str,
    user_id: str = Form(...),
    org_id: str = Form(...),
):
    integration = get_integration(integration_name)
    return await integration.get_credentials(user_id, org_id)


@app.post("/integrations/{integration_name}/load")
async def get_integration_items(
    integration_name: str,
    credentials: str = Form(...),
):
    integration = get_integration(integration_name)
    return await integration.get_items(credentials)
