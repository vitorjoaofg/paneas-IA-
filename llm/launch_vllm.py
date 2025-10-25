import os

from vllm import EngineArgs, LLMEngine


def create_vllm_engine(model_path: str, dtype: str = "float16") -> LLMEngine:
    engine_args = EngineArgs(
        model=model_path,
        dtype=dtype,
        tensor_parallel_size=2,
        pipeline_parallel_size=1,
        gpu_memory_utilization=0.92,
        max_num_seqs=64 if dtype == "float16" else 96,
        max_model_len=16384,
        max_num_batched_tokens=16384,
        disable_log_requests=True,
        enable_prefix_caching=True,
        swap_space=4,
        enforce_eager=False,
        trust_remote_code=False,
        download_dir="/models/cache",
    )

    return LLMEngine.from_engine_args(engine_args)
