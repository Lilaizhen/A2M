import argparse
import json
import math
from pathlib import Path
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def load_tools(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "attack_tools" in first:
            extracted = []
            for entry in data:
                tools = entry.get("attack_tools") or []
                if isinstance(tools, dict):
                    tools = [tools]
                for tool in tools:
                    if not isinstance(tool, dict):
                        continue
                    name = tool.get("name")
                    desc = tool.get("description")
                    if name or desc:
                        extracted.append(
                            {
                                "name": name,
                                "description": desc,
                                "return_value": tool.get("return_value"),
                            }
                        )
            if extracted:
                return extracted
        if isinstance(first, dict) and "tools" in first:
            extracted = []
            for entry in data:
                tools_by_server = entry.get("tools") or {}
                for server in tools_by_server.values():
                    for tool in server.get("tools", []):
                        extracted.append(
                            {
                                "name": tool.get("name"),
                                "description": tool.get("description"),
                            }
                        )
            return extracted

    return data


def build_text(item, mode: str, include_return_value: bool) -> str:
    name = (item.get("name") or "").strip()
    desc = (item.get("description") or "").strip()
    if mode == "name":
        text = name
    elif mode == "description":
        text = desc
    elif name and desc:
        text = f"{name}\n{desc}"
    else:
        text = name or desc
    if include_return_value:
        return_value = item.get("return_value")
        if return_value is not None:
            if isinstance(return_value, str):
                rv_text = return_value.strip()
            else:
                rv_text = json.dumps(return_value, ensure_ascii=False)
            if rv_text:
                if text:
                    text = f"{text}\n{rv_text}"
                else:
                    text = rv_text
    return text


def resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def get_max_length(model, override: Optional[int]) -> int:
    if override:
        return override
    config = model.config
    for attr in ("n_positions", "max_position_embeddings"):
        value = getattr(config, attr, None)
        if isinstance(value, int) and value > 0:
            return value
    return 1024


def compute_ppl_for_tokens(
    token_ids, model, device: str, max_length: int, stride: int
):
    if len(token_ids) < 2:
        return None, 0, 0.0

    total_nll = 0.0
    total_tokens = 0
    for i in range(0, len(token_ids), stride):
        begin_loc = max(i + stride - max_length, 0)
        end_loc = min(i + stride, len(token_ids))
        trg_len = end_loc - i

        input_slice = torch.tensor(token_ids[begin_loc:end_loc], device=device).unsqueeze(0)
        labels = input_slice.clone()
        labels[:, :-trg_len] = -100

        with torch.no_grad():
            outputs = model(input_ids=input_slice, labels=labels)
            total_nll += outputs.loss.item() * trg_len
            total_tokens += trg_len

        if end_loc == len(token_ids):
            break

    if total_tokens == 0:
        return None, 0, 0.0
    ppl = math.exp(total_nll / total_tokens)
    return ppl, total_tokens, total_nll


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute GPT-2 perplexity for tool descriptions."
    )
    parser.add_argument(
        "--input",
        default="configs/tool2mcp_tools.json",
        help="Input JSON list containing tool entries.",
    )
    parser.add_argument(
        "--output",
        default="configs/tool2mcp_tools_ppl.json",
        help="Output JSON file with per-tool perplexity.",
    )
    parser.add_argument(
        "--model-path",
        default="/home/llz/models/gpt2",
        help="Local path to the GPT-2 model.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Device to run inference on.",
    )
    parser.add_argument(
        "--text-mode",
        default="name+description",
        choices=["name", "description", "name+description"],
        help="Which fields to evaluate.",
    )
    parser.add_argument(
        "--include-return-value",
        action="store_true",
        help="Append return_value content to the evaluated text if present.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=None,
        help="Override model max length for sliding window.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=None,
        help="Stride for sliding window; defaults to half of max length.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N tools.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    tools = load_tools(input_path)
    if not isinstance(tools, list):
        raise ValueError("Input JSON must be a list of tool entries.")
    if args.limit:
        tools = tools[: args.limit]

    device = resolve_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(args.model_path)
    model.to(device)
    model.eval()

    max_length = get_max_length(model, args.max_length)
    stride = args.stride if args.stride else max_length // 2
    if stride <= 0:
        stride = max_length

    results = []
    total_nll = 0.0
    total_tokens = 0

    for idx, item in enumerate(tools, start=1):
        text = build_text(item, args.text_mode, args.include_return_value)
        token_ids = tokenizer.encode(text, add_special_tokens=False)
        ppl, token_count, nll = compute_ppl_for_tokens(
            token_ids, model, device, max_length, stride
        )

        if token_count > 0:
            total_nll += nll
            total_tokens += token_count

        results.append(
            {
                "name": item.get("name"),
                "description": item.get("description"),
                "ppl": ppl,
                "tokens": token_count,
            }
        )

        if idx % 50 == 0 or idx == len(tools):
            print(f"Processed {idx}/{len(tools)} tools")

    overall_ppl = math.exp(total_nll / total_tokens) if total_tokens else None
    valid_ppls = [item["ppl"] for item in results if item["ppl"] is not None]
    valid_count = len(valid_ppls)
    min_ppl = min(valid_ppls) if valid_ppls else None
    max_ppl = max(valid_ppls) if valid_ppls else None
    gt_50 = sum(1 for value in valid_ppls if value > 50) / valid_count if valid_count else 0.0
    gt_100 = sum(1 for value in valid_ppls if value > 100) / valid_count if valid_count else 0.0
    gt_200 = sum(1 for value in valid_ppls if value > 200) / valid_count if valid_count else 0.0

    output_payload = {
        "model_path": args.model_path,
        "input": str(input_path),
        "text_mode": args.text_mode,
        "include_return_value": args.include_return_value,
        "max_length": max_length,
        "stride": stride,
        "overall_ppl": overall_ppl,
        "total_tokens": total_tokens,
        "stats": {
            "count": valid_count,
            "min_ppl": min_ppl,
            "max_ppl": max_ppl,
            "ratio_gt_50": gt_50,
            "ratio_gt_100": gt_100,
            "ratio_gt_200": gt_200,
        },
        "items": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote results to {output_path}")
    if overall_ppl is not None:
        print(f"Overall PPL: {overall_ppl:.4f} (tokens: {total_tokens})")
        print(
            "Stats: count={count} min={min_ppl} max={max_ppl} "
            "ratio_gt_50={ratio_gt_50:.4f} ratio_gt_100={ratio_gt_100:.4f} "
            "ratio_gt_200={ratio_gt_200:.4f}".format(**output_payload["stats"])
        )


if __name__ == "__main__":
    main()
