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


def get_or_create_client(identifier: str, channel: str) -> int:
    """
    Finds the client matching this identifier, or creates a new (email-less)
    record if none exists yet. Returns the client's internal id.

    channel: 'telegram' or 'whatsapp' — determines which column the identifier is stored in.
    """
    client = get_client_by_identifier(identifier)
    if client is not None:
        return client["id"]

    connection = get_connection()
    cursor = connection.cursor()

    if channel == "telegram":
        cursor.execute(
            "INSERT INTO clients (telegram_id, channel) VALUES (%s, %s)",
            (identifier, channel)
        )
    else:
        cursor.execute(
            "INSERT INTO clients (whatsapp_number, channel) VALUES (%s, %s)",
            (identifier, channel)
        )

    connection.commit()
    new_id = cursor.lastrowid

    cursor.close()
    connection.close()
    return new_id


def update_client_email(identifier: str, email: str) -> bool:
    """
    Saves the client's email address. Returns True if a matching client
    was found and updated, False otherwise.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE clients SET email = %s WHERE telegram_id = %s OR whatsapp_number = %s",
        (email, identifier, identifier)
    )
    connection.commit()

    updated = cursor.rowcount > 0

    cursor.close()
    connection.close()
    return updated