#!/usr/bin/env bash
# Local wrapper around moriyasujapan/qwen38-flash-next-vllm-2x170hx.
set -euo pipefail

: "${UPSTREAM_DIR:?set UPSTREAM_DIR to the pinned upstream checkout}"
: "${MODEL_DIR:?set MODEL_DIR to the W4A16 checkpoint}"
: "${PLE_MODEL_DIR:?set PLE_MODEL_DIR to the derived FP8 PLE checkpoint}"
: "${RECIPE:?set RECIPE to the pinned alesha-pro overlay checkout}"
: "${GPUS:?set GPUS to the two CMP 170HX indices or UUIDs}"

export MODEL_DIR PLE_MODEL_DIR RECIPE GPUS
export IMAGE=${IMAGE:-vllm/vllm-openai:qwen38-flash-next-x86_64-cu130}
export PORT=${PORT:-18024}
export CACHE=${CACHE:-$UPSTREAM_DIR/.cache}
export MAX_MODEL_LEN=${MAX_MODEL_LEN:-262144}
export MAX_NUM_SEQS=${MAX_NUM_SEQS:-8}
export MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-1024}
export KV_CACHE_MEMORY=${KV_CACHE_MEMORY:-24383208960}

exec bash "$UPSTREAM_DIR/scripts/run.sh"
