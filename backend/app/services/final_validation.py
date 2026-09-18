from __future__ import annotations

from .domain import CheckOutcome


def final_status(checks: list[CheckOutcome]) -> tuple[str, str, list[str], list[str], list[str]]:
    passed = [check.message for check in checks if check.state == "PASS"]
    failed = [check.message for check in checks if check.state == "FAIL"]
    verify = [check.message for check in checks if check.state == "VERIFY"]
    if failed:
        status = "FAIL"
    elif verify:
        status = "VERIFY"
    else:
        status = "PASS"
    confidence = "HIGH" if status == "PASS" else ("MEDIUM" if not verify else "LOW")
    return status, confidence, passed, failed, verify


def ranking_score(
    status: str,
    profit: float | None,
    roi: float | None,
    demand: int | None,
    competition: int | None,
    confidence: str,
) -> float:
    if status != "PASS":
        return 0.0
    confidence_weight = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.0}.get(confidence, 0.0)
    score = (
        (profit or 0) * 4
        + (roi or 0) * 1.5
        + min(demand or 0, 1000) * 0.1
        + max(0, 30 - (competition or 30)) * 2
    )
    return round(score * confidence_weight, 2)
