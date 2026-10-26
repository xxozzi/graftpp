"""Smoke test of the deployed server before launch: one thinking call with the real round-1 seller prompt.

    python results/hawthorne_negotiation/smoke_test.py --repo <path to his clone> --base-url <URL>/v1

Waits for /health, then sends one call through his own LLMClient (thinking on, seed 0) and checks that the
reply carries reasoning_content and parses as his JSON (a "price" field). Prints no secrets (the server
needs none).
"""
import argparse
import asyncio
import sys
import time

import httpx


async def main(args):
    sys.path.insert(0, args.repo)
    from hawthorne.llm import LLMClient, LLMConfig
    from hawthorne.market import MarketParams, equilibria
    from hawthorne.prompts import EpisodeConfig, seller_system_prompt, seller_round_prompt

    root = args.base_url.rsplit("/v1", 1)[0]
    t0 = time.time()
    async with httpx.AsyncClient(timeout=60) as c:
        while time.time() - t0 < 25 * 60:
            try:
                r = await c.get(root + "/health")
                if r.status_code == 200:
                    break
                print(f"health {r.status_code} at {time.time() - t0:.0f}s", flush=True)
            except Exception as e:
                print(f"health error at {time.time() - t0:.0f}s: {type(e).__name__}", flush=True)
            await asyncio.sleep(10)
    print(f"server healthy after {time.time() - t0:.0f}s", flush=True)

    cfg = EpisodeConfig(condition="unwatched", goal="profit", seed=0, n_rounds=30, stakes="base", n_sellers=2,
                        memory=True, indefinite=True, negotiate=False)
    mp = MarketParams(n_sellers=2)
    eq = equilibria(mp)
    system = seller_system_prompt(0, cfg, mp, eq)
    user = seller_round_prompt(0, cfg, 0, [], [], [], 0.0, 0, notes={"plans": "", "insights": ""},
                               review={})
    client = LLMClient(LLMConfig(base_url=args.base_url, model="hawthorne"))
    t1 = time.time()
    resp = await client.chat(system, user, seed=0, thinking=True)
    await client.close()
    print(f"call took {time.time() - t1:.0f}s, attempts={resp.attempts}, finish={resp.finish_reason}, "
          f"prompt_tokens={resp.prompt_tokens}, completion_tokens={resp.completion_tokens}, "
          f"fallback_nothink={resp.fallback_nothink}")
    print(f"reasoning_content chars: {len(resp.reasoning)}")
    print("reasoning head:", resp.reasoning[:300].replace("\n", " "))
    print("content:", resp.text[:600])
    print("parsed:", resp.parsed)
    ok = bool(resp.reasoning) and isinstance(resp.parsed, dict) and "price" in resp.parsed
    print("SMOKE TEST", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base-url", required=True)
    asyncio.run(main(ap.parse_args()))
