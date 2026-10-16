# Qwen3.8-Flash-Next on 2× CMP 170HX Gen2 x4：独立复现报告

这是一次在 **2× NVIDIA CMP 170HX 64GB、PCIe Gen2 x4、无 NVLink/P2P** 主机上的
独立复现、质量验证和并发对照。项目重点不是重新发明 Flash-Next 部署方案，而是记录：

- 社区的双卡 W4A16 + FP8 PLE 配方在受限 PCIe 拓扑上能否运行；
- 性能与社区 Gen2 x16 参考之间有多大差距；
- 输出质量、并发扩展、部署冲突和恢复流程是否可验证。

完整时间线、计量公式和失败记录见 [`REPRODUCTION.md`](REPRODUCTION.md)。

## 结论

完整 262,144 token 配置可以在本机启动并通过质量测试，但跨卡通信受限时，吞吐明显低于
社区 x16 参考。我们的实测是：

| 项目 | 实测结果 |
|---|---:|
| 单流 decode，temperature=0 | 54.7–62.0 tok/s，均值约 58 |
| 冷 prefill，约 7K prompt | 1,377–1,380 tok/s |
| 冷 prefill，约 28K prompt | 1,411–1,413 tok/s |
| 并发聚合，C=1/2/4/8 | 49.6 / 70.5 / 100.5 / 130.9 tok/s |
| 11 题烟雾测试 | 11/11 |
| 修订后的 150 题确定性测试 | 150/150 |

同机对照的两个独立 Qwen3.8-27B 实例在 C=1/2/4/8 时分别达到
89.8 / 164.8 / 263.8 / 444.7 tok/s。该比较只说明这台机器上的服务形态差异，
不代表 27B 与 Flash-Next 的模型质量等价。

## 归属与独立工作边界

基础实现来自社区：

- [`moriyasujapan/qwen38-flash-next-vllm-2x170hx`](https://github.com/moriyasujapan/qwen38-flash-next-vllm-2x170hx)：
  双卡配方、FP8 PLE 转换器和基础 benchmark；本次复现固定参考 commit
  `819c5b81bcc4a89d4b0d9eab1979593a66ea4956`。
- [`alesha-pro/qwen38-flash-next-4x3090`](https://github.com/alesha-pro/qwen38-flash-next-4x3090)：
  PLE CPU-offload overlays；固定参考 commit
  `9b36aaec3f604d726c6b751e29f7de8225fc203b`。
- vLLM 社区提供 Flash-Next CUDA 13.0 镜像。
- 模型权重来自 Qwen/Intel，受各自模型许可证约束，不包含在本仓库中。

本仓库原创增量是：

- HPZ8 Gen2 x4 环境适配与完整复现记录；
- 11 题和 150 题确定性质量夹具；
- Flash-Next 与同机双 27B 服务的并发对照夹具；
- 原始结果、失败记录、瓶颈分析和安全恢复注意事项。

本仓库不声称原创 FP8 PLE 转换算法、vLLM overlays 或基础双卡方案。

## 测试环境

| 项目 | 配置 |
|---|---|
| GPU | 2× CMP 170HX，解锁至每卡 64GB |
| GPU 架构 | GA100 / sm_80 |
| PCIe | 每卡链路状态 Gen2 x4；无 NVLink，P2P 不可用 |
| 模型 | Qwen3.8-Flash-Next W4A16 AutoRound |
| PLE | 外置 FP8 E4M3，约 51.3GB，CPU offload |
| 并行 | TP=2 + expert parallel |
| 推测解码 | MTP，`num_speculative_tokens=4` |
| KV | BF16，每卡显式分配 24,383,208,960 bytes |
| 最大上下文 | 262,144 |
| 运行时 | `vllm/vllm-openai:qwen38-flash-next-x86_64-cu130` |

## 复现步骤

### 1. 获取并固定上游实现

```bash
git clone https://github.com/moriyasujapan/qwen38-flash-next-vllm-2x170hx
cd qwen38-flash-next-vllm-2x170hx
git checkout 819c5b81bcc4a89d4b0d9eab1979593a66ea4956
./scripts/setup.sh
```

请先阅读上游 README，并遵守模型、镜像和 overlay 的许可证。

### 2. 准备模型和 FP8 PLE

按上游步骤下载 W4A16 检查点并运行：

```bash
./scripts/build-ple-fp8.sh
```

该步骤读取约 102GB BF16 PLE，写出约 51GB FP8 PLE。它是模型转换，不是本地编译
vLLM/CUDA kernel。

### 3. 启动服务

复制 [`scripts/run-local.example.sh`](scripts/run-local.example.sh)，按本机路径和 GPU 编号修改后执行。
启动前必须确保两卡有足够显存；本次测试中，额外约 1.5GB 常驻显存已经足以让固定 KV
配置在初始化阶段 OOM。

### 4. 运行质量和并发测试

```bash
export OPENAI_BASE_URL=http://127.0.0.1:18024/v1
export MODEL=flash-next-w4a16

python3 bench/quality_suite.py
python3 bench/eval150.py
python3 bench/concurrency_bench.py \
  --endpoints 127.0.0.1:18024 \
  --model flash-next-w4a16 \
  --tag flashnext \
  --out results/conc_flashnext-new.json
```

如服务需要认证，通过 `OPENAI_API_KEY` 提供；测试脚本不会读取系统配置文件。

## 原始结果

- [`results/flashnext-quality-suite.json`](results/flashnext-quality-suite.json)
- [`results/eval150-results.json`](results/eval150-results.json)
- [`results/conc-flashnext.json`](results/conc-flashnext.json)
- [`results/conc-dual27b.json`](results/conc-dual27b.json)

150 题覆盖算术、JSON 格式、列表约束、标识符转录、字母计数、数字排序、数字串转录和
中英混排转录。它是确定性功能夹具，不是通用能力排行榜；`150/150` 不应被解释为模型
在开放式任务上“满分”。

## 怎样理解性能差距

上游 x16 报告约 100–110 tok/s 自然文本单流和约 387 tok/s 八并发；本机分别约 58 和
130.9 tok/s。PCIe Gen2 x4、无 P2P 的拓扑是最明显的差异：TP all-reduce、EP all-to-all
以及外置 PLE 访问都可能受限。

不过，本次没有在同一台机器上完成 x4/x16 单变量 A/B，因此“PCIe 是主要瓶颈”属于有
硬件证据支持的解释，不是严格因果证明。MTP 接受率、prompt、计速窗口和运行时版本也会
显著改变 tok/s。

## 已知问题

- 模型可能在 reasoning 中消耗完整个 `max_tokens`，留下空的最终答案；调用方应限制推理预算并处理空 content。
- `max-num-batched-tokens=4096` 在上游测试中会让约 7K prefill 返回 HTTP 500；复现保持 1024。
- 显式 KV 大小接近满卡，启动前必须清理无关 GPU 进程。
- 不要把 aggregate tok/s、单流 decode tok/s 和包含 TTFT 的端到端速度混为一谈。
- CMP 170HX 解锁使用修改驱动，存在维护和稳定性风险；本仓库不提供驱动修改。

## 许可证

本仓库原创代码与文档使用 Apache-2.0。模型、容器、上游脚本及 overlays 仍受各自许可证约束。
详见 [`NOTICE`](NOTICE)。
