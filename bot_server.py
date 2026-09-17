import asyncio
import os
import warnings
import re
import json

import requests
from dotenv import load_dotenv
from flask import Flask, request, Response
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from twilio.twiml.messaging_response import MessagingResponse
from groq import AsyncGroq

from helpers.clients import create_client
from helpers.mcp_agent_tools import format_history

warnings.filterwarnings("ignore")
load_dotenv()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")

# One conversation history PER client, keyed by identifier — never a single shared list.
conversation_histories: dict[str, list[dict]] = {}

groq_client = AsyncGroq(api_key=GROQ_API_KEY)


def get_history(identifier: str) -> list[dict]:
    return conversation_histories.setdefault(identifier, [])


async def call_mcp_agent(identifier: str, message: str, history: list[dict]) -> str:
    params = StdioServerParameters(command="uv", args=["run", "mcp_server.py"])

    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            print("MCP session initialized...")

            prompt_response = await session.get_prompt(
                name="appointment_classification_prompt",
                arguments={
                    "user_input": message,
                    "history": format_history(history) if history else ""
                }
            )

            prompt_text = prompt_response.messages[0].content.text

            print("Calling the Groq model to select the right tool...")

            completion = await groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "system", "content": prompt_text}]
            )

            raw_content = completion.choices[0].message.content
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)

            if not match:
                return "Sorry, something went wrong understanding your request. Could you rephrase it?"

            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                return "Sorry, something went wrong understanding your request. Could you rephrase it?"

            tool_name = parsed.get("tool_name")

            if not tool_name:
                resource_result = await session.read_resource("info://medical-center")
                center_info = resource_result.contents[0].text
                print("Waiting for the Groq model to answer the general question...")
                completion = await groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": f"Answer the patient's question using only this information about the medical center:\n\n{center_info}"},
                        {"role": "user", "content": message}
                    ]
                )
                return completion.choices[0].message.content

            args = parsed.get("args", {})
            args["identifier"] = identifier

            try:
                result = await session.call_tool(tool_name, arguments=args)
                reply_text = result.content[0].text
                return reply_text
            except Exception as e:
                print(f"Tool call failed: {e}")
                return "Sorry, something went wrong while processing your request. Please try again."


@app.post("/webhook/telegram")
def telegram_webhook():
    data = request.get_json()
    telegram_id = str(data['message']['chat']['id'])
    incoming_message = data['message']['text']

    sender = data['message'].get('from', {})
    first_name = sender.get('first_name', '')
    last_name = sender.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip() or None

    create_client(telegram_id, channel="telegram", full_name=full_name)

    history = get_history(telegram_id)
    history.append({"role": "user", "content": incoming_message})

    reply_text = asyncio.run(call_mcp_agent(identifier=telegram_id, message=incoming_message, history=history))

    history.append({"role": "assistant", "content": reply_text})

    send_telegram_message(telegram_id, reply_text)
    return "OK", 200


@app.post("/webhook/twilio")
def whatsapp_webhook():
    incoming_message = request.form.get('Body', '')
    from_number = request.form.get('From', '').replace('whatsapp:', '')
    full_name = request.form.get('ProfileName') or None

    create_client(from_number, channel="whatsapp", full_name=full_name)

    history = get_history(from_number)
    history.append({"role": "user", "content": incoming_message})

    reply_text = asyncio.run(call_mcp_agent(identifier=from_number, message=incoming_message, history=history))

    history.append({"role": "assistant", "content": reply_text})

    resp = MessagingResponse()
    resp.message(reply_text)
    return Response(str(resp), mimetype="application/xml")


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text})
    print(response.text)


if __name__ == "__main__":
    # TODO
    pass