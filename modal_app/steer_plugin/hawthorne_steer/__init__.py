"""vLLM general plugin: add a fixed steering vector to the residual stream after one Qwen3 decoder layer.

No-op unless HAWTHORNE_STEER_FILE is set.  The file (.npz, written by modal_app/steering.py) holds
`vec` (unit vector), `layer` (decoder-layer index) and `norm` (mean residual-stream norm at that layer);
HAWTHORNE_STEER_ALPHA scales the vector in units of that norm.

vLLM's Qwen3DecoderLayer returns (hidden_states, residual) whose sum is the residual stream, so adding to
the returned hidden_states is the same intervention as adding to HF's hidden_states[layer + 1].
"""

import os


def register():
    path = os.environ.get("HAWTHORNE_STEER_FILE")
    if not path:
        return
    import numpy as np
    import torch
    from vllm.model_executor.models import qwen3
    from vllm.model_executor.models.utils import extract_layer_index

    cls = qwen3.Qwen3DecoderLayer
    if getattr(cls, "_hawthorne_steered", False):
        return
    d = np.load(path)
    layer = int(d["layer"])
    alpha = float(os.environ.get("HAWTHORNE_STEER_ALPHA", "0"))
    vec = (alpha * float(d["norm"]) * d["vec"]).astype("float32")
    orig_init, orig_forward = cls.__init__, cls.forward

    def __init__(self, *args, prefix: str = "", **kwargs):
        orig_init(self, *args, prefix=prefix, **kwargs)
        self._steer_on = extract_layer_index(prefix) == layer
        if self._steer_on:
            # built under vLLM's default-device/dtype context, so this lands on the GPU in bf16
            self.register_buffer("_steer", torch.tensor(vec, dtype=torch.get_default_dtype()), persistent=False)

    def forward(self, positions, hidden_states, residual):
        hidden_states, residual = orig_forward(self, positions, hidden_states, residual)
        if self._steer_on:
            hidden_states = hidden_states + self._steer
        return hidden_states, residual

    cls.__init__, cls.forward, cls._hawthorne_steered = __init__, forward, True
    print(f"[hawthorne-steer] {path}: layer={layer} alpha={alpha} |alpha*v|={np.linalg.norm(vec):.1f}", flush=True)
