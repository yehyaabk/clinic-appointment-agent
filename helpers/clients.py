from db.config import get_connection


def get_client_by_identifier(identifier: str) -> dict | None:
    """
    Looks up a client by their Telegram chat_id or WhatsApp phone number.
    Returns the client row as a dict, or None if not found.
    """
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM clients WHERE telegram_id = %s OR whatsapp_number = %s",
        (identifier, identifier)
    )
    client = cursor.fetchone()

    cursor.close()
    connection.close()
    return client


def create_client(identifier: str, channel: str, full_name: str = None) -> None:
    """
    Ensures a client row exists for this identifier, creating one if needed.
    Safe to call on every incoming message — if the client already exists,
    nothing changes.
 
    channel: 'telegram' or 'whatsapp' — determines which column the identifier is stored in.
    full_name: the client's display name from Telegram/WhatsApp, if available.
    """
    connection = get_connection()
    cursor = connection.cursor()
 
    if channel == "telegram":
        cursor.execute(
            """INSERT INTO clients (telegram_id, channel, full_name)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE id = id""",
            (identifier, channel, full_name)
        )
    else:
        cursor.execute(
            """INSERT INTO clients (whatsapp_number, channel, full_name)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE id = id""",
            (identifier, channel, full_name)
        )
    connection.commit()
 
    cursor.close()
    connection.close()
