#!/usr/bin/env python3
"""示例 LLM 提取适配器 —— 演示 aos extract --extractor 契约，不是内核依赖。

契约（见 tools/semantic_extract._custom_extract）：
  输入  : argv[1] = 素材文件路径
  输出  : stdout 一个 YAML {objects: [{object_type, identity, properties{name: type}}]}
  失败  : 非零退出码 → EXTRACTOR-FAILED（fail-closed）

本示例默认离线运行（内置确定性 stub），证明"接适配器"零 LLM 依赖。
接真实 LLM 只改 generate_candidates()：调用你自己的服务/SDK 按同 schema
产出 objects[] 即可 —— 闸门、草案、晋升逻辑完全不变。

生产接法示意（本示例不执行，避免任何网络/密钥依赖）：
    from openai import OpenAI
    resp = OpenAI().responses.create(
        model="gpt-4o",
        input=f"从需求文本提取本体候选，仅输出 YAML objects[]：\n{text}")
    return yaml.safe_load(resp.output_text)
"""
import sys
import yaml


def generate_candidates(text: str) -> dict:
    """替换为真实 LLM 调用；此处为可离线复现的确定性占位候选。

    故意选模板不存在的 LedgerEntry，避免与内置 Contract 声明撞名，
    使本样例的 promote 步骤能真实跑通（晋升不覆盖已有正典声明）。
    """
    return {"objects": [{
        "object_type": "LedgerEntry",
        "identity": "entry_id",
        "properties": {"amount": "number", "vendor_ref": "string", "status": "string"},
    }]}


def main() -> int:
    if len(sys.argv) < 2:
        print("EXTRACTOR-USAGE: llm_extractor.py <material-file>", file=sys.stderr)
        return 2
    text = open(sys.argv[1], encoding="utf-8").read()
    yaml.safe_dump(generate_candidates(text), sys.stdout,
                   allow_unicode=True, sort_keys=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
