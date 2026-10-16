#!/usr/bin/env python3
"""FlashNext 150 题能力测试 v2：修复出题 bug 后重测（同种子同题目）
修复：①中英混排双句号歧义（指令在前、句子在末尾、不追加标点）
     ②列表判分近义词宽松（前缀匹配，桃/桃子）
     ③max_tokens 预算上调，防推理吃预算误判截断
"""
import json, os, random, re, time, urllib.request

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:18024/v1").rstrip("/")
URL = f"{BASE_URL}/chat/completions"
MODEL = os.environ.get("MODEL", "flash-next-w4a16")
LOG = os.environ.get("LOG", "results/eval150-progress.log")
OUT = os.environ.get("OUT", "results/eval150-results-new.json")
API_KEY = os.environ.get("OPENAI_API_KEY", "")

random.seed(20260926)

PROVINCES = ["河北","山西","辽宁","吉林","黑龙江","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","海南","四川","贵州","云南","陕西","甘肃","青海","台湾","内蒙古","广西","西藏","宁夏","新疆","北京","天津","上海","重庆"]
FRUITS = ["苹果","香蕉","橙子","葡萄","西瓜","草莓","芒果","菠萝","荔枝","樱桃","桃子","梨","柚子","石榴","柿子","杏","李子","猕猴桃","哈密瓜","火龙果","山竹","椰子","枇杷","杨梅","桑葚","百香果","牛油果"]
CITIES = ["上海","北京","深圳","广州","杭州","成都","南京","武汉","西安","重庆","苏州","天津","长沙","郑州","青岛","大连","厦门","福州","合肥","昆明","哈尔滨","沈阳","济南","宁波","无锡","佛山","东莞","南宁","石家庄","贵阳"]

def pool_ok(item, pool):
    if item in pool: return True
    # 近义/前缀宽松：桃 ↔ 桃子
    return any(item.startswith(p) or p.startswith(item) for p in pool if len(item) >= 1 and len(p) >= 1)

def build():
    qs = []
    # 1. 算术运算 19
    for i in range(19):
        if i % 3 == 0:
            a, b = random.randint(11, 99), random.randint(11, 99)
            d = random.choice([4, 6, 8, 9, 12]); c = d * random.randint(3, 88)
            e = random.randint(5, 200)
            expr = f"{a}×{b} + {c}÷{d} − {e}"; exp = a * b + c // d - e
        elif i % 3 == 1:
            a, b = random.randint(12, 99), random.randint(12, 99)
            c = random.randint(3, 20)
            e = random.choice([3, 4, 5, 6, 8]); d = e * random.randint(4, 66)
            expr = f"（{a} + {b}）×{c} − {d}÷{e}"; exp = (a + b) * c - d // e
        else:
            a, b = random.randint(12, 88), random.randint(12, 88)
            c, d = random.randint(3, 19), random.randint(3, 19)
            e = random.randint(10, 99)
            expr = f"{a}×{b} − {c}×{d} + {e}"; exp = a * b - c * d + e
        qs.append(("算术运算", f"计算 {expr} = ？只输出最终数字。",
                   lambda s, e=exp: s.strip() == str(e), 800))

    # 2. JSON 格式跟随 19
    names = ["Widget-X7","Bolt-M20","Sensor-A3","Cable-USB-C","Filter-P3","Valve-V8","Pump-H5","Nozzle-N2"]
    for i in range(19):
        nm = random.choice(names) + f"-{random.randint(10,99)}"
        stock, price = random.randint(3, 999), random.randint(10, 9999)
        tags = random.sample(["sale","new","hot","vip","eco","pro"], random.randint(1, 3))
        prompt = (f'根据信息输出一个 JSON 对象，键必须是 name、stock、price、tags（字符串数组），'
                  f'顺序也按此顺序。信息：name={nm}，stock={stock}，price={price}，tags={tags}。'
                  f"只输出 JSON 本身，不要解释不要代码块标记。")
        def chk(s, nm=nm, stock=stock, price=price, tags=tags):
            t = re.sub(r"^```(json)?\s*|\s*```$", "", s.strip()).strip()
            try: j = json.loads(t)
            except Exception:
                m = re.search(r"\{.*\}", t, re.S)
                if not m: return False
                try: j = json.loads(m.group(0))
                except Exception: return False
            if not isinstance(j, dict): return False
            if list(j.keys()) != ["name", "stock", "price", "tags"]: return False
            if j["name"] != nm: return False
            try:
                if int(j["stock"]) != stock or int(j["price"]) != price: return False
            except Exception: return False
            return list(j["tags"]) == tags
        qs.append(("JSON格式跟随", prompt, chk, 1500))

    # 3. 列表计数约束 19
    pools = [("中国省份", PROVINCES), ("水果", FRUITS), ("城市", CITIES)]
    for i in range(19):
        label, pool = pools[i % 3]
        n = random.randint(6, 10)
        prompt = (f"恰好列出 {n} 个不同的{label}名，用顿号「、」分隔，一行输出。"
                  f"严格正好 {n} 个，不多不少。只输出这一行。")
        def chk(s, n=n, pool=pool):
            items = [x for x in re.split(r"[、,，;；\s]+", s.strip()) if x]
            if len(items) != n: return False
            if len(set(items)) != n: return False
            return all(pool_ok(x, pool) for x in items)
        qs.append(("列表计数约束", prompt, chk, 1000))

    # 4. 标识符转录 19
    def rand_ident():
        first = random.choice("_" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
        body = "".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
                       for _ in range(random.randint(7, 15)))
        return first + body
    for i in range(19):
        ident = rand_ident()
        qs.append(("标识符转录", f"把下面的标识符原样输出（区分大小写）：{ident}。只输出该标识符。",
                   lambda s, e=ident: s.strip() == e, 800))

    # 5. 字母计数 19
    for i in range(19):
        s = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(random.randint(15, 30)))
        if i % 7 == 0:
            ch = random.choice("ghijkxyz")
            if ch in s: s = s.replace(ch, "q", 1)
        else:
            ch = random.choice("abcdefgh")
        exp = s.count(ch)
        qs.append(("字母计数", f"字符串 {s} 中字母 {ch} 出现了几次？只输出数字。",
                   lambda x, e=exp: x.strip() == str(e), 600))

    # 6. 数字排序 19（15 升序 + 4 降序）
    for i in range(19):
        n = random.randint(8, 12)
        nums = [random.randint(-999, 9999) for _ in range(n)]
        while len(set(nums)) < n:
            nums = [random.randint(-999, 9999) for _ in range(n)]
        desc = i >= 15
        exp = sorted(nums, reverse=desc)
        order = "从大到小" if desc else "从小到大"
        prompt = f"把下面的数列按{order}排列：{' '.join(map(str, nums))}。用一个空格分隔，只输出排序后的数列。"
        qs.append(("数字排序", prompt, lambda s, e=exp: [int(x) for x in re.findall(r"-?\d+", s)] == e, 3000))

    # 7. 数字串转录 18
    for i in range(18):
        digits = "".join(random.choice("0123456789") for _ in range(random.randint(32, 40)))
        qs.append(("数字串转录", f"把下面的数字串原样复制一遍：{digits}。只输出该数字串。",
                   lambda s, e=digits: s.strip() == e, 800))

    # 8. 中英混排转录 18 —— 修复：指令在前、句子在末尾、不追加任何标点
    frags = [
        "部署完成，server ready on port {p}，请访问 http://host:{p}/api/v1/status 确认。",
        "订单 {a}-{b} 已发货，tracking number {c}，预计 {d} 天内送达 inbox。",
        "函数 calc_{e}() 返回 {f}，错误码 E{g} 表示 timeout。",
        "版本 v{h}.{i} 更新：fix {j} bug，性能提升 {k}%。",
        "节点 node-{m} 在 rack {n}，延迟 {o} ms，丢包率 {p2}%。",
        "会议 rescheduled 至 {q} 月 {r} 日 {s}:00，地点 Room {t}。",
    ]
    for i in range(18):
        tpl = frags[i % len(frags)]
        sent = tpl.format(p=random.randint(1024, 65535), a=random.randint(10000, 99999),
                          b=random.randint(10, 99), c="".join(random.choice("0123456789") for _ in range(12)),
                          d=random.randint(2, 30), e=random.choice(["total","delta","ratio"]),
                          f=random.randint(1, 999), g=random.randint(100, 999),
                          h=random.randint(1, 9), i=random.randint(0, 9),
                          j=random.randint(1, 50), k=random.randint(5, 90),
                          m=random.randint(1, 64), n=random.randint(1, 12),
                          o=random.randint(1, 999), p2=round(random.uniform(0.1, 5.0), 1),
                          q=random.randint(1, 12), r=random.randint(1, 28),
                          s=random.randint(8, 21), t=random.randint(1, 30))
        prompt = (f"请把下面这句话原样输出，标点、大小写、数字全部一致，只输出这句话本身，"
                  f"不要引号、不要任何多余字符：\n{sent}")
        qs.append(("中英混排转录", prompt, lambda x, e=sent: x.strip() == e, 3000))
    return qs

def ask(prompt, max_tokens, timeout=180):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0, "max_tokens": max_tokens}).encode()
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(URL, data=body, headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    dt = time.time() - t0
    m = out["choices"][0]["message"]
    return dt, (m.get("content") or "").strip(), out["choices"][0].get("finish_reason")

def main():
    qs = build()
    assert len(qs) == 150, f"题目数错误: {len(qs)}"
    results = []
    cats = {}
    with open(LOG, "w") as lg:
        lg.write(f"start {time.strftime('%F %T')} total={len(qs)} v2\n"); lg.flush()
        for i, (cat, prompt, chk, mt) in enumerate(qs, 1):
            rec = {"i": i, "cat": cat, "q": prompt}
            try:
                dt, ans, fr = ask(prompt, mt)
                if ans == "":
                    dt2, ans, fr = ask(prompt, mt * 4)
                    dt += dt2
                    rec["retry"] = True
                ok = bool(chk(ans))
            except Exception as e:
                ans, ok, dt, fr = f"ERROR:{e}", False, 0.0, "error"
            rec.update({"ok": ok, "ans": ans[:200], "s": round(dt, 1), "fr": fr})
            results.append(rec)
            cats.setdefault(cat, [0, 0])
            cats[cat][1] += 1
            if ok: cats[cat][0] += 1
            line = f"[{i:3d}/150] {cat} {'PASS' if ok else 'FAIL'} {dt:.1f}s"
            if not ok: line += f" | got={ans[:80]!r}"
            lg.write(line + "\n"); lg.flush()
            time.sleep(0.15)
        total_ok = sum(v[0] for v in cats.values())
        summary = {"overall": f"{total_ok}/150", "rate": round(total_ok / 150 * 100, 1),
                   "by_cat": {k: f"{v[0]}/{v[1]}" for k, v in cats.items()}}
        lg.write("SUMMARY " + json.dumps(summary, ensure_ascii=False) + "\n")
        lg.write("EVAL150V2_DONE\n"); lg.flush()
    with open(OUT, "w") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
