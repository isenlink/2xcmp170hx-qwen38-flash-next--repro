#!/usr/bin/env python3
"""FlashNext 精度/质量测试套件：11 题，可核验答案为主"""
import json, os, time, urllib.request

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:18024/v1").rstrip("/")
URL = f"{BASE_URL}/chat/completions"
MODEL = os.environ.get("MODEL", "flash-next-w4a16")
OUT = os.environ.get("OUT", "results/flashnext-quality-suite-new.json")
API_KEY = os.environ.get("OPENAI_API_KEY", "")

QS = [
    ("算术", "计算 17×23 + 456÷8 − 12 = ？只输出最终数字。", 200),
    ("应用题-鸡兔", "鸡兔同笼，头 35 个，脚 94 只。兔几只、鸡几只？格式：兔X鸡Y", 300),
    ("逻辑-说谎", "甲说「乙说谎」，乙说「丙说谎」，丙说「甲和乙都在说谎」。已知三人中只有一人说真话，说真话的是谁？只输出「甲/乙/丙」。", 400),
    ("陷阱-小数", "9.11 和 9.9 哪个更大？只输出那个数。", 200),
    ("计数-字母", "单词 strawberry 里有几个字母 r？只输出数字。", 200),
    ("代码", "写一个 Python 函数 is_palindrome(s)：忽略大小写与非英文字母字符，判断回文。只输出代码块，不要解释。", 600),
    ("指令遵循", "用恰好 3 句话介绍光合作用，每句必须依次以「首先」「其次」「最后」开头。", 500),
    ("知识-精确值", "光在真空中的速度精确值是多少米/秒？只输出数字。", 200),
    ("应用题-水池", "水池开进水管 5 小时注满，开出水管 8 小时放空。两管同时开，几小时注满？用分数小时回答，格式：X/Y", 300),
    ("幻觉检测", "《狂人日记》的作者是谁？只输出人名。", 200),
    ("中文写作", "以「雨后的城市」为题写一段 60 字左右的微散文，有意象、有画面感。", 500),
]

def ask(qid, prompt, max_tokens):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(URL, data=body, headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    dt = time.time() - t0
    msg = out["choices"][0]["message"]
    text = (msg.get("content") or "").strip()
    usage = out.get("usage", {})
    return dt, text, usage

def main():
    results = []
    for i, (tag, prompt, mt) in enumerate(QS, 1):
        try:
            dt, text, usage = ask(tag, prompt, mt)
            results.append({"i": i, "tag": tag, "q": prompt, "a": text,
                            "s": round(dt, 1), "ct": usage.get("completion_tokens")})
            print(f"=== [{i}] {tag} ({dt:.1f}s, {usage.get('completion_tokens')}tok) ===", flush=True)
            print(text[:600], flush=True)
            print(flush=True)
        except Exception as e:
            results.append({"i": i, "tag": tag, "q": prompt, "a": f"ERROR: {e}", "s": 0, "ct": 0})
            print(f"=== [{i}] {tag} ERROR {e} ===", flush=True)
    with open(OUT, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("QUALITY_SUITE_DONE", flush=True)

if __name__ == "__main__":
    main()
