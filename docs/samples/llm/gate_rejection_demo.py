#!/usr/bin/env python3
"""反例演示：LLM 产出的载荷试图绕过 Action 直写事件存储 → 内核拒绝 + 留审计。

这是"AI 参与但闸门机械唯一"最强的可验证证据：候选/载荷来自谁不重要，
写路径只有 commit(action_id, ...) 一条，write_raw 必拒（INV-1 / VER-28 item1）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # gate_rejection_demo.py → 模板根
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.store import EventStore, DirectWriteForbidden  # noqa: E402


def main() -> int:
    store = EventStore()

    # 一段"看起来像 LLM 输出"的事件载荷 —— 结构完整、字段齐全。
    llm_payload = {
        "stream_id": "domain:LedgerEntry",
        "event_type": "LedgerEntryCreated@1",
        "payload": {"entry_id": "E-1", "valid_time": "2026-01-01T00:00:00+00:00"},
    }

    refused = False
    try:
        store.write_raw(**llm_payload)               # 试图直写，绕过能力清单
    except DirectWriteForbidden as exc:
        refused = "INV-1" in str(exc)
        print("REFUSED:", str(exc))

    audit_kind = store.audit[-1]["kind"] if store.audit else ""
    print("AUDIT:", audit_kind)

    ok = refused and audit_kind == "structurally-rejected"
    print("GATE-DEMO:", "PASS —— 直写被拒且留审计" if ok else "FAIL —— 闸门异常")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
