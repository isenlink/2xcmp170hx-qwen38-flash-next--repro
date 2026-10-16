# 给文强的发布交接

## 建议仓库

- 名称：`qwen38-flash-next-2x170hx-gen2x4-repro`
- 可见性：Public
- 默认分支：`main`
- 简介：`Independent Qwen3.8-Flash-Next reproduction on 2x CMP 170HX Gen2 x4, with raw benchmarks and quality harnesses.`
- Topics：`qwen`、`vllm`、`cmp170hx`、`flash-next`、`llm-inference`、`benchmark`

## 发布前必读

1. 这是社区方案的独立复现，不是原创 Flash-Next runtime。
2. 不要把上游 x16 的 97.8–170 tok/s 或 386.9 tok/s 写成我们的实测。
3. 我们的 HPZ8 Gen2 x4 数据是单流 54.7–62.0 tok/s、C=8 聚合 130.9 tok/s。
4. README/NOTICE 已明确标注 `moriyasujapan`、`alesha-pro`、vLLM 和模型权重归属。
5. 包内没有模型权重、镜像、驱动补丁、API key 或内网地址。

## 已完成验证

```text
Python syntax:          3/3 PASS
eval150 generated cases: 150 PASS
JSON result files:      4/4 PASS
sensitive-pattern scan: 0 hits
git working tree:       clean
```

本地根提交：`d742b83`。加入本交接文件后会有第二个提交；以归档内 `git log` 为准。

## GitHub 发布命令

解压归档并进入仓库后：

```bash
git status --short --branch
git log --oneline --decorate -3
gh repo create qwen38-flash-next-2x170hx-gen2x4-repro \
  --public \
  --source . \
  --remote origin \
  --push
```

若要发到组织账号，给 `gh repo create` 使用完整的 `ORG/repo` 名称。

## 发布后验收

- GitHub 首页正确渲染 `README.md`；
- `README.md` 中两个上游链接可点击；
- 四个 `results/*.json` 可以下载；
- 默认分支为 `main`；
- License 显示 Apache-2.0；
- 仓库中不存在模型权重、`.env`、密钥或主机私有配置；
- Release/帖子引用我们的数据时明确写 `PCIe Gen2 x4`。
