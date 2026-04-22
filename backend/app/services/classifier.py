from app.schemas.classification import ClassificationResult

FRAUD_KEYWORDS = ("선입금", "예약금", "외부 메신저", "카톡으로", "직거래 안됨", "계좌이체")
SPAM_KEYWORDS = ("광고", "홍보", "이벤트 당첨", "지금 클릭", "도배")
ABUSE_KEYWORDS = ("욕설", "씨발", "개새끼", "죽여", "협박", "혐오")
POLICY_KEYWORDS = ("불법", "금지 품목", "의약품", "주류", "담배")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def classify_report(
    reason_code: str,
    description: str,
    metadata: dict | None = None,
) -> ClassificationResult:
    """규칙 기반 1차 분류기.

    인터페이스(reason_code + description + metadata -> ClassificationResult)를
    좁게 유지해서 추후 호출부 수정 없이 LLM 기반 분류기로 교체할 수 있게 한다.
    """
    text = description or ""
    meta_blob = " ".join(str(v) for v in (metadata or {}).values())
    haystack = f"{text} {meta_blob}"

    if reason_code == "fraud_suspected" or _contains_any(haystack, FRAUD_KEYWORDS):
        return ClassificationResult(
            category="fraud",
            confidence=0.88 if reason_code == "fraud_suspected" else 0.7,
            reasoning_summary="사기 의심 신호(선입금/외부 메신저 등)가 신고 본문에서 감지됨",
        )

    if reason_code == "abusive_language" or _contains_any(haystack, ABUSE_KEYWORDS):
        return ClassificationResult(
            category="abuse",
            confidence=0.8,
            reasoning_summary="욕설/협박/혐오 표현 키워드가 감지됨",
        )

    if reason_code == "spam" or _contains_any(haystack, SPAM_KEYWORDS):
        return ClassificationResult(
            category="spam",
            confidence=0.75,
            reasoning_summary="광고/도배 패턴이 감지됨",
        )

    if reason_code == "policy_violation" or _contains_any(haystack, POLICY_KEYWORDS):
        return ClassificationResult(
            category="policy",
            confidence=0.7,
            reasoning_summary="정책 위반 키워드(금지 품목 등)가 감지됨",
        )

    if reason_code == "scam_link":
        return ClassificationResult(
            category="fraud",
            confidence=0.72,
            reasoning_summary="외부 스캠 링크 신고로 사기 카테고리로 분류",
        )

    # 특정 카테고리 시그널이 약한 경우 general로 폴백.
    return ClassificationResult(
        category="general",
        confidence=0.4,
        reasoning_summary="특정 카테고리 신호가 약해 general로 분류",
    )
