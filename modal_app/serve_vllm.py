"""OpenAI-compatible vLLM server on Modal for Hawthorne Market agents (Qwen3-14B, thinking on).

Deploy the base model:
    modal deploy modal_app/serve_vllm.py

Deploy a fine-tuned (merged) checkpoint stored in the `hawthorne-models` volume:
    HAWTHORNE_SERVE_MODEL=/models/graft_retain HAWTHORNE_SERVE_NAME=graft-retain \
        modal deploy modal_app/serve_vllm.py

Deploy with activation steering (vector file on the `hawthorne-data` volume, see modal_app/steering.py):
    HAWTHORNE_STEER_FILE=/data/steer/desperation.npz HAWTHORNE_STEER_ALPHA=0.15 \
        HAWTHORNE_SERVE_NAME=steer-desperation modal deploy modal_app/serve_vllm.py

The served model name is always "hawthorne" so client code never changes.
"""

import os

import modal

MODEL_PATH = os.environ.get("HAWTHORNE_SERVE_MODEL", "Qwen/Qwen3-14B")
SERVE_NAME = os.environ.get("HAWTHORNE_SERVE_NAME", "base")
GPU = os.environ.get("HAWTHORNE_GPU", "H100")
MAX_MODEL_LEN = int(os.environ.get("HAWTHORNE_MAX_MODEL_LEN", "20480"))
N_REPLICAS_MIN = int(os.environ.get("HAWTHORNE_MIN_CONTAINERS", "0"))
N_REPLICAS_MAX = int(os.environ.get("HAWTHORNE_MAX_CONTAINERS", "6"))
STEER_FILE = os.environ.get("HAWTHORNE_STEER_FILE", "")
STEER_ALPHA = os.environ.get("HAWTHORNE_STEER_ALPHA", "0")
STEER_PLUGIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steer_plugin")

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0", "huggingface_hub[hf_transfer]")
    .env({
        "HF_XET_HIGH_PERFORMANCE": "1",
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "VLLM_LOG_STATS_INTERVAL": "30",
        "HAWTHORNE_SERVE_MODEL": MODEL_PATH,
        "HAWTHORNE_MAX_MODEL_LEN": str(MAX_MODEL_LEN),
        "HAWTHORNE_STEER_FILE": STEER_FILE,
        "HAWTHORNE_STEER_ALPHA": STEER_ALPHA,
        # a compiled graph cached by an unsteered (or differently steered) server must never be reused
        **({"VLLM_DISABLE_COMPILE_CACHE": "1"} if STEER_FILE else {}),
    })
    .add_local_dir(STEER_PLUGIN, "/opt/steer_plugin", copy=True)
    .run_commands("python -m pip install --no-deps /opt/steer_plugin")
)

hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)
models_vol = modal.Volume.from_name("hawthorne-models", create_if_missing=True)
data_vol = modal.Volume.from_name("hawthorne-data", create_if_missing=True)

app = modal.App(f"hawthorne-vllm-{SERVE_NAME}")

MINUTES = 60
VLLM_PORT = 8000


@app.server(
    image=vllm_image,
    gpu=GPU,
    scaledown_window=8 * MINUTES,
    startup_timeout=20 * MINUTES,
    min_containers=N_REPLICAS_MIN,
    max_containers=N_REPLICAS_MAX,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
        "/models": models_vol,
        "/data": data_vol,
    },
    port=VLLM_PORT,
    target_concurrency=40,
    unauthenticated=True,
)
class Server:
    @modal.enter()
    def start(self):
        import subprocess
        model = os.environ["HAWTHORNE_SERVE_MODEL"]
        cmd = [
            "vllm", "serve", model,
            "--served-model-name", "hawthorne", model,
            "--host", "0.0.0.0", "--port", str(VLLM_PORT),
            "--uvicorn-log-level=warning",
            "--max-model-len", os.environ["HAWTHORNE_MAX_MODEL_LEN"],
            "--max-num-seqs", "128",
            "--gpu-memory-utilization", "0.92",
            "--dtype", "bfloat16",
            "--no-enforce-eager",
            "--tensor-parallel-size", "1",
            "--reasoning-parser", "qwen3",
        ]
        print(*cmd)
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()


@app.local_entrypoint()
async def test():
    import asyncio, time, json
    import aiohttp
    url = await Server.get_url.aio()
    print("server url:", url)
    async with aiohttp.ClientSession(base_url=url) as s:
        deadline = time.time() + 19 * MINUTES
        while time.time() < deadline:
            try:
                async with s.get("/health", timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass
            await asyncio.sleep(5)
        payload = {"model": "hawthorne", "messages": [
            {"role": "system", "content": "Reply with JSON only."},
            {"role": "user", "content": 'What is 17*23? Return {"answer": <int>}'}],
            "max_tokens": 1500, "temperature": 0.6, "top_p": 0.95, "top_k": 20}
        async with s.post("/v1/chat/completions", json=payload) as r:
            d = await r.json()
            msg = d["choices"][0]["message"]
            print("reasoning:", (msg.get("reasoning_content") or msg.get("reasoning") or "")[:400])
            print("content:", msg.get("content"))
            print("usage:", d.get("usage"))
