MONEY_SIGNALS = ("선입금", "예약금", "계좌", "송금", "입금")
EXTERNAL_LINK_SIGNALS = ("http://", "https://", "카톡", "telegram", "텔레그램")


def score_priority(category: str, description: str, metadata: dict | None = None) -> str:
    text = (description or "").lower()
    meta_price = (metadata or {}).get("price") if metadata else None
    has_money_signal = any(k.lower() in text for k in MONEY_SIGNALS) or bool(meta_price)
    has_external_link = any(k.lower() in text for k in EXTERNAL_LINK_SIGNALS)

    if category == "fraud":
        if has_money_signal or has_external_link:
            return "critical"
        return "high"

    if category == "policy":
        return "high"

    if category == "abuse":
        return "medium"

    if category == "spam":
        return "medium"

    # general 카테고리 기본값
    if has_money_signal or has_external_link:
        return "medium"
    return "low"
