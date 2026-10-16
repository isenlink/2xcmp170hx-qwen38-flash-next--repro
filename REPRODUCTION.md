# 复现记录与计量口径

## 时间线

测试日期：2026-09-26，时区 Asia/Shanghai。

| 时间 | 动作 | 结果 |
|---|---|---|
| 12:24 | 下载 W4A16 检查点 | 开始 |
| 14:10 | 17 个权重分片与索引核验 | PASS |
| 14:14 | BF16 PLE 转 FP8并验证 manifest | PASS |
| 14:33 | 停止占卡服务、登记维护状态、启动容器 | 开始 |
| 14:43 | Flash-Next 服务健康 | PASS，约 10 分钟启动 |
| 14:50 | 单流和 prefill 基准 | 完成 |
| 15:42 | 11 题质量烟雾 | 11/11 |
| 15:52 | 150 题 v1 | 139/150；发现夹具缺陷 |
| 16:07 | 修正夹具后用同一种子重测 | 150/150 |
| 16:13 | Flash-Next 并发基准 | 完成 |
| 16:23 | 双 27B 对照基准 | 完成 |
| 16:45 | 停止实验服务并恢复原服务 | 开始 |
| 17:0x | 三个原服务健康检查、GPU 错误检查 | PASS |

## 实际运行配置

```text
tensor_parallel_size=2
enable_expert_parallel=true
speculative_method=mtp
num_speculative_tokens=4
max_model_len=262144
max_num_seqs=8
max_num_batched_tokens=1024
gpu_memory_utilization=0.92
kv_cache_memory=24383208960 bytes/card
kv_cache_dtype=auto (BF16)
cudagraph_mode=FULL_DECODE_ONLY
```

没有在本机重新编译 vLLM 或 CUDA kernel。启动使用预编译 CUDA 13.0 镜像，通过 bind mount
加载固定版本的 Python overlays。启动阶段包含引擎初始化和 CUDA Graph capture，这不等同于
本地编译新的推理内核。

## 性能口径

### 单流 decode

`54.7–62.0 tok/s` 来自 temperature=0、约 600 completion tokens 的单流请求。该数字不包含
prefill，但会受输出内容和 MTP 接受率影响。

### Prefill

约 7K 和 28K prompt 使用冷输入测量。报告值分别为 1,377–1,380 和 1,411–1,413 input tok/s。

### 并发 aggregate tok/s

每个并发层级执行两轮；请求同时提交，单请求目标约 1,400 prompt tokens + 300 completion
tokens。aggregate throughput 定义为：

```text
所有成功请求的 completion_tokens 总和 / 该批请求的 makespan
```

原始 JSON 保留每轮的 completion token 数、平均 wall time、最大 wall time和错误数。

### 质量测试

11 题套件包含确定答案与开放式烟雾项。150 题套件只评估可程序判定的功能：

- 算术运算：19
- JSON 格式跟随：19
- 列表计数约束：19
- 标识符转录：19
- 字母计数：19
- 数字排序：19
- 数字串转录：18
- 中英混排转录：18

v1 的 11 个失败来自题面双句号歧义、过严的字符串判定及 token 预算不足。修订版保持随机
种子 `20260926`，修正夹具后得到 150/150。本仓库只发布修订版脚本和结果，避免传播已知
有缺陷的评分口径。

## 遇到的问题

1. 固定 KV 配置接近占满显存；其他服务占用约 1.5GB 时，初始化会 CUDA OOM。
2. 本机管理程序曾在测试窗口自动拉起原服务，造成资源争用；测试前必须停用自动恢复行为。
3. 模型可能把全部 token 预算用于 reasoning，最终 `content` 为空；这不能简单判成知识错误。
4. 两张卡均为 Gen2 x4 且无 P2P；TP、EP 和 PLE offload 都可能经过受限链路。

## 可复现性限制

- 没有在同一主机完成 x4 与 x16 的单变量 A/B。
- speculative decode 对文本可预测性敏感，不同 prompt 的 tok/s 不可直接横比。
- 双 27B 对照是服务形态和吞吐对照，不是模型能力等价对照。
- 结果仅代表这一组硬件、驱动、模型 revision、overlay commit 和运行时镜像。
