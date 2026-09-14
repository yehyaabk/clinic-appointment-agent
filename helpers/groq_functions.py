import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are a medical assistant. You will receive a patient's symptom description
and a doctor's description. Your role is to determine whether this doctor is
a relevant match for the patient's symptoms.

Only return the single word True or False, nothing else.

Example 1:
Doctor description: I am a Dermatologist
Patient: I have red spots on my skin
Return: True

Example 2:
Doctor description: I am a Dermatologist
Patient: I have a headache
Return: False
"""


def extract_boolean(raw_reply: str) -> bool | None:
    has_true = re.search(r"\btrue\b", raw_reply, re.IGNORECASE) is not None
    has_false = re.search(r"\bfalse\b", raw_reply, re.IGNORECASE) is not None

    if has_true and not has_false:
        return True
    elif has_false and not has_true:
        return False
    else:
        return None 


def match_doctors_to_symptoms(symptom_description: str, doctors: list[str]) -> list[int]:
    matching_indices = []

    for index, doctor_description in enumerate(doctors):
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Doctor description: {doctor_description}\nPatient: {symptom_description}"}
            ]
        )

        raw_reply = completion.choices[0].message.content
        is_match = extract_boolean(raw_reply)

        if is_match is None:
            print(f"Ambiguous LLM reply for doctor #{index}: '{raw_reply}' — treating as no match")
            is_match = False

        if is_match:
            matching_indices.append(index)

    return matching_indices