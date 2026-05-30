## 最小可交付科研版（已实现）

### 1) 审计日志（合规可追溯）
- 文件：`audit_logger.py`
- 日志：`data/audit_log.jsonl`
- 已接入事件：
  - 登录成功/失败
  - 注册成功
  - 推理成功/失败（含后端模式、用户、主诉摘要/错误摘要）

### 2) 证据可信度建模（工程近似）
- 文件：`local_rag_client.py`
- 实现：
  - 检索融合分数中加入 `LEVEL_CREDIBILITY`
  - 指南 > 文献 > 病例 > unknown
  - 证据记录包含 `evidence_id`，并输出到 traceability（support_point 中可见）

### 3) 伪标签 + 对比学习（最小实验闭环）
- 伪标签生成：`research/pseudo_label_generator.py`
  - 输入：`data/unlabeled_queries.jsonl`
  - 输出：`data/pseudo_labeled_pairs.jsonl`
- 对比学习训练：`research/contrastive_train_min.py`
  - 有 `sentence-transformers` 时执行1 epoch轻量训练并保存模型
  - 无依赖时也会生成 `data/contrastive_train_report.json`（可交付计划+统计）

## 推荐执行顺序
1. `python research/pseudo_label_generator.py`
2. `python research/contrastive_train_min.py`
3. 查看 `data/contrastive_train_report.json`

## 说明
- 当前方案为“科研最小可交付”：优先保证可复现、可展示、可继续扩展。
- 若后续要进一步对齐文档中 3.2~3.3 的算法级声明（注意力改造/动态权重学习），需引入自定义模型训练与推理框架。
