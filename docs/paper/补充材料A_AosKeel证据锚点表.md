# 电子版补充材料 A：AosKeel 证据锚点表

配套论文：《边界可见性与担保主体的制度性依赖——算法治理的技术哲学分析》（最终投稿版 v4.2）

证据来自公开仓库 https://github.com/shao200/AosKeel ，无需登录。核验日期2026-11-21；commit为 ade0619fda04b3f2d65b3a88c3e47b8623849afb；冻结正典v2.2.0，登记号AOS-ART-004，SHA-256为 fff3d7e712317ca4e3d199b9bc6974f87470ff19f907a7faf2fc974ae993597e 。仓库可能演进，读者应以哈希对应的历史版本核对本文断言。本表功能是使技术断言可被逐条核查，而非提供产品评测。

| 编号 | 支撑的论断 | 文件路径与行号 | 原文摘录（节选） |
|---|---|---|---|
| E1 | GOV-1算术/正当性两级契约 | docs/aos-spec.md:373 | "两级社会契约：算术（平台强制校验）；正当性（社会担保，非平台保证）" |
| E2 | BOOT-1外部凭证、不合成正当性 | src/cli/main.py:324-332 | 强制appointment-ref；"此处仅记录引用，不制造正当性" |
| E3 | BOOT-2/3模板层不实装、返回拒绝 | src/cli/main.py:336-338 | "模板层未实装，此为诚实边界，不模拟治理" |
| E4 | 观测层物理逻辑分离、闭包禁读 | docs/aos-spec.md:109-117 | "本体事件日志与会话事件流MUST物理与逻辑分离" |
| E5 | 投影源级排除会话流 | src/kernel/projection.py:28-38 | "会话流禁止进入投影源"；rebuild中跳过session |
| E6 | 不提供合规证明 | README.md:282,300 | "No proof of compliance... never marks them passed for you" |
| E8 | 事件存储为内存结构 | README.md:285; src/kernel/store.py:40 | "EventStore is a dict: no persistence across process restarts" |
| E9 | FileStore为单进程参考实现 | README.md:285; src/kernel/filestore.py:6-8 | "单写进程模型——多进程并发需实例侧自行加锁" |
| E10 | 完整能力面规则为实例侧义务 | README.md:290; src/kernel/pipeline.py:65-72 | "not an automatic context gate in the template" |
| E11 | 链式审计标识为导出时派生 | tools/audit_export.py:7-24 | "只读派生件：不改任何源账本" |
| E12 | 结构指纹刻意弱设计 | README.md:288; tools/fingerprint.py:11-24 | "checks clause counts and anchors" |
| E13 | 哈希域刻意收窄 | README.md:291; tools/hash_spec.py:21-24 | 冻结字节仅aos-spec.md + SPEC-FINGERPRINT.md |
| E14 | 控制台绑定回环、无认证层 | README.md:287; tools/console.py:102-104 | "binds to 127.0.0.1 only and ships without an authentication layer" |
| E15 | "信任即产品"价值主张 | docs/STRATEGY.md:47 | "一个会大声说'我不做什'的系统，本身就是……信任资产"① |
| E17 | 草案不是事实、晋升需提案 | README.md:255 | "a draft is not a fact, promotion requires a GOV-1 proposal" |
| E18 | 脏数据拒绝而非洗白 | README.md:274; tools/data_import.py:9-11 | "dirty rows are refused, never laundered" |
| E21 | GOV-3触及基座自动拒绝 | docs/aos-spec.md:391 | "base_layer_touched: yes = 触及基座，自动拒绝" |
| E22 | 声明-注册双射 | src/kernel/registration.py:341-363 | "declared != registered"显式拒绝 |
| E23 | 三阶段门控 | README.md:137; src/cli/main.py:135-169 | 结构指纹→密码学hash→declared==registered，任一失败退出非零 |

① 原文作"我不做什"，疑脱"么"字，此处照录未改。E15来自战略稿，属信息性文档、不在冻结哈希域内[E13]；引用它作为批判分析对象，而非规范性依据。

E6 的 README.md:282 与 :300 均已回查，分别对应“No proof of compliance”条目与否认合规证明表。编号沿用作者内部证据登记体系，空缺编号（E7、E16、E19、E20）对应本文未引用的工程断言。证据使用说明：3.4节正文列举的三项拒绝（E6、E3、E17）与其余工程限定（E8–E14）均已回补，无失锚断言；E12–E14的工程细节不在正文展开，读者可据本表核查。

---

说明：本表编号沿用作者内部证据登记体系，空缺编号（E7、E16、E19、E20）对应论文未引用的工程断言。文中凡涉 AosKeel 意图判断处，均以"作者陈述"标注并指向本表锚点；E15 来自战略稿，属信息性文档、不在冻结哈希域内，在论文 4.3 节作为批判对象而非规范依据。
