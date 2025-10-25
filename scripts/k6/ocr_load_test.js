import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const ocrLatency = new Trend('ocr_latency_ms');
const errorRate = new Rate('ocr_errors');

export const options = {
  stages: [
    { duration: '1m', target: 10 },
    { duration: '4m', target: 30 },
    { duration: '2m', target: 60 },
    { duration: '2m', target: 30 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<4000'],
    ocr_errors: ['rate<0.05'],
  },
};

const API_BASE = __ENV.API_BASE || 'http://localhost:8000';
const API_TOKEN = __ENV.API_TOKEN || 'token_abc123';
const PDF_PATH = __ENV.PDF_PATH || '/test-data/documents/sample_5pages.pdf';

export default function () {
  const pdf = open(PDF_PATH, 'b');

  const payload = {
    file: http.file(pdf, 'sample.pdf', 'application/pdf'),
    languages: JSON.stringify(['pt', 'en']),
    output_format: 'json',
    use_gpu: 'true',
  };

  const params = {
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
    },
  };

  const startTime = Date.now();
  const res = http.post(`${API_BASE}/api/v1/ocr`, payload, params);
  const latency = Date.now() - startTime;

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'returns pages': (r) => JSON.parse(r.body).pages?.length > 0,
  });

  ocrLatency.add(latency);
  errorRate.add(!ok);

  sleep(1);
}
