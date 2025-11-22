#!/usr/bin/env python3
"""
Gera enriquecimento de uma chamada usando um LLM da OpenAI e atualiza o JSON do dashboard.

Uso:
    python engine/llm_enrichment.py --call-id 0105-... --model gpt-4o-mini
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from threading import Lock

import requests

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DEFAULT_MODEL = "gpt-4o"
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DASHBOARD_LOCK = Lock()


def load_transcript(call_id: str) -> Dict[str, Any]:
    path = BASE_DIR / f"{call_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Transcrição não encontrada: {path}")
    with path.open() as handle:
        return json.load(handle)


def build_conversation_prompt(segments: List[Dict[str, Any]]) -> str:
    lines = []
    for seg in segments:
        role = (seg.get("role") or "unknown").upper()
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = seg.get("start")
        if start is not None:
            lines.append(f"[{role} @ {start:.1f}s] {text}")
        else:
            lines.append(f"[{role}] {text}")
    return "\n".join(lines)


def call_openai(model: str, prompt: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {DEFAULT_API_KEY}",
        "Content-Type": "application/json",
    }
    system_prompt = (
        "Você é um analista de qualidade de chamadas. Receberá a transcrição completa "
        "com papéis originais (IVR, AGENT, CUSTOMER). Atenção: os papéis informados nos colchetes "
        "podem estar incorretos. Reclassifique cada fala usando apenas 'agent', 'customer' ou 'ivr', "
        "interpretando o conteúdo: quem oferece planos/descontos/procedimentos é o agente; quem relata problemas "
        "ou toma decisões é o cliente; mensagens robóticas são 'ivr'. Agrupe as falas prolongadas do mesmo interlocutor. "
        "Responda em JSON puro (sem texto adicional) com os campos abaixo:\n"
        "{\n"
        '  "status_real_detectado": <string - use snake_case consistente com engine>,\n'
        '  "customer_sentiment": {"label": "positive|neutral|negative", "score": <float -1..1>},\n'
        '  "agent_sentiment": {"label": "positive|neutral|negative", "score": <float -1..1>},\n'
        '  "script_followed": {"label": "aligned|partial|off_script", "confidence": <0..1>, "rationale": <string>},\n'
        '  "source_awareness": {"detected": <bool>, "level": <0..2>, "evidence": [<strings>]},\n'
        '  "follow_up": {"detected": <bool>, "actor": "agent|customer|null", "summary": <string>},\n'
        '  "objection_handling": {"handled": <bool>, "count": <int>, "notes": <string>},\n'
        '  "customer_anger": {"detected": <bool>, "quotes": [<strings>]},\n'
        '  "segment_corrections": [ {"index": <int>, "role": "agent|customer|ivr"} ] (use índices zero-based seguindo a ordem dos blocos enviados; inclua apenas quando precisar corrigir o papel original),\n'
        '  "speaker_corrections": [ {"role": "agent|customer|ivr", "text": "..."} ] (máximo 20 entradas, somente frases relevantes resumindo cada turno com o papel corrigido, ignorando interjeições ou repetições),\n'
        '  "timeline": [ {"role": "...", "text": "..."} ] (resuma blocos principais, máximo 20 entradas),\n'
        '  "notes": <string com observações adicionais>\n'
        "}\n"
        "Certifique-se de que o JSON é válido, completo e que a atribuição de papéis (segment_corrections) está correta."
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"OpenAI API falhou ({response.status_code}): {response.text}")
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Resposta malformada da OpenAI: {data}") from exc
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Falha ao decodificar JSON do modelo: {content}") from exc


def update_dashboard(call_id: str, enrichment: Dict[str, Any]) -> None:
    dashboard_path = PROJECT_DIR / "public" / "data" / "full_analysis.json"
    if not dashboard_path.exists():
        raise FileNotFoundError(f"JSON do frontend não encontrado: {dashboard_path}")
    with DASHBOARD_LOCK:
        with dashboard_path.open() as handle:
            dashboard = json.load(handle)

        try:
            entry = next(
                item for item in dashboard["per_call_details"] if item.get("call_id") == call_id
            )
        except StopIteration:
            raise KeyError(f"Call ID {call_id} não localizado em per_call_details.")

        def sentiment_to_pair(data: Dict[str, Any]) -> tuple[str, float]:
            label = (data.get("label") or "neutral").lower()
            score = float(data.get("score") or 0.0)
            return label, score

ALLOWED_STATUSES = {
    "dialogo_conectado",
    "cliente_interagiu_sem_agente",
    "conectado_sem_cliente",
    "ivr_sem_interacao",
    "buzon",
    "fax_ou_contestadora",
    "sem_audio",
    "numero_inexistente",
    "telefone_suspendido",
    "orden_aberta",
}


def apply_enrichment(entry: Dict[str, Any], enrichment: Dict[str, Any]) -> None:
    def sentiment_to_pair(data: Dict[str, Any]) -> tuple[str, float]:
        label = (data.get("label") or "neutral").lower()
        score = float(data.get("score") or 0.0)
        return label, score

    status_real = enrichment.get("status_real_detectado")
    if isinstance(status_real, str):
        entry["llm_status_raw"] = status_real
        normalized_status = (
            status_real.strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if normalized_status in ALLOWED_STATUSES:
            entry["status_real_detectado"] = normalized_status

    cust_label, cust_score = sentiment_to_pair(enrichment.get("customer_sentiment", {}))
    entry["customer_sentiment_label"] = cust_label
    entry["customer_sentiment_score"] = round(cust_score, 4)

    agent_label, agent_score = sentiment_to_pair(enrichment.get("agent_sentiment", {}))
    entry["agent_sentiment_label"] = agent_label
    entry["agent_sentiment_score"] = round(agent_score, 4)

    script_info = enrichment.get("script_followed", {})
    script_label = script_info.get("label")
    if script_label:
        entry["script_alignment_label"] = script_label
    confidence = script_info.get("confidence")
    if confidence is not None:
        entry["script_alignment_score"] = float(confidence)
    evidence = script_info.get("evidence")
    if isinstance(evidence, list):
        entry["script_keywords_matched"] = evidence
        entry["script_keyword_hits"] = len(evidence)
        entry["script_keyword_total"] = max(entry.get("script_keyword_total", 0), entry["script_keyword_hits"])

    source_info = enrichment.get("source_awareness", {})
    entry["operator_source_awareness"] = 1 if source_info.get("detected") else 0
    entry["operator_source_awareness_level"] = int(source_info.get("level") or 0)
    entry["operator_source_awareness_matches"] = source_info.get("evidence") or []

    follow_info = enrichment.get("follow_up", {})
    entry["follow_up_commitment"] = 1 if follow_info.get("detected") else 0
    entry["follow_up_actor"] = follow_info.get("actor")
    entry["follow_up_matches"] = [follow_info.get("summary")] if follow_info.get("summary") else entry.get("follow_up_matches", [])

    objection_info = enrichment.get("objection_handling", {})
    entry["objection_handled"] = 1 if objection_info.get("handled") else 0
    entry["objection_handled_count"] = int(objection_info.get("count") or 0)

    anger_info = enrichment.get("customer_anger", {})
    entry["customer_anger_detected"] = 1 if anger_info.get("detected") else 0
    entry["customer_anger_matches"] = anger_info.get("quotes") or []

    pitch_info = enrichment.get("sales_pitch") or {}
    if pitch_info.get("label"):
        entry["sales_pitch_label"] = pitch_info.get("label")
    if pitch_info.get("score") is not None:
        entry["sales_pitch_score"] = float(pitch_info.get("score") or 0.0)
    if isinstance(pitch_info.get("topics"), list):
        entry["sales_pitch_topics"] = pitch_info.get("topics")

    if "notes" in enrichment:
        entry["llm_notes"] = enrichment["notes"]

    agent_identity = enrichment.get("agent_identity") or {}
    if isinstance(agent_identity, dict):
        name = agent_identity.get("name")
        confidence = agent_identity.get("confidence")
        entry["agent_name_detected"] = name.strip() if isinstance(name, str) and name.strip() else None
        entry["agent_name_confidence"] = float(confidence) if confidence is not None else None
    customer_identity = enrichment.get("customer_identity") or {}
    if isinstance(customer_identity, dict):
        name = customer_identity.get("name")
        confidence = customer_identity.get("confidence")
        entry["customer_name_detected"] = name.strip() if isinstance(name, str) and name.strip() else None
        entry["customer_name_confidence"] = float(confidence) if confidence is not None else None

    entry.pop("llm_timeline", None)
    entry["llm_enrichment_source"] = "openai"
    segment_corrections = []
    raw_corrections = enrichment.get("segment_corrections")
    if isinstance(raw_corrections, list):
        for item in raw_corrections:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            role = (item.get("role") or "").strip().lower()
            if isinstance(idx, int) and role in {"agent", "customer", "ivr"}:
                segment_corrections.append({"index": idx, "role": role})
    if segment_corrections:
        entry["llm_segment_corrections"] = segment_corrections
    else:
        entry.pop("llm_segment_corrections", None)
    return segment_corrections


def update_dashboard(call_id: str, enrichment: Dict[str, Any]) -> None:
    dashboard_path = PROJECT_DIR / "public" / "data" / "full_analysis.json"
    if not dashboard_path.exists():
        raise FileNotFoundError(f"JSON do frontend não encontrado: {dashboard_path}")
    with DASHBOARD_LOCK:
        with dashboard_path.open() as handle:
            dashboard = json.load(handle)

        try:
            entry = next(
                item for item in dashboard["per_call_details"] if item.get("call_id") == call_id
            )
        except StopIteration:
            raise KeyError(f"Call ID {call_id} não localizado em per_call_details.")

        apply_enrichment(entry, enrichment)

        with dashboard_path.open("w") as handle:
            json.dump(dashboard, handle, ensure_ascii=False, indent=2)


def _process_call(target_id: str, model: str) -> tuple[str, bool, str]:
    try:
        transcript = load_transcript(target_id)
        segments = transcript.get("segments") or []
        if not segments:
            raise ValueError("Transcrição sem segmentos.")
        prompt = (
            "Transcrição completa (um turno por linha):\n"
            f"{build_conversation_prompt(segments)}\n\n"
            "Analise seguindo as instruções do sistema."
        )
        enrichment = call_openai(model, prompt)
        update_dashboard(target_id, enrichment)
        return target_id, True, ""
    except Exception as exc:  # pragma: no cover
        return target_id, False, str(exc)


def enrich_calls(
    call_ids: List[str],
    model: str = DEFAULT_MODEL,
    workers: int | None = None,
    verbose: bool = True,
) -> tuple[int, List[tuple[str, str]]]:
    unique_ids = sorted(set(call_ids))
    if not unique_ids:
        return 0, []

    max_workers = max(1, workers or (os.cpu_count() or 4))
    successes = 0
    failures: List[tuple[str, str]] = []

    if verbose:
        print(f"Iniciando enriquecimento de {len(unique_ids)} chamadas com {max_workers} thread(s) usando {model}...")

    if max_workers == 1:
        for cid in unique_ids:
            cid, ok, message = _process_call(cid, model)
            if ok:
                successes += 1
                if verbose:
                    print(f"[OK] {cid}")
            else:
                failures.append((cid, message))
                if verbose:
                    print(f"[ERRO] {cid}: {message}")
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_process_call, cid, model): cid for cid in unique_ids}
            for future in as_completed(futures):
                cid, ok, message = future.result()
                if ok:
                    successes += 1
                    if verbose:
                        print(f"[OK] {cid}")
                else:
                    failures.append((cid, message))
                    if verbose:
                        print(f"[ERRO] {cid}: {message}")

    if verbose:
        print(f"\nEnriquecimento finalizado. Sucesso: {successes} | Falhas: {len(failures)}")
        if failures:
            for cid, message in failures:
                print(f" - {cid}: {message}")
    return successes, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Enriquecimento de chamada via LLM OpenAI.")
    parser.add_argument("--call-id", action="append", help="ID da chamada a ser processada (pode repetir).")
    parser.add_argument("--all", action="store_true", help="Processar todas as chamadas disponíveis em engine/*.json.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo da OpenAI a ser utilizado.")
    parser.add_argument("--workers", type=int, default=None, help="Quantidade de threads paralelas.")
    args = parser.parse_args()

    call_ids: List[str] = []
    if args.all:
        call_ids = [
            fname.replace(".json", "")
            for fname in os.listdir(BASE_DIR)
            if fname.endswith(".json")
            and not fname.endswith(".analysis.json")
            and fname not in {"global_metrics.json", "full_analysis.json"}
        ]
    if args.call_id:
        call_ids.extend(args.call_id)
    if not call_ids:
        parser.error("Informe --all ou ao menos um --call-id.")

    try:
        enrich_calls(call_ids, model=args.model, workers=args.workers, verbose=True)
    except Exception as exc:  # pragma: no cover - utilização manual
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
