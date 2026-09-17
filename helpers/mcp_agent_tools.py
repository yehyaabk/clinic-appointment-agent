from typing import List


def format_history(history: List[dict], num_messages: int = 6) -> str:
    """
    Formats the last `num_messages` turns of conversation history into a
    readable string, suitable for injecting into a prompt.
    """
    recent_history = history[-num_messages:-1]

    lines = [f"- {entry['role']}: {entry['content']}" for entry in recent_history]

    return "\n".join(lines)
    