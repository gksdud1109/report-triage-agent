import secrets


def new_report_id() -> str:
    return f"rpt_{secrets.token_hex(6)}"


def new_queue_item_id() -> str:
    return f"qi_{secrets.token_hex(6)}"


def new_classification_id() -> str:
    return f"cls_{secrets.token_hex(6)}"
