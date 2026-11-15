"""src/interpreter/audit.py —— 解释器审计（KS-3.3 / VER-11）。
版本身份进审计记录：解释器版本必须可审计 —— 会话审计必须包含
（解释器版本，快照哈希，评估结果）。"""
from __future__ import annotations
import hashlib, json
INTERPRETER_VERSION = "bool-profile@1.0.0 + map-profile@1.0.0"
def record_evaluation(expr: str, env: dict, result: bool) -> dict:
    """单次评估的审计三元组。"""
    snapshot_hash = hashlib.sha256(
        json.dumps(env, sort_keys=True, default=str).encode()).hexdigest()
    return {"interpreter_version": INTERPRETER_VERSION,
            "snapshot_hash": snapshot_hash, "result": bool(result)}
