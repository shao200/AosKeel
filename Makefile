.PHONY: verify test release bootstrap-sandbox
verify:
	python -m src.cli.main verify
test:
	python -m src.cli.main test
# 发布闸门（fail-closed）：三关 + 布线套件 + 骨架一致性全绿才出制品（VER-27 前置）。
release:
	python -m src.cli.main release
# 沙箱序列只到 BOOT-0/1：stage 1 须提供真实外部凭据，模板不合成创制任命（GOV-1）。
# 演示凭据写进 Makefile 即是合成任命（v0.2-F 方案的缺陷，此处明确不采纳）。
bootstrap-sandbox:
	python -m src.cli.main bootstrap --stage 0 --dry-run
	python -m src.cli.main bootstrap --stage 0
