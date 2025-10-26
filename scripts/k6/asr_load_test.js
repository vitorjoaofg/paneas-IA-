import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const asrLatency = new Trend('asr_latency_ms');

export const options = {
  stages: [
    { duration: '2m', target: 20 },
    { duration: '5m', target: 50 },
    { duration: '2m', target: 100 },
    { duration: '3m', target: 50 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<1800'],
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.05'],
  },
};

const API_BASE = __ENV.API_BASE || 'http://localhost:8000';
const API_TOKEN = __ENV.API_TOKEN || 'token_abc123';
const AUDIO_PATH = __ENV.AUDIO_PATH || '/test-data/sample_10s.wav';

export default function () {
  const audio = open(AUDIO_PATH, 'b');

  const payload = {
    file: http.file(audio, 'sample.wav'),
    language: 'pt',
    model: 'whisper/medium',
    enable_diarization: false,
    enable_alignment: false,
  };

  const params = {
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
    },
  };

  const startTime = Date.now();
  const res = http.post(`${API_BASE}/api/v1/asr`, payload, params);
  const endTime = Date.now();

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'has text field': (r) => JSON.parse(r.body).text !== undefined,
    'processing time acceptable': (r) => {
      const body = JSON.parse(r.body);
      return body.processing_time_ms < 2000;
    },
  });

  errorRate.add(!success);
  asrLatency.add(endTime - startTime);

  sleep(1);
}
