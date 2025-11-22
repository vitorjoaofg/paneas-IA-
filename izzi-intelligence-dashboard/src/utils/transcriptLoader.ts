import type { TranscriptSegment } from "../types";

type RawSegment = {
  id?: number;
  start?: number | string;
  end?: number | string;
  text?: string;
  speaker?: string;
  role?: string;
};

type AnnotatedSegment = {
  segment_index?: number;
  role?: string;
};

const transcriptCache = new Map<string, TranscriptSegment[]>();
const transcriptPromises = new Map<string, Promise<TranscriptSegment[]>>();
const BASE_URL = (import.meta.env.BASE_URL ?? "/").replace(/\/+$/, "/");

function buildUrl(path: string): string {
  return `${BASE_URL}${path.replace(/^\/+/, "")}`;
}

function normalizeSegment(segment: RawSegment, index: number, overrides: Map<number, string>): TranscriptSegment {
  const start = Number(segment.start ?? 0) || 0;
  const end = Number(segment.end ?? segment.start ?? 0) || start;
  const baseSpeaker = (segment.speaker ?? segment.role ?? "customer").toLowerCase();
  const speaker = overrides.get(index) ?? baseSpeaker;
  return {
    id: typeof segment.id === "number" ? segment.id : index,
    start,
    end,
    text: String(segment.text ?? "").trim(),
    speaker,
  };
}

async function fetchOverrides(callId: string): Promise<Map<number, string>> {
  const overrides = new Map<number, string>();
  const url = buildUrl(`engine/diarization/output/${callId}.annotated.json`);
  try {
    const resp = await fetch(url);
    if (!resp.ok) return overrides;
    const payload = (await resp.json()) as { segments?: AnnotatedSegment[] };
    if (!Array.isArray(payload?.segments)) return overrides;
    payload.segments.forEach((item) => {
      if (typeof item?.segment_index === "number" && typeof item?.role === "string") {
        overrides.set(item.segment_index, item.role.toLowerCase());
      }
    });
  } catch (error) {
    console.warn("Falha ao carregar anotação de diarização", callId, error);
  }
  return overrides;
}

async function fetchTranscript(callId: string): Promise<TranscriptSegment[]> {
  const cached = transcriptCache.get(callId);
  if (cached) return cached;

  const pending = transcriptPromises.get(callId);
  if (pending) return pending;

  const promise = (async () => {
    try {
      const url = buildUrl(`engine/${callId}.json`);
      const resp = await fetch(url);
      if (!resp.ok) {
        transcriptCache.set(callId, []);
        return [] as TranscriptSegment[];
      }
      const payload = (await resp.json()) as { segments?: RawSegment[] };
      const segmentsRaw = Array.isArray(payload?.segments) ? payload.segments : [];
      if (segmentsRaw.length === 0) {
        transcriptCache.set(callId, []);
        return [] as TranscriptSegment[];
      }

      const overrides = await fetchOverrides(callId);

      const normalized = segmentsRaw.map((segment, index) => normalizeSegment(segment, index, overrides));
      transcriptCache.set(callId, normalized);
      return normalized;
    } catch (error) {
      console.error("Falha ao carregar transcrição", callId, error);
      transcriptCache.set(callId, []);
      return [] as TranscriptSegment[];
    }
  })();

  transcriptPromises.set(callId, promise);
  const result = await promise;
  transcriptPromises.delete(callId);
  return result;
}

export function getCachedTranscript(callId: string): TranscriptSegment[] | undefined {
  return transcriptCache.get(callId);
}

export async function loadTranscript(callId: string): Promise<TranscriptSegment[]> {
  return fetchTranscript(callId);
}

export async function preloadTranscripts(callIds: string[]): Promise<void> {
  for (const id of callIds) {
    await fetchTranscript(id);
  }
}

export function getTranscriptCacheSize(): number {
  return transcriptCache.size;
}

export function clearTranscriptCache(): void {
  transcriptCache.clear();
  transcriptPromises.clear();
}
