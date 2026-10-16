#!/usr/bin/env python3
"""并发对比套件：同一套负载打不同部署（flashnext 单实例 vs 双卡各一实例）
用法:
  python3 concurrency_bench.py --endpoints 127.0.0.1:18024 --model flash-next-w4a16 \
      --tag flashnext --out results/conc-flashnext-new.json
  python3 concurrency_bench.py --endpoints 127.0.0.1:8081 127.0.0.1:8083 --model qwen3.8-27b \
      --tag dual27b --out results/conc-dual27b-new.json
"""
import argparse, json, os, random, time, statistics, urllib.request
from concurrent.futures import ThreadPoolExecutor

APIKEY = os.environ.get("OPENAI_API_KEY", "")

BODY = ("请围绕给定主题展开论述，要求结构清晰、论据充实。主题编号 {n}："
        "论数字基础设施的韧性设计。" )
# 拼到约 1000 token：中文 ~1 token/字，重复到 ~1400 字符留裕量
def make_prompt(n):
    seed = f"[req-{n}-{random.randbytes(4).hex()}] "
    p = seed
    while len(p) < 2600:
        p += ("城市供水系统的冗余设计包括多水源、环状管网与在线传感；"
              "resilience requires redundancy, observability and graceful degradation；"
              "故障注入演练能暴露单点，灰度发布能隔离风险。")
    return p + f"\n\n{BODY.format(n=n)}"

def one_request(base, model, prompt, max_tokens, timeout=180):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"http://{base}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {APIKEY}"} if APIKEY else
                                        {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    wall = time.time() - t0
    ct = out["usage"]["completion_tokens"]
    pt = out["usage"]["prompt_tokens"]
    return {"wall": wall, "ct": ct, "pt": pt}

def run_level(endpoints, model, C, max_tokens, rep, seed0):
    reqs = []
    with ThreadPoolExecutor(max_workers=C) as ex:
        futs = []
        for i in range(C):
            ep = endpoints[i % len(endpoints)]      # 双端点时 50/50 轮询分流
            futs.append(ex.submit(one_request, ep, model, make_prompt(seed0 + i), max_tokens))
        for f in futs:
            try:
                reqs.append(f.result())
            except Exception as e:
                reqs.append({"wall": -1, "ct": 0, "pt": 0, "err": str(e)})
    return reqs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", nargs="+", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=2)
    args = ap.parse_args()
    random.seed(7)
    levels = [1, 2, 4, 8]
    report = {"tag": args.tag, "endpoints": args.endpoints, "model": args.model,
              "max_tokens": 300, "prompt_tokens_approx": 1400, "levels": {}}
    seed0 = 10000
    for C in levels:
        for rep in range(args.reps):
            t0 = time.time()
            reqs = run_level(args.endpoints, args.model, C, 300, rep, seed0)
            seed0 += C + 10
            time.sleep(1.0)
            total_ct = sum(r["ct"] for r in reqs)
            walls = [r["wall"] for r in reqs if r["wall"] > 0]
            errors = [r for r in reqs if r.get("err") or r["wall"] < 0]
            # All requests start together; the slowest request defines batch makespan.
            agg = total_ct / max(max(walls) if walls else time.time() - t0 - 1.0, 0.01)
            entry = {"rep": rep, "agg_tok_s": round(agg, 1),
                     "total_ct": total_ct,
                     "avg_wall": round(statistics.mean(walls), 2) if walls else None,
                     "max_wall": round(max(walls), 2) if walls else None,
                     "errors": len(errors)}
            report["levels"].setdefault(str(C), []).append(entry)
            print(f"[C={C} rep={rep}] agg={entry['agg_tok_s']} tok/s "
                  f"avg_wall={entry['avg_wall']}s max_wall={entry['max_wall']}s "
                  f"errors={entry['errors']}", flush=True)
    # 汇总
    summary = {}
    for C in levels:
        reps = report["levels"][str(C)]
        summary[str(C)] = round(statistics.mean(r["agg_tok_s"] for r in reps), 1)
    report["agg_summary"] = summary
    print("SUMMARY " + json.dumps(summary), flush=True)
    with open(args.out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"{args.tag.upper()}_CONC_DONE", flush=True)

if __name__ == "__main__":
    main()
