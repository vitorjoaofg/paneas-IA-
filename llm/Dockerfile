FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install vllm==0.4.2 \
    && pip install torchvision==0.18.0 \
    && pip install -r requirements.txt \
    && pip uninstall -y flashinfer || true

RUN python - <<'PY'
from pathlib import Path

config_path = Path('/opt/conda/lib/python3.10/site-packages/vllm/config.py')
source = config_path.read_text()
needle = '    rope_scaling = getattr(hf_config, "rope_scaling", None)\\n'
replacement = (
    '    rope_scaling = getattr(hf_config, "rope_scaling", None)\\n'
    '    if rope_scaling is not None:\\n'
    '        rope_scaling = dict(rope_scaling)\\n'
    '        if "type" not in rope_scaling and "rope_type" in rope_scaling:\\n'
        '            rope_scaling["type"] = rope_scaling["rope_type"]\\n'
)
if replacement not in source:
    updated = source.replace(needle, replacement, 1)
    config_path.write_text(updated)
PY

RUN python - <<'PY'
from pathlib import Path

lm_path = Path('/opt/conda/lib/python3.10/site-packages/lmformatenforcer/integrations/transformers.py')
source = lm_path.read_text()
old_block = """try:
    from transformers import AutoModelForCausalLM
    from transformers.generation.logits_process import LogitsWarper, PrefixConstrainedLogitsProcessor
    from transformers.tokenization_utils import PreTrainedTokenizerBase
except ImportError:
    raise ImportError('transformers is not installed. Please install it with "pip install transformers[torch]"')
"""
new_block = """try:
    from transformers import AutoModelForCausalLM
    from transformers.tokenization_utils import PreTrainedTokenizerBase
    from transformers.generation import logits_process as _logits_process
    PrefixConstrainedLogitsProcessor = _logits_process.PrefixConstrainedLogitsProcessor
    LogitsWarper = getattr(_logits_process, 'LogitsWarper', None)
    if LogitsWarper is None:
        from transformers.generation.logits_process import LogitsProcessor as LogitsWarper
except ImportError:
    raise ImportError('transformers is not installed. Please install it with "pip install transformers[torch]"')
"""
if old_block in source:
    source = source.replace(old_block, new_block)
    lm_path.write_text(source)
PY

RUN python - <<'PY'
from pathlib import Path

rope_path = Path('/opt/conda/lib/python3.10/site-packages/vllm/model_executor/layers/rotary_embedding.py')
source = rope_path.read_text()
if 'class Llama3RotaryEmbedding' not in source:
    insert_anchor = 'class Phi3SuScaledRotaryEmbedding'
    insert_idx = source.find(insert_anchor)
    llama3_class = """

class Llama3RotaryEmbedding(RotaryEmbedding):
    def __init__(self, head_size: int, rotary_dim: int,
                 max_position_embeddings: int, base: int,
                 is_neox_style: bool, rope_scaling: Dict[str, Any]) -> None:
        self._rope_scaling = dict(rope_scaling)
        super().__init__(head_size, rotary_dim, max_position_embeddings, base,
                         is_neox_style)

    def _compute_inv_freq(self, base: Union[int, float]) -> torch.Tensor:
        inv_freq = super()._compute_inv_freq(base)
        rope = self._rope_scaling
        factor = float(rope.get("factor", 1.0))
        low_freq_factor = float(rope.get("low_freq_factor", 1.0))
        high_freq_factor = float(rope.get("high_freq_factor", low_freq_factor))
        original_max = float(
            rope.get("original_max_position_embeddings",
                     self.max_position_embeddings))
        if factor == 0:
            return inv_freq
        if high_freq_factor == low_freq_factor:
            return inv_freq / factor

        low_freq_wavelen = original_max / low_freq_factor
        high_freq_wavelen = original_max / high_freq_factor

        wavelen = (2 * math.pi) / inv_freq
        scaled = torch.where(wavelen > low_freq_wavelen, inv_freq / factor,
                             inv_freq)
        smooth_factor = (
            (original_max / wavelen) - low_freq_factor) / (
                high_freq_factor - low_freq_factor)
        smoothed = (1 - smooth_factor) * (scaled / factor) + \
            smooth_factor * scaled
        medium_mask = (~(wavelen < high_freq_wavelen)) & (
            ~(wavelen > low_freq_wavelen))
        return torch.where(medium_mask, smoothed, scaled)
"""
    source = source[:insert_idx] + llama3_class + source[insert_idx:]
    source = source.replace(
        '        elif scaling_type == "su":\n',
        '        elif scaling_type == "llama3":\n'
        '            rotary_emb = Llama3RotaryEmbedding(head_size, rotary_dim,\n'
        '                                              max_position, base,\n'
        '                                              is_neox_style, rope_scaling)\n'
        '        elif scaling_type == "su":\n')
    rope_path.write_text(source)
PY

COPY . /app

EXPOSE 8001

ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]
