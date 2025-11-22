# Diarização heurística

Este módulo gera anotações de papel (`agent`, `customer`, `ivr`) a partir das transcrições já existentes.  
Não há um modelo pesado de diarização de áudio aqui; aproveitamos o texto para reclassificar cada segmento com heurísticas
voltadas para espanhol (vocabulário típico de IVR/atendente).

## Estrutura

```
engine/diarization/
├── README.md
├── output/
│   └── <call_id>.annotated.json
└── run_diarization.py
```

## Uso

1. Gere as anotações para um `call_id`:

   ```bash
   python engine/diarization/run_diarization.py --call-id 0105-...
   ```

   Para processar todas as chamadas presentes em `engine/*.json`:

   ```bash
   python engine/diarization/run_diarization.py --all
   ```

2. O script cria `engine/diarization/output/<call_id>.annotated.json`.  
   O `generate_full_analysis_v3.py` utiliza automaticamente esse arquivo (quando presente) para recalcular
   métricas de talk-time e temas sem depender da LLM para corrigir papéis.

> Observação: se um `call_id` já possuía anotação e quiser refazer, basta executar o comando novamente.
> O arquivo será sobrescrito.

