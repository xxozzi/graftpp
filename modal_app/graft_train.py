"""GRAFT / GRAFT++ supervised fine-tuning with dual LoRA adapters on Qwen3-14B (Modal, H100).

Follows the SFT variant of Ward*, Hu* et al. (2026), "Gradient Routing Localizes and
Removes Unintended Behaviors in RL" (GRAFT), re-implemented compactly:

  * Two LoRA adapters (RETAIN, FORGET) on every attention/MLP projection of a frozen base.
  * Per-example gradient routing (micro-batch 1, grad accumulation):
        forget       : forward R+F ; grads -> FORGET only (x kappa), RETAIN grads zeroed
        unclassified : forward R+F ; grads -> both
        retain/anchor: forward R only (FORGET ablated) ; grads -> RETAIN only
        soft w in[0,1]: forward R+F ; retain grad x(1-w), forget grad x(1+(kappa-1)w)
                        (GRAFT++: w = calibrated probe probability of collusive intent)
  * Deployment = merge RETAIN into the base weights (FORGET ablated).

Dataset: /data/<run>/train.jsonl, records
  {"id","system","user","reasoning","content","cls": "forget"|"unclassified"|"retain", "w": float?}

Usage:
  modal run modal_app/graft_train.py --run graft_text --epochs 2
  modal run modal_app/graft_train.py::merge --run graft_text --config retain_only
"""

import json
import math
import os
import time

import modal

from common import torch_image, VOLUMES, MODEL_ID, build_chat_text, data_vol, models_vol

app = modal.App("hawthorne-graft")

TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


# --------------------------------------------------------------------------- #
# Dual LoRA
# --------------------------------------------------------------------------- #

def _dual_lora_module():
    import torch
    import torch.nn as nn

    class DualLoRALinear(nn.Module):
        def __init__(self, base: nn.Linear, r: int, alpha: float):
            super().__init__()
            self.base = base
            for p in self.base.parameters():
                p.requires_grad = False
            dt, dev = base.weight.dtype, base.weight.device
            self.r, self.scaling = r, alpha / r
            self.A_retain = nn.Parameter(torch.empty(r, base.in_features, dtype=dt, device=dev))
            self.B_retain = nn.Parameter(torch.zeros(base.out_features, r, dtype=dt, device=dev))
            self.A_forget = nn.Parameter(torch.empty(r, base.in_features, dtype=dt, device=dev))
            self.B_forget = nn.Parameter(torch.zeros(base.out_features, r, dtype=dt, device=dev))
            nn.init.kaiming_uniform_(self.A_retain, a=math.sqrt(5))
            nn.init.kaiming_uniform_(self.A_forget, a=math.sqrt(5))
            self.scale_retain = 1.0
            self.scale_forget = 1.0

        def forward(self, x):
            out = self.base(x)
            if self.scale_retain != 0.0:
                out = out + (x @ self.A_retain.t() @ self.B_retain.t()) * (self.scaling * self.scale_retain)
            if self.scale_forget != 0.0:
                out = out + (x @ self.A_forget.t() @ self.B_forget.t()) * (self.scaling * self.scale_forget)
            return out

        def retain_params(self):
            return [self.A_retain, self.B_retain]

        def forget_params(self):
            return [self.A_forget, self.B_forget]

        @torch.no_grad()
        def delta(self, which: str):
            if which == "retain":
                return (self.B_retain.float() @ self.A_retain.float()) * self.scaling
            if which == "forget":
                return (self.B_forget.float() @ self.A_forget.float()) * self.scaling
            raise ValueError(which)

    return DualLoRALinear


def inject(model, r: int, alpha: float):
    import torch.nn as nn
    DualLoRALinear = _dual_lora_module()
    for p in model.parameters():
        p.requires_grad = False
    n = 0
    for name, mod in list(model.named_modules()):
        for t in TARGETS:
            child = getattr(mod, t, None)
            if isinstance(child, nn.Linear):
                setattr(mod, t, DualLoRALinear(child, r, alpha))
                n += 1
    return n


def adapters(model):
    DualLoRALinear = _dual_lora_module()
    return [m for m in model.modules() if type(m).__name__ == "DualLoRALinear"]


def set_scales(model, retain: float, forget: float):
    for m in adapters(model):
        m.scale_retain, m.scale_forget = retain, forget


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #

@app.function(image=torch_image, gpu="H100", timeout=6 * 3600, volumes=VOLUMES, memory=64 * 1024)
def train(run: str, epochs: int = 2, lr: float = 1e-4, r: int = 16, alpha: float = 32.0,
          step_size: int = 16, kappa: float = 2.0, max_len: int = 9000, warmup_ratio: float = 0.1,
          seed: int = 0, max_examples: int = -1, weight_decay: float = 1e-4) -> dict:
    import random
    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    run_dir = f"/data/{run}"
    records = [json.loads(l) for l in open(f"{run_dir}/train.jsonl")]
    if max_examples > 0:
        records = records[:max_examples]
    print(f"[{run}] {len(records)} training examples; cls counts:",
          {c: sum(1 for x in records if x['cls'] == c) for c in ('forget', 'unclassified', 'retain')})

    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map="cuda",
                                                 attn_implementation="sdpa")
    n_mod = inject(model, r, alpha)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    ads = adapters(model)
    retain_params = [p for m in ads for p in m.retain_params()]
    forget_params = [p for m in ads for p in m.forget_params()]
    print(f"injected {n_mod} dual-LoRA modules; trainable retain={sum(p.numel() for p in retain_params)/1e6:.1f}M "
          f"forget={sum(p.numel() for p in forget_params)/1e6:.1f}M")

    # --- tokenize
    def encode(rec):
        p_text, t_text, a_text = build_chat_text(tok, rec["system"], rec["user"], rec.get("reasoning", ""),
                                                 rec.get("content", ""), thinking=rec.get("thinking", True))
        p_ids = tok(p_text, add_special_tokens=False)["input_ids"]
        resp_ids = tok(t_text + a_text, add_special_tokens=False)["input_ids"]
        ids = (p_ids + resp_ids)[:max_len]
        labels = ([-100] * len(p_ids) + resp_ids)[:max_len]
        return ids, labels

    data = []
    for rec in records:
        ids, labels = encode(rec)
        if sum(1 for l in labels if l != -100) < 8:
            continue
        cls = rec["cls"]
        w = rec.get("w")
        if cls == "forget":
            r_scale, f_scale, ablate_forget = 0.0, kappa, False
        elif cls == "retain":
            r_scale, f_scale, ablate_forget = 1.0, 0.0, True
        elif cls == "unclassified" and w is not None:          # soft routing (GRAFT++)
            w = float(min(max(w, 0.0), 1.0))
            r_scale, f_scale, ablate_forget = 1.0 - w, 1.0 + (kappa - 1.0) * w, False
        else:
            r_scale, f_scale, ablate_forget = 1.0, 1.0, False
        data.append({"ids": ids, "labels": labels, "cls": cls, "r": r_scale, "f": f_scale,
                     "ablate": ablate_forget, "id": rec["id"]})
    print(f"{len(data)} examples after encoding; mean len={np.mean([len(d['ids']) for d in data]):.0f}")

    opt_r = torch.optim.AdamW(retain_params, lr=lr, betas=(0.9, 0.95), weight_decay=weight_decay)
    opt_f = torch.optim.AdamW(forget_params, lr=lr, betas=(0.9, 0.95), weight_decay=weight_decay)
    total_steps = max(1, epochs * len(data) // step_size)
    warmup = max(1, int(warmup_ratio * total_steps))

    def lr_at(step):
        if step < warmup:
            return lr * (step + 1) / warmup
        prog = (step - warmup) / max(1, total_steps - warmup)
        return 0.5 * lr * (1 + math.cos(math.pi * prog))

    def scale_hooks(params, scale):
        if scale == 1.0:
            return []
        return [p.register_hook(lambda g, s=scale: g * s) for p in params]

    log_path = f"{run_dir}/train_log.jsonl"
    logf = open(log_path, "a")
    model.train()
    step, t0 = 0, time.time()
    for ep in range(epochs):
        order = list(range(len(data)))
        random.shuffle(order)
        buf, losses = [], {"forget": [], "unclassified": [], "retain": []}
        used_r = used_f = False
        for k, idx in enumerate(order):
            ex = data[idx]
            cur_lr = lr_at(step)
            for g in opt_r.param_groups: g["lr"] = cur_lr
            for g in opt_f.param_groups: g["lr"] = cur_lr
            if ex["ablate"]:
                set_scales(model, 1.0, 0.0)
            hooks = scale_hooks(retain_params, ex["r"]) + scale_hooks(forget_params, ex["f"])
            try:
                x = torch.tensor([ex["ids"]], device="cuda")
                y = torch.tensor([ex["labels"]], device="cuda")
                out = model(input_ids=x, labels=y)
                loss = out.loss / step_size
                loss.backward()
                losses[ex["cls"]].append(out.loss.item())
            finally:
                for h in hooks: h.remove()
                if ex["ablate"]:
                    set_scales(model, 1.0, 1.0)
            used_r |= ex["r"] > 0
            used_f |= (ex["f"] > 0 and not ex["ablate"])
            buf.append(idx)
            if len(buf) == step_size or k == len(order) - 1:
                torch.nn.utils.clip_grad_norm_(retain_params + forget_params, 1.0)
                if used_r: opt_r.step()
                if used_f: opt_f.step()
                opt_r.zero_grad(set_to_none=True); opt_f.zero_grad(set_to_none=True)
                step += 1
                rec_log = {"step": step, "epoch": ep, "lr": cur_lr, "elapsed": time.time() - t0,
                           **{f"loss_{c}": (float(np.mean(v)) if v else None) for c, v in losses.items()}}
                logf.write(json.dumps(rec_log) + "\n"); logf.flush()
                if step % 5 == 0 or step == 1:
                    print(f"[{run}] ep{ep} step {step}/{total_steps} "
                          + " ".join(f"{c}={np.mean(v):.3f}" for c, v in losses.items() if v)
                          + f" lr={cur_lr:.2e} {time.time()-t0:.0f}s", flush=True)
                buf, losses = [], {"forget": [], "unclassified": [], "retain": []}
                used_r = used_f = False
    logf.close()

    # --- save adapters
    sd = {}
    for name, m in model.named_modules():
        if type(m).__name__ == "DualLoRALinear":
            for pn in ("A_retain", "B_retain", "A_forget", "B_forget"):
                sd[f"{name}.{pn}"] = getattr(m, pn).detach().cpu()
    torch.save({"state_dict": sd, "r": r, "alpha": alpha, "targets": TARGETS}, f"{run_dir}/adapters.pt")
    data_vol.commit()
    print(f"[{run}] saved adapters -> {run_dir}/adapters.pt in {time.time()-t0:.0f}s")
    return {"run": run, "steps": step, "n": len(data), "seconds": time.time() - t0}


# --------------------------------------------------------------------------- #
# Merge RETAIN (and/or FORGET) into base weights -> standard HF checkpoint for vLLM
# --------------------------------------------------------------------------- #

@app.function(image=torch_image, gpu="H100", timeout=2 * 3600, volumes=VOLUMES, memory=96 * 1024)
def merge(run: str, config: str = "retain_only") -> str:
    """config in {retain_only, both, forget_only}."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    ck = torch.load(f"/data/{run}/adapters.pt", map_location="cpu")
    sd, scaling = ck["state_dict"], ck["alpha"] / ck["r"]
    use_r = config in ("retain_only", "both")
    use_f = config in ("forget_only", "both")
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    n = 0
    with torch.no_grad():
        for name, mod in model.named_modules():
            for t in TARGETS:
                lin = getattr(mod, t, None)
                key = f"{name}.{t}"
                if lin is None or f"{key}.A_retain" not in sd:
                    continue
                delta = torch.zeros_like(lin.weight, dtype=torch.float32)
                if use_r:
                    delta += (sd[f"{key}.B_retain"].float() @ sd[f"{key}.A_retain"].float()).to("cuda") * scaling
                if use_f:
                    delta += (sd[f"{key}.B_forget"].float() @ sd[f"{key}.A_forget"].float()).to("cuda") * scaling
                lin.weight.add_(delta.to(lin.weight.dtype))
                n += 1
    dest = f"/models/{run}__{config}"
    os.makedirs(dest, exist_ok=True)
    model.save_pretrained(dest, safe_serialization=True, max_shard_size="5GB")
    tok.save_pretrained(dest)
    models_vol.commit()
    print(f"merged {n} modules ({config}) -> {dest}")
    return dest


@app.local_entrypoint()
def main(run: str = "graft_text", epochs: int = 2, lr: float = 1e-4, step_size: int = 16,
         kappa: float = 2.0, max_examples: int = -1, merge_configs: str = "retain_only"):
    res = train.remote(run, epochs=epochs, lr=lr, step_size=step_size, kappa=kappa,
                       max_examples=max_examples)
    print(res)
    cfgs = [c for c in merge_configs.split(",") if c]
    for dest in merge.map([run] * len(cfgs), cfgs):
        print("merged ->", dest)
