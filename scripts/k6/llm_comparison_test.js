import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const fp16Latency = new Trend('llm_fp16_latency_ms');
const int4Latency = new Trend('llm_int4_latency_ms');

export const options = {
  scenarios: {
    fp16_test: {
      executor: 'constant-vus',
      vus: 20,
      duration: '5m',
      exec: 'testFP16',
    },
    int4_test: {
      executor: 'constant-vus',
      vus: 20,
      duration: '5m',
      exec: 'testINT4',
    },
  },
};

const API_BASE = __ENV.API_BASE || 'http://localhost:8000';
const API_TOKEN = __ENV.API_TOKEN || 'token_abc123';

const testPrompts = [
  'Resuma o seguinte texto em 3 parágrafos...',
  'Analise o sentimento desta transcrição...',
  'Extraia as informações principais sobre...',
];

function callLLM(model) {
  const payload = JSON.stringify({
    model,
    messages: [
      { role: 'system', content: 'Você é um assistente útil.' },
      { role: 'user', content: testPrompts[Math.floor(Math.random() * testPrompts.length)] },
    ],
    max_tokens: 300,
    temperature: 0.7,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_TOKEN}`,
    },
  };

  const startTime = Date.now();
  const res = http.post(`${API_BASE}/api/v1/chat/completions`, payload, params);
  const latency = Date.now() - startTime;

  check(res, {
    [`${model} status 200`]: (r) => r.status === 200,
  });

  return latency;
}

export function testFP16() {
  const latency = callLLM('qwen2.5-14b-instruct');
  fp16Latency.add(latency);
}

export function testINT4() {
  const latency = callLLM('qwen2.5-14b-instruct-awq');
  int4Latency.add(latency);
}
