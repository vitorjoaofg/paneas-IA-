#!/usr/bin/env python3
"""
Transcreve chamadas IZZI em lote via gateway ASR e grava os JSONs em engine/.

Uso típico:
    python transcribe_batch.py --audio-dir ../../izzi_batch_20251120_01_9530/audio --concurrency 8 --language es

O script é reiniciável: arquivos já presentes em engine/*.json são ignorados.
Falhas são registradas em stderr e no summary final.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import httpx

sys.path.append(str(Path(__file__).resolve().parent))
import generate_full_analysis_v3 as g  # noqa: E402

ENGINE_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA = ENGINE_DIR / "metadata.csv"
DEFAULT_OUTPUT_DIR = ENGINE_DIR
DEFAULT_AUDIO_DIR = (ENGINE_DIR.parent.parent / "izzi_batch_20251120_01_9530" / "audio").resolve()
DEFAULT_API_URL = "http://localhost:8000/api/v1/asr"
DEFAULT_LANGUAGE = "es"
DEFAULT_COMPUTE_TYPE = "int8_float16"
DEFAULT_BEAM_SIZE = 5
DEFAULT_NUM_SPEAKERS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcrição em lote para o dashboard IZZI.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="CSV de metadados (; separado).")
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR, help="Pasta com os WAVs.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Onde salvar os JSONs.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Endpoint REST do ASR.")
    parser.add_argument("--bearer", default=None, help="Bearer token (opcional).")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Hint de linguagem para o ASR.")
    parser.add_argument("--concurrency", type=int, default=6, help="Número de chamadas paralelas.")
    parser.add_argument("--limit", type=int, default=None, help="Limite de arquivos a processar (debug).")
    parser.add_argument("--provider", default="paneas", choices=["paneas", "openai", "assemblyai"], help="Provider do ASR.")
    parser.add_argument("--timeout", type=float, default=200.0, help="Timeout por requisição (s).")
    parser.add_argument("--enable-diarization", action="store_true", default=True, help="Usar diarização do ASR interno.")
    parser.add_argument("--use-openai-diarization", action="store_true", default=False, help="Corrigir speakers via OpenAI.")
    parser.add_argument("--num-speakers", type=int, default=DEFAULT_NUM_SPEAKERS, help="Sugestão de número de speakers.")
    parser.add_argument("--compute-type", default=DEFAULT_COMPUTE_TYPE, help="Compute type do ASR interno.")
    parser.add_argument("--beam-size", type=int, default=DEFAULT_BEAM_SIZE, help="Beam size do Whisper.")
    parser.add_argument("--enrich", action="store_true", help="Rodar LLM e atualizar full_analysis.json após cada transcrição.")
    parser.add_argument("--llm-model", default="gpt-4o", help="Modelo de LLM para enriquecimento.")
    parser.add_argument("--llm-workers", type=int, default=1, help="Workers para LLM (usar 1 para sequencial).")
    parser.add_argument("--only-ids", type=str, nargs="*", help="Lista de call_ids específicos para processar.")
    return parser.parse_args()


def read_metadata_ids(metadata_path: Path) -> List[str]:
    import csv

    with metadata_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        ids = []
        for row in reader:
            fid = (row.get("file_id") or "").replace(".WAV", "").strip()
            if fid:
                ids.append(fid)
    return ids


def pending_targets(
    ids: Iterable[str],
    audio_dir: Path,
    output_dir: Path,
    limit: int | None,
) -> List[Tuple[str, Path, Path]]:
    """Return list of (file_id, audio_path, output_path) to process."""
    targets: List[Tuple[str, Path, Path]] = []
    for fid in ids:
        audio_path = audio_dir / f"{fid}.WAV"
        out_path = output_dir / f"{fid}.json"
        if out_path.exists():
            continue
        if not audio_path.exists():
            print(f"[WARN] audio ausente: {audio_path}", file=sys.stderr)
            continue
        targets.append((fid, audio_path, out_path))
        if limit and len(targets) >= limit:
            break
    return targets


def build_payload(
    audio_path: Path,
    language: str,
    provider: str,
    *,
    enable_diarization: bool,
    use_openai_diarization: bool,
    num_speakers: int,
    compute_type: str,
    beam_size: int,
) -> Tuple[Dict[str, str], Dict[str, tuple]]:
    data = {
        "language": language,
        "model": "whisper/medium",
        "enable_diarization": str(enable_diarization).lower(),
        "enable_alignment": "false",
        "use_openai_diarization": str(use_openai_diarization).lower(),
        "num_speakers": str(num_speakers),
        "compute_type": compute_type,
        "vad_filter": "true",
        "beam_size": str(beam_size),
        "provider": provider,
    }
    files = {"file": (audio_path.name, audio_path.read_bytes(), "audio/wav")}
    return data, files


def normalize_response(fid: str, audio_path: Path, payload: Dict[str, any]) -> Dict[str, any]:
    segments_out: List[Dict[str, any]] = []
    for idx, seg in enumerate(payload.get("segments") or []):
        speaker = seg.get("speaker")
        role = seg.get("role")
        if not role and isinstance(speaker, str):
            speaker_norm = speaker.strip().lower()
            if speaker_norm in {"agent", "customer", "ivr"}:
                role = speaker_norm
        segments_out.append(
            {
                "id": idx,
                "start": float(seg.get("start", 0.0) or 0.0),
                "end": float(seg.get("end", 0.0) or 0.0),
                "text": seg.get("text") or "",
                "speaker": speaker,
                "role": role,
                "words": seg.get("words"),
            }
        )

    return {
        "file_path": str(audio_path),
        "file_name": audio_path.name,
        "base_id": fid,
        "transcription": payload.get("text") or "",
        "language": payload.get("language") or "",
        "segments": segments_out,
        "duration": float(payload.get("duration_seconds") or 0.0),
        "metadata": payload.get("metadata"),
    }


async def transcribe_one(
    client: httpx.AsyncClient,
    api_url: str,
    fid: str,
    audio_path: Path,
    output_path: Path,
    language: str,
    provider: str,
    *,
    enable_diarization: bool,
    use_openai_diarization: bool,
    num_speakers: int,
    compute_type: str,
    beam_size: int,
) -> Tuple[str, bool, str | None]:
    import time
    start_time = time.time()
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"[INICIO] {fid} ({file_size_mb:.2f} MB)", flush=True)

    data, files = build_payload(
        audio_path,
        language,
        provider,
        enable_diarization=enable_diarization,
        use_openai_diarization=use_openai_diarization,
        num_speakers=num_speakers,
        compute_type=compute_type,
        beam_size=beam_size,
    )
    resp = await client.post(api_url, data=data, files=files)
    resp.raise_for_status()
    payload = resp.json()
    normalized = normalize_response(fid, audio_path, payload)
    output_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    elapsed = time.time() - start_time
    duration = payload.get("duration_seconds", 0)
    print(f"[ASR-OK] {fid} - Áudio: {duration:.1f}s | Processamento: {elapsed:.1f}s", flush=True)
    return fid, True, None


def enrich_and_merge(
    call_id: str,
    metadata: Dict[str, Dict[str, str]],
    *,
    llm_model: str,
    llm_workers: int,
) -> None:
    import time
    start_time = time.time()
    print(f"[LLM-INICIO] {call_id} - Preparando chamada para análise LLM...", flush=True)

    prepared = g.prepare_calls([call_id], metadata)
    print(f"[LLM-ENVIANDO] {call_id} - Enviando para {llm_model}...", flush=True)

    per_call_details, successes, failures = g.run_llm_pipeline(prepared, model=llm_model, workers=llm_workers, quiet=True)
    if failures:
        print(f"[ENRICH-FAIL] {call_id}: {failures}", file=sys.stderr, flush=True)
    if not per_call_details:
        return
    detail = per_call_details[0]

    print(f"[LLM-MERGE] {call_id} - Mesclando resultados...", flush=True)
    engine_file = ENGINE_DIR / "full_analysis.json"
    frontend_file = ENGINE_DIR.parent / "public" / "data" / "full_analysis.json"
    try:
        existing = json.loads(engine_file.read_text())
    except FileNotFoundError:
        existing = {"dataset_summary": {}, "status_analysis": {}, "divergence_summary": {}, "per_call_details": []}

    index = {item.get("call_id"): item for item in existing.get("per_call_details") or []}
    index[call_id] = detail
    merged_calls = list(index.values())

    dataset_summary = g.compute_dataset_summary(merged_calls)
    dataset_summary["recurrence_summary"] = g.compute_recurrence_summary(merged_calls)
    status_analysis = g.compute_status_analysis(merged_calls)
    divergence_summary = g.compute_divergence_summary(merged_calls, dataset_summary)

    out = {
        "dataset_summary": dataset_summary,
        "status_analysis": status_analysis,
        "divergence_summary": divergence_summary,
        "per_call_details": merged_calls,
    }
    engine_file.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    frontend_file.parent.mkdir(parents=True, exist_ok=True)
    frontend_file.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    elapsed = time.time() - start_time
    print(f"[ENRICH-OK] {call_id} - LLM concluído em {elapsed:.1f}s", flush=True)


async def run_batch(
    targets: List[Tuple[str, Path, Path]],
    api_url: str,
    bearer: str | None,
    concurrency: int,
    timeout: float,
    language: str,
    provider: str,
    *,
    enable_diarization: bool,
    use_openai_diarization: bool,
    num_speakers: int,
    compute_type: str,
    beam_size: int,
    enrich: bool,
    llm_model: str,
    llm_workers: int,
) -> Tuple[int, List[Tuple[str, str]]]:
    import time
    from datetime import datetime

    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    errors: List[Tuple[str, str]] = []
    semaphore = asyncio.Semaphore(max(1, concurrency))
    metadata_cache = g.load_metadata(DEFAULT_METADATA) if enrich else {}

    completed = 0
    total = len(targets)
    start_batch_time = time.time()

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), headers=headers) as client:
        async def worker(fid: str, audio_path: Path, output_path: Path) -> None:
            nonlocal completed
            try:
                await transcribe_one(
                    client,
                    api_url,
                    fid,
                    audio_path,
                    output_path,
                    language,
                    provider,
                    enable_diarization=enable_diarization,
                    use_openai_diarization=use_openai_diarization,
                    num_speakers=num_speakers,
                    compute_type=compute_type,
                    beam_size=beam_size,
                )
                if enrich:
                    enrich_and_merge(
                        fid,
                        metadata_cache,
                        llm_model=llm_model,
                        llm_workers=llm_workers,
                    )

                completed += 1
                elapsed = time.time() - start_batch_time
                avg_per_file = elapsed / completed
                eta_seconds = avg_per_file * (total - completed)
                eta_str = f"{int(eta_seconds//3600)}h{int((eta_seconds%3600)//60)}m" if eta_seconds > 0 else "0m"
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] ✅ {completed}/{total} concluído | ETA: {eta_str} | Média: {avg_per_file:.1f}s/arquivo", flush=True)

            except Exception as exc:  # pragma: no cover - network/remote failures
                msg = repr(exc)
                errors.append((fid, msg))
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] ❌ FALHA {fid}: {msg}", file=sys.stderr, flush=True)

        tasks = [worker(fid, audio, out) for fid, audio, out in targets]
        await asyncio.gather(*tasks)
    return len(targets) - len(errors), errors


def main() -> None:
    args = parse_args()
    ids = args.only_ids if args.only_ids else read_metadata_ids(args.metadata)
    targets = pending_targets(ids, args.audio_dir, args.output_dir, args.limit)
    print(f"Alvos: {len(targets)} | Concurrency: {args.concurrency} | API: {args.api_url}")
    if not targets:
        print("Nada a fazer.")
        return
    successes, errors = asyncio.run(
        run_batch(
            targets,
            api_url=args.api_url,
            bearer=args.bearer,
            concurrency=args.concurrency,
            timeout=args.timeout,
            language=args.language,
            provider=args.provider,
            enable_diarization=args.enable_diarization,
            use_openai_diarization=args.use_openai_diarization,
            num_speakers=args.num_speakers,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            enrich=args.enrich,
            llm_model=args.llm_model,
            llm_workers=args.llm_workers,
        )
    )
    print(f"Concluído: {successes}/{len(targets)} com {len(errors)} falha(s)")
    if errors:
        for fid, msg in errors[:20]:
            print(f"- {fid}: {msg}", file=sys.stderr)


if __name__ == "__main__":
    main()
