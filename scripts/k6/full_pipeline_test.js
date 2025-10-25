import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const pipelineLatency = new Trend('pipeline_latency_ms');
const pipelineFailures = new Counter('pipeline_failures');

export const options = {
  scenarios: {
    steady_pipeline: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1m',
      preAllocatedVUs: 20,
      stages: [
        { target: 10, duration: '2m' },
        { target: 20, duration: '4m' },
        { target: 5, duration: '2m' },
      ],
    },
  },
  thresholds: {
    pipeline_latency_ms: ['p(95)<5000'],
    pipeline_failures: ['count<20'],
  },
};

const API_BASE = __ENV.API_BASE || 'http://localhost:8000';
const API_TOKEN = __ENV.API_TOKEN || 'token_abc123';
const AUDIO_PATH = __ENV.AUDIO_PATH || '/test-data/audio/sample_conversation.wav';
const PDF_PATH = __ENV.PDF_PATH || '/test-data/documents/sample_5pages.pdf';

export default function () {
  const headers = {
    Authorization: `Bearer ${API_TOKEN}`,
    'Content-Type': 'application/json',
  };

  const start = Date.now();

  try {
    group('asr', () => {
      const audio = open(AUDIO_PATH, 'b');
      const payload = {
        file: http.file(audio, 'conversation.wav', 'audio/wav'),
        language: 'pt',
        model: 'large-v3-turbo',
        enable_diarization: 'true',
        enable_alignment: 'true',
      };
      const res = http.post(`${API_BASE}/api/v1/asr`, payload, {
        headers: { Authorization: `Bearer ${API_TOKEN}` },
      });
      check(res, {
        'asr status 200': (r) => r.status === 200,
        'asr segments present': (r) => JSON.parse(r.body).segments?.length > 0,
      });
    });

    group('ocr', () => {
      const pdf = open(PDF_PATH, 'b');
      const payload = {
        file: http.file(pdf, 'sample.pdf', 'application/pdf'),
        languages: JSON.stringify(['pt']),
        use_gpu: 'true',
      };
      const res = http.post(`${API_BASE}/api/v1/ocr`, payload, {
        headers: { Authorization: `Bearer ${API_TOKEN}` },
      });
      check(res, {
        'ocr status 200': (r) => r.status === 200,
      });
    });

    group('llm', () => {
      const payload = JSON.stringify({
        model: 'qwen2.5-14b-instruct',
        messages: [
          { role: 'system', content: 'Você é um assistente útil.' },
          { role: 'user', content: 'Crie o resumo da transcrição e destaque 3 tópicos.' },
        ],
        max_tokens: 300,
      });
      const res = http.post(`${API_BASE}/api/v1/chat/completions`, payload, { headers });
      check(res, {
        'llm status 200': (r) => r.status === 200,
      });
    });

    group('analytics', () => {
      const payload = JSON.stringify({
        call_id: `call-${Date.now()}`,
        audio_uri: 's3://bucket/call_123.wav',
        transcript_uri: 's3://bucket/call_123.json',
        analysis_types: ['vad_advanced', 'prosody', 'emotion', 'keywords', 'summary'],
        keywords: ['contrato', 'pagamento', 'cancelamento'],
      });
      const res = http.post(`${API_BASE}/api/v1/analytics/speech`, payload, { headers });
      check(res, {
        'analytics accepted': (r) => r.status === 202,
      });
    });
  } catch (err) {
    pipelineFailures.add(1);
  } finally {
    const elapsed = Date.now() - start;
    pipelineLatency.add(elapsed);
  }

  sleep(1);
}
