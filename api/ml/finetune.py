"""LoRA fine-tune of a multilingual encoder (MuRIL default, XLM-R fallback).

Fits the 4GB-GPU budget: LoRA adapters only, fp16, small batches with
gradient accumulation. Reports the same metrics as the baseline so the
two are directly comparable.

Usage:
  .venv/bin/python -m ml.finetune [--model xlm-roberta-base] [--epochs 10]
"""

from __future__ import annotations

import argparse
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


def main() -> None:
    import numpy as np
    import torch
    from peft import LoraConfig, get_peft_model, TaskType
    from sklearn.metrics import f1_score
    from sklearn.utils.class_weight import compute_class_weight
    from torch import nn
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    from . import dataset, evaluate

    class WeightedTrainer(Trainer):
        """Cross-entropy with balanced class weights: without this, 178
        examples collapse to the majority class."""

        def __init__(self, *args, class_weights=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.class_weights = class_weights

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            weight = (
                self.class_weights.to(outputs.logits.device)
                if self.class_weights is not None
                else None
            )
            loss = nn.functional.cross_entropy(outputs.logits, labels, weight=weight)
            return (loss, outputs) if return_outputs else loss

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/muril-base-cased")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lr", type=float, default=3e-4)
    args = parser.parse_args()

    print("cuda:", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")

    items, reviewed = dataset.load_items()
    print(dataset.describe(items))
    print("data status:", "REVIEWED" if reviewed else "PRE-REVIEW (candidates only)")
    splits = dataset.stratified_split(items, seed=args.seed)

    tok = AutoTokenizer.from_pretrained(args.model)
    base = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=3)
    lora_cfg = LoraConfig(
        task_type=TaskType.SEQ_CLS, r=16, lora_alpha=32, lora_dropout=0.1,
        target_modules=["query", "value"],
    )
    model = get_peft_model(base, lora_cfg)
    model.print_trainable_parameters()

    def encode(split: list[dict]) -> dict:
        enc = tok(
            [i["text"] for i in split], truncation=True, padding=True, max_length=256
        )
        enc["labels"] = [i["label_id"] for i in split]
        return enc

    class SplitDataset(torch.utils.data.Dataset):
        def __init__(self, enc: dict):
            self.enc = enc

        def __len__(self) -> int:
            return len(self.enc["labels"])

        def __getitem__(self, i: int) -> dict:
            return {k: torch.tensor(v[i]) for k, v in self.enc.items()}

    train_ds = SplitDataset(encode(splits["train"]))
    val_ds = SplitDataset(encode(splits["val"]))
    test_ds = SplitDataset(encode(splits["test"]))

    def macro_f1(eval_pred) -> dict:
        logits, labels = eval_pred
        return {"macro_f1": f1_score(labels, np.argmax(logits, axis=1), average="macro")}

    out_dir = ARTIFACTS / "muril-lora"
    training_args = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=16,
        gradient_accumulation_steps=2,
        learning_rate=args.lr,
        weight_decay=0.01,
        label_smoothing_factor=0.1,
        fp16=torch.cuda.is_available(),
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        seed=args.seed,
        report_to="none",
        logging_steps=10,
    )
    trainer = WeightedTrainer(
        model=model, args=training_args, train_dataset=train_ds,
        eval_dataset=val_ds, compute_metrics=macro_f1,
        class_weights=torch.tensor(
            compute_class_weight(
                "balanced", classes=np.array([0, 1, 2]),
                y=np.array([i["label_id"] for i in splits["train"]]),
            ),
            dtype=torch.float,
        ),
    )
    trainer.train()
    trainer.save_model(str(out_dir))
    tok.save_pretrained(str(out_dir))

    for name, ds in (("val", val_ds), ("test", test_ds)):
        pred = trainer.predict(ds)
        ids = [int(i) for i in np.argmax(pred.predictions, axis=1)]
        print()
        print(evaluate.report(
            [i["label_id"] for i in splits[name]], ids,
            f"finetuned({args.model})/{name}",
        ))


if __name__ == "__main__":
    main()
