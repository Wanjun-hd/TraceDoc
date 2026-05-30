"""
最小可交付科研版：对比学习训练脚本（可选依赖 sentence-transformers）

输入: data/pseudo_labeled_pairs.jsonl
输出: data/contrastive_train_report.json

说明:
- 若环境有 sentence-transformers，则执行轻量训练
- 若没有，则输出“训练计划 + 样本统计”，用于中期检查可交付
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS_PATH = ROOT / "data" / "pseudo_labeled_pairs.jsonl"
REPORT_PATH = ROOT / "data" / "contrastive_train_report.json"


def load_pairs():
    rows = []
    if not PAIRS_PATH.is_file():
        return rows
    with PAIRS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def write_report(payload):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 训练报告写入: {REPORT_PATH}")


def main():
    pairs = load_pairs()
    if not pairs:
        write_report(
            {
                "status": "no_data",
                "message": "未找到伪标签训练对，请先执行 research/pseudo_label_generator.py",
            }
        )
        return

    try:
        from sentence_transformers import InputExample, SentenceTransformer, losses  # type: ignore
        from torch.utils.data import DataLoader  # type: ignore

        model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        train_examples = []
        for row in pairs:
            train_examples.append(
                InputExample(
                    texts=[row["query"], row["positive_text"]],
                    label=1.0,
                )
            )
            train_examples.append(
                InputExample(
                    texts=[row["query"], row["negative_text"]],
                    label=0.0,
                )
            )

        train_loader = DataLoader(train_examples, shuffle=True, batch_size=16)
        train_loss = losses.CosineSimilarityLoss(model=model)
        model.fit(train_objectives=[(train_loader, train_loss)], epochs=1, warmup_steps=10)
        out_dir = ROOT / "data" / "embedding_model_min"
        model.save(str(out_dir))
        write_report(
            {
                "status": "trained",
                "pairs": len(pairs),
                "examples": len(train_examples),
                "output_model_dir": str(out_dir),
            }
        )
    except Exception as exc:
        write_report(
            {
                "status": "plan_only",
                "pairs": len(pairs),
                "message": "当前环境未安装 sentence-transformers 或训练失败，已完成可复现训练计划准备。",
                "error": str(exc),
                "next": [
                    "pip install sentence-transformers torch",
                    "python research/contrastive_train_min.py",
                ],
            }
        )


if __name__ == "__main__":
    main()
