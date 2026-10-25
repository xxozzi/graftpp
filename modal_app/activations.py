"""Extract residual-stream activations for Hawthorne trajectories (for probes / GRAFT++ routing).

Input : /data/<name>/records.jsonl   (one record per (episode, round, seller))
          {"id", "system", "user", "reasoning", "content"}
Output: /data/<name>/acts_<shard>.npz with, for each layer L in LAYERS:
          last_prompt_L  [N, d]   residual at the final prompt token (pre-generation)
          think_mean_L   [N, d]   mean over <think> tokens
          answer_mean_L  [N, d]   mean over answer tokens
        plus ids (object array) and n_tokens.

Run:  modal run modal_app/activations.py --name main --shards 4
"""

import json
import os

import modal

from common import torch_image, VOLUMES, MODEL_ID, build_chat_text, data_vol

app = modal.App("hawthorne-activations")

LAYERS = [8, 14, 20, 24, 28, 32, 36]   # of 40 decoder layers (hidden_states index = layer+1)
MAX_LEN = 12000


@app.function(image=torch_image, gpu="H100", timeout=4 * 3600, volumes=VOLUMES)
def extract(name: str, shard: int, n_shards: int, batch_size: int = 1, layers: list[int] | None = None) -> dict:
    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    layers = layers or LAYERS
    path = f"/data/{name}/records.jsonl"
    records = [json.loads(l) for l in open(path)]
    records = records[shard::n_shards]
    print(f"shard {shard}/{n_shards}: {len(records)} records")

    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.bfloat16,
                                                 device_map="cuda", attn_implementation="sdpa")
    model.eval()
    d = model.config.hidden_size
    out = {f"{k}_{L}": np.zeros((len(records), d), dtype=np.float16)
           for L in layers for k in ("last_prompt", "think_mean", "answer_mean")}
    ids, n_tokens, n_think = [], [], []

    with torch.no_grad():
        for i, rec in enumerate(records):
            p_text, t_text, a_text = build_chat_text(tok, rec["system"], rec["user"],
                                                     rec.get("reasoning", ""), rec.get("content", ""),
                                                     thinking=rec.get("thinking", True))
            p_ids = tok(p_text, add_special_tokens=False)["input_ids"]
            t_ids = tok(t_text, add_special_tokens=False)["input_ids"] if t_text else []
            a_ids = tok(a_text, add_special_tokens=False)["input_ids"]
            all_ids = (p_ids + t_ids + a_ids)[:MAX_LEN]
            n_p, n_t = len(p_ids), len(t_ids)
            x = torch.tensor([all_ids], device="cuda")
            hs = model(input_ids=x, output_hidden_states=True).hidden_states
            for L in layers:
                h = hs[L + 1][0].float()          # [T, d]
                out[f"last_prompt_{L}"][i] = h[n_p - 1].cpu().numpy().astype(np.float16)
                if n_t > 0:
                    out[f"think_mean_{L}"][i] = h[n_p:n_p + n_t].mean(0).cpu().numpy().astype(np.float16)
                if len(all_ids) > n_p + n_t:
                    out[f"answer_mean_{L}"][i] = h[n_p + n_t:].mean(0).cpu().numpy().astype(np.float16)
            ids.append(rec["id"]); n_tokens.append(len(all_ids)); n_think.append(n_t)
            if i % 50 == 0:
                print(f"  {i}/{len(records)} tokens={len(all_ids)}", flush=True)
    out["ids"] = np.array(ids, dtype=object)
    out["n_tokens"] = np.array(n_tokens)
    out["n_think"] = np.array(n_think)
    dest = f"/data/{name}/acts_{shard}.npz"
    np.savez_compressed(dest, **out)
    data_vol.commit()
    return {"shard": shard, "n": len(records), "dest": dest}


@app.local_entrypoint()
def main(name: str = "main", shards: int = 4, layers: str = ""):
    ls = [int(x) for x in layers.split(",")] if layers else LAYERS
    results = list(extract.starmap([(name, s, shards, 1, ls) for s in range(shards)]))
    print(results)
