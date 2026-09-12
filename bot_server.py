import asyncio
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

from flask import Flask, request, Response
import requests
from twilio.twiml.messaging_response import MessagingResponse

from dotenv import load_dotenv
import os
import warnings

warnings.filterwarnings("ignore")
load_dotenv()

app = Flask(__name__)


async def call_mcp_agent(message: str):
    # TODO
    pass


@app.post("/webhook/telegram")
def telegram_webhook():
    # TODO
    pass


@app.post("/webhook/twilio")
def whatsapp_webhook():
    # TODO
    pass


if __name__ == "__main__":
    # TODO
    pass
