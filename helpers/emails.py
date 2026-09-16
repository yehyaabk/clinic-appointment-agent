import re
from db.config import get_connection

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    """Basic format check for an email address."""
    return bool(EMAIL_PATTERN.match(email.strip()))


def set_client_email(identifier: str, email: str) -> bool:
    """
    Saves (creates or updates) a client's email address.
    Returns True if a matching client was found and updated, False otherwise.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE clients SET email = %s WHERE whatsapp_number = %s OR telegram_id = %s",
        (email, identifier, identifier)
    )
    connection.commit()

    updated = cursor.rowcount > 0

    cursor.close()
    connection.close()
    return updated