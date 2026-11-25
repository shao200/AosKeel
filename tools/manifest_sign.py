"""tools/manifest_sign.py —— 发布清单真实性层：可选的 Ed25519 分离签名。

诚实边界：默认发布清单只有**完整性**（SHA-256 正典摘要），没有任何签名——
哈希能证明"没被改"，不能证明"是谁发的"。需要真实性时显式提供私钥：

    AOS_SIGNING_KEY=release-ed25519.pem aos release
    python -c "from tools import manifest_sign, json; ..."   # 或用 verify_manifest

签名对象是清单去掉 `signature` 字段后的规范化 JSON（sort_keys + 紧凑分隔符），
因此字段顺序、缩进不影响验签；`authenticity` 字段本身也在签名域内，防止
"把 signed 改回 unsigned"的降级改写。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

UNSIGNED = "unsigned-integrity-only"
SIGNED = "signed-ed25519"


def canonical_bytes(manifest: dict) -> bytes:
    """验签/签名的规范化字节：剔除 signature，其余字段（含 authenticity）全进域。"""
    core = {k: v for k, v in manifest.items() if k != "signature"}
    return json.dumps(core, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _dependency():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)
    except ImportError as e:                      # 可选依赖：不装也不影响默认发布
        raise RuntimeError(
            "SIGN-DEPENDENCY-MISSING: 需要 Ed25519 签名时请安装 "
            "`pip install -e .[sign]`（或自行提供等价实现）") from e
    return serialization, Ed25519PrivateKey, Ed25519PublicKey


def sign_manifest(manifest: dict, key_path: str | Path) -> dict:
    """用 PEM 私钥对清单签名；返回带 authenticity/signature 的新字典。"""
    serialization, Ed25519PrivateKey, _ = _dependency()
    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError(f"KEY-TYPE-INVALID: {key_path} 不是 Ed25519 私钥")
    core = {**{k: v for k, v in manifest.items() if k != "signature"},
            "authenticity": SIGNED}
    sig = key.sign(canonical_bytes(core))
    return {**core,
            "signature": {"alg": "ed25519", "key_id": Path(key_path).stem,
                          "sig_b64": base64.b64encode(sig).decode("ascii")}}


def verify_manifest(manifest: dict, public_key_path: str | Path) -> bool:
    """用 PEM 公钥验签；缺签名 / 算法不符 / 验签失败一律返回 False（不抛）。"""
    serialization, _, Ed25519PublicKey = _dependency()
    sig = manifest.get("signature") or {}
    if sig.get("alg") != "ed25519" or not sig.get("sig_b64"):
        return False
    try:
        pub = serialization.load_pem_public_key(Path(public_key_path).read_bytes())
        if not isinstance(pub, Ed25519PublicKey):
            return False
        pub.verify(base64.b64decode(sig["sig_b64"]), canonical_bytes(manifest))
        return True
    except Exception:                             # 格式/密钥/签名不符均为 False
        return False
