import type { PerCallDetail } from "../types";

const MS_PER_DAY = 1000 * 60 * 60 * 24;
const RECURRENCE_WINDOW_DAYS = 7;
const RECURRENCE_WINDOW_MS = RECURRENCE_WINDOW_DAYS * MS_PER_DAY;
const FOLLOW_UP_THRESHOLD_DAYS = 5;
const FOLLOW_UP_THRESHOLD_MS = FOLLOW_UP_THRESHOLD_DAYS * MS_PER_DAY;
const NEGATIVE_SENTIMENT_THRESHOLD = 0.3;
const HIGH_RISK_SENTIMENT_THRESHOLD = 0;

export interface TimelineCall {
  row: PerCallDetail;
  date: Date;
}

export interface PhoneTimeline {
  phone: string;
  calls: TimelineCall[];
}

export interface WeekPoint {
  week: string;
  weekStart: Date;
  count: number;
}

export interface WeeklyFollowUpPoint extends WeekPoint {
  followUps: number;
  pending: number;
  improductive: number;
}

export interface ReincidenteClient {
  phone: string;
  totalCalls: number;
  firstDate: Date;
  lastDate: Date;
  recurrenceWindowEnd: Date | null;
  averageSentiment: number | null;
  currentDivergence: number;
  lastStatusReal: string | null;
  primaryIsland: string;
  followUpCommitted: boolean;
  hasNegativeSentiment: boolean;
  unresolvedComplaint: boolean;
  persistentComplaint: boolean;
}

export interface ReincidenciasResult {
  clients: ReincidenteClient[];
  totalPhones: number;
  recurrentCount: number;
  unresolvedComplaintCount: number;
  persistentComplaintCount: number;
  persistentComplaintPercent: number;
  islandStats: { island: string; recurrentCount: number; totalCount: number; percent: number }[];
  weeklySeries: WeekPoint[];
  angryRecurringCount: number;
  angryRecurringVariation: number;
  pitchInconsistentCount: number;
  scriptNeverAlignedCount: number;
  angryRecurringPhones: string[];
  pitchInconsistentPhones: string[];
  scriptNeverAlignedPhones: string[];
  unresolvedComplaintPhones: string[];
}

export interface FollowUpResult {
  totalFollowUps: number;
  pendingCases: number;
  pendingPercent: number;
  improductiveCases: number;
  improductivePercent: number;
  pendingPhones: string[];
  weeklySeries: WeeklyFollowUpPoint[];
}

export interface RiscoChurnDetail {
  phone: string;
  streakLength: number;
  streakStart: Date;
  streakEnd: Date;
  lastSentiment: number | null;
  primaryIsland: string;
}

export interface RiscoChurnResult {
  totalHighRisk: number;
  details: RiscoChurnDetail[];
}

export interface TempoResolucaoDetail {
  phone: string;
  firstDivergentDate: Date;
  resolutionDate: Date;
  diffDays: number;
}

export interface TempoResolucaoResult {
  averageDays: number | null;
  details: TempoResolucaoDetail[];
}

function safeTrim(value: string | null | undefined) {
  return typeof value === "string" ? value.trim() : "";
}

export function parseCallDate(raw: string | null): Date | null {
  if (!raw) return null;
  const [datePart, timePart = "00:00:00"] = raw.trim().split(" ");
  const [dayStr, monthStr, yearStr] = datePart.split(/[\\/]/);
  if (!dayStr || !monthStr || !yearStr) return null;
  const day = Number(dayStr);
  const month = Number(monthStr);
  const year = Number(yearStr);
  if (!Number.isFinite(day) || !Number.isFinite(month) || !Number.isFinite(year)) return null;
  const [hourStr = "0", minuteStr = "0", secondStr = "0"] = timePart.split(":");
  const hour = Number(hourStr);
  const minute = Number(minuteStr);
  const second = Number(secondStr);
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

export function buildPhoneTimelines(rows: PerCallDetail[]): PhoneTimeline[] {
  const byPhone = new Map<string, TimelineCall[]>();
  for (const row of rows) {
    const phone = safeTrim(row.phone_number);
    if (!phone) continue;
    const date = parseCallDate(row.call_datetime ?? null);
    if (!date) continue;
    if (!byPhone.has(phone)) {
      byPhone.set(phone, []);
    }
    byPhone.get(phone)!.push({ row, date });
  }

  const timelines: PhoneTimeline[] = [];
  for (const [phone, calls] of byPhone.entries()) {
    calls.sort((a, b) => a.date.getTime() - b.date.getTime());
    timelines.push({ phone, calls });
  }
  return timelines;
}

function getPrimaryIsland(calls: TimelineCall[]) {
  const counter = new Map<string, number>();
  for (const call of calls) {
    const key = safeTrim(call.row.island) || safeTrim(call.row.queue) || "Indefinido";
    counter.set(key, (counter.get(key) ?? 0) + 1);
  }
  let top = "Indefinido";
  let max = -1;
  for (const [key, value] of counter.entries()) {
    if (value > max) {
      top = key;
      max = value;
    }
  }
  return top;
}

function getWeekInfo(date: Date): { week: string; start: Date } {
  const target = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const dayNr = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dayNr);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((target.getTime() - yearStart.getTime()) / MS_PER_DAY + 1) / 7);
  const weekStart = new Date(target);
  const diff = weekStart.getUTCDay() || 7;
  weekStart.setUTCDate(weekStart.getUTCDate() - (diff - 1));
  weekStart.setUTCHours(0, 0, 0, 0);
  return {
    week: `${target.getUTCFullYear()}-W${String(weekNo).padStart(2, "0")}`,
    start: weekStart,
  };
}

function hasNegativeSentiment(calls: TimelineCall[]) {
  return calls.some((call) => typeof call.row.customer_sentiment_score === "number" && call.row.customer_sentiment_score < NEGATIVE_SENTIMENT_THRESHOLD);
}

function isPersistentComplaint(timeline: PhoneTimeline) {
  const { calls } = timeline;
  if (!calls.length) return false;
  const dialogo = calls.some((call) => safeTrim(call.row.status_real_detectado).toLowerCase() === "dialogo_conectado");
  if (!dialogo) return false;
  if (!hasNegativeSentiment(calls)) return false;
  return calls.every((call) => call.row.divergente === 1);
}

function computeRecurrentWindow(calls: TimelineCall[]) {
  if (calls.length < 3) return null;
  for (let startIndex = 0; startIndex < calls.length - 2; startIndex += 1) {
    let endIndex = startIndex;
    while (
      endIndex < calls.length &&
      calls[endIndex].date.getTime() - calls[startIndex].date.getTime() <= RECURRENCE_WINDOW_MS
    ) {
      endIndex += 1;
    }
    if (endIndex - startIndex >= 3) {
      return calls[endIndex - 1].date;
    }
  }
  return null;
}

function calculateAverageSentiment(calls: TimelineCall[]) {
  let sum = 0;
  let count = 0;
  for (const call of calls) {
    const value = call.row.customer_sentiment_score;
    if (typeof value === "number" && Number.isFinite(value)) {
      sum += value;
      count += 1;
    }
  }
  if (count === 0) return null;
  return sum / count;
}

function getAngryWeeklyVariation(map: Map<string, { phones: Set<string>; start: Date }>) {
  if (map.size === 0) {
    return 0;
  }
  const entries = Array.from(map.values()).sort((a, b) => a.start.getTime() - b.start.getTime());
  if (entries.length === 1) {
    return entries[0].phones.size;
  }
  const last = entries[entries.length - 1].phones.size;
  const previous = entries[entries.length - 2].phones.size;
  return last - previous;
}

export function getReincidencias(rows: PerCallDetail[], timelinesParam?: PhoneTimeline[]): ReincidenciasResult {
  const timelines = timelinesParam ?? buildPhoneTimelines(rows);
  const totalPhones = timelines.length;
  const clients: ReincidenteClient[] = [];
  const islandTracker = new Map<string, { total: Set<string>; recurrent: Set<string> }>();
  const weeklyMap = new Map<string, { count: number; start: Date }>();
  const unresolvedPhones = new Set<string>();
  const persistentPhones = new Set<string>();
  const dialogoPhones = new Set<string>();
  const angryPhones = new Set<string>();
  const angryWeeklyMap = new Map<string, { phones: Set<string>; start: Date }>();
  const pitchInconsistentPhones = new Set<string>();
  const scriptNeverAlignedPhones = new Set<string>();

  for (const row of rows) {
    const phone = safeTrim(row.phone_number);
    if (!phone) continue;
    if (safeTrim(row.status_real_detectado).toLowerCase() === "dialogo_conectado") {
      dialogoPhones.add(phone);
    }
  }

  for (const timeline of timelines) {
    const { phone, calls } = timeline;
    const primaryIsland = getPrimaryIsland(calls);
    if (!islandTracker.has(primaryIsland)) {
      islandTracker.set(primaryIsland, { total: new Set<string>(), recurrent: new Set<string>() });
    }
    islandTracker.get(primaryIsland)!.total.add(phone);

    const recurrenceWindowEnd = computeRecurrentWindow(calls);
    const averageSentiment = calculateAverageSentiment(calls);
    const hasNegative = hasNegativeSentiment(calls);
    const angerCount = calls.filter((call) => call.row.customer_anger_detected === 1).length;
    if (angerCount >= 2) {
      angryPhones.add(phone);
    }
    for (const call of calls) {
      if (call.row.customer_anger_detected === 1) {
        const info = getWeekInfo(call.date);
        if (!angryWeeklyMap.has(info.week)) {
          angryWeeklyMap.set(info.week, { phones: new Set<string>(), start: info.start });
        }
        angryWeeklyMap.get(info.week)!.phones.add(phone);
      }
    }

    const pitchLabels = new Set(
      calls
        .map((call) => safeTrim(call.row.sales_pitch_label).toLowerCase())
        .filter((label) => label && label !== "unknown"),
    );
    if (pitchLabels.size > 1) {
      pitchInconsistentPhones.add(phone);
    }

    const neverAligned = calls.every((call) => safeTrim(call.row.script_alignment_label).toLowerCase() !== "aligned");
    if (neverAligned && recurrenceWindowEnd) {
      scriptNeverAlignedPhones.add(phone);
    }

    const persistent = isPersistentComplaint(timeline);
    if (persistent) {
      persistentPhones.add(phone);
    }

    if (!recurrenceWindowEnd) {
      continue;
    }

    islandTracker.get(primaryIsland)!.recurrent.add(phone);
    const { week, start } = getWeekInfo(recurrenceWindowEnd);
    if (!weeklyMap.has(week)) {
      weeklyMap.set(week, { count: 0, start });
    }
    weeklyMap.get(week)!.count += 1;

    const lastCall = calls[calls.length - 1];
    if (lastCall.row.divergente === 1 && hasNegative) {
      unresolvedPhones.add(phone);
    }

    clients.push({
      phone,
      totalCalls: calls.length,
      firstDate: calls[0].date,
      lastDate: lastCall.date,
      recurrenceWindowEnd,
      averageSentiment,
      currentDivergence: lastCall.row.divergente,
      lastStatusReal: lastCall.row.status_real_detectado,
      primaryIsland,
      followUpCommitted: calls.some((call) => call.row.follow_up_commitment === 1),
      hasNegativeSentiment: hasNegative,
      unresolvedComplaint: unresolvedPhones.has(phone),
      persistentComplaint: persistent,
    });
  }

  clients.sort((a, b) => b.lastDate.getTime() - a.lastDate.getTime());

  const islandStats = Array.from(islandTracker.entries()).map(([island, value]) => {
    const recurrentCount = value.recurrent.size;
    const totalCount = value.total.size;
    return {
      island,
      recurrentCount,
      totalCount,
      percent: totalCount ? recurrentCount / totalCount : 0,
    };
  });

  islandStats.sort((a, b) => b.recurrentCount - a.recurrentCount);

  const weeklySeries = Array.from(weeklyMap.entries())
    .map(([week, entry]) => ({
      week,
      weekStart: entry.start,
      count: entry.count,
    }))
    .sort((a, b) => a.weekStart.getTime() - b.weekStart.getTime());

  const angryRecurringVariation = getAngryWeeklyVariation(angryWeeklyMap);

  const persistentComplaintPercent = dialogoPhones.size
    ? persistentPhones.size / dialogoPhones.size
    : 0;

  return {
    clients,
    totalPhones,
    recurrentCount: clients.length,
    unresolvedComplaintCount: unresolvedPhones.size,
    persistentComplaintCount: persistentPhones.size,
    persistentComplaintPercent,
    islandStats,
    weeklySeries,
    angryRecurringCount: angryPhones.size,
    angryRecurringVariation,
    pitchInconsistentCount: pitchInconsistentPhones.size,
    scriptNeverAlignedCount: scriptNeverAlignedPhones.size,
    angryRecurringPhones: Array.from(angryPhones),
    pitchInconsistentPhones: Array.from(pitchInconsistentPhones),
    scriptNeverAlignedPhones: Array.from(scriptNeverAlignedPhones),
    unresolvedComplaintPhones: Array.from(unresolvedPhones),
  };
}

export function getFollowUpPendente(rows: PerCallDetail[], timelinesParam?: PhoneTimeline[]): FollowUpResult {
  const timelines = timelinesParam ?? buildPhoneTimelines(rows);
  let totalFollowUps = 0;
  let pendingCases = 0;
  let improductiveCases = 0;
  const pendingPhones = new Set<string>();
  const weeklyMap = new Map<string, { followUps: number; pending: number; improductive: number; start: Date }>();

  for (const timeline of timelines) {
    const { phone, calls } = timeline;
    for (let index = 0; index < calls.length; index += 1) {
      const call = calls[index];
      if (call.row.follow_up_commitment !== 1) continue;
      totalFollowUps += 1;
      const followUpDate = call.date;
      const { week, start } = getWeekInfo(followUpDate);
      if (!weeklyMap.has(week)) {
        weeklyMap.set(week, { followUps: 0, pending: 0, improductive: 0, start });
      }
      const entry = weeklyMap.get(week)!;
      entry.followUps += 1;

      let resolved = false;
      let improductive = false;

      for (let nextIndex = index + 1; nextIndex < calls.length; nextIndex += 1) {
        const nextCall = calls[nextIndex];
        const diff = nextCall.date.getTime() - followUpDate.getTime();
        if (diff < 0) continue;
        if (diff <= FOLLOW_UP_THRESHOLD_MS) {
          improductive = true;
        }
        if (nextCall.row.divergente === 0) {
          resolved = true;
          break;
        }
      }

      if (!resolved) {
        pendingCases += 1;
        pendingPhones.add(phone);
        entry.pending += 1;
      }

      if (improductive) {
        improductiveCases += 1;
        entry.improductive += 1;
      }
    }
  }

  const weeklySeries = Array.from(weeklyMap.entries())
    .map(([week, value]) => ({
      week,
      weekStart: value.start,
      count: value.pending,
      followUps: value.followUps,
      pending: value.pending,
      improductive: value.improductive,
    }))
    .sort((a, b) => a.weekStart.getTime() - b.weekStart.getTime());

  return {
    totalFollowUps,
    pendingCases,
    pendingPercent: totalFollowUps ? pendingCases / totalFollowUps : 0,
    improductiveCases,
    improductivePercent: totalFollowUps ? improductiveCases / totalFollowUps : 0,
    pendingPhones: Array.from(pendingPhones),
    weeklySeries,
  };
}

export function getRiscoChurn(rows: PerCallDetail[], timelinesParam?: PhoneTimeline[]): RiscoChurnResult {
  const timelines = timelinesParam ?? buildPhoneTimelines(rows);
  const details: RiscoChurnDetail[] = [];

  for (const timeline of timelines) {
    const { phone, calls } = timeline;
    let streak = 0;
    let bestStreak = 0;
    let bestStartIndex = -1;
    let currentStartIndex = -1;

    for (let index = 0; index < calls.length; index += 1) {
      const score = calls[index].row.customer_sentiment_score;
      if (typeof score === "number" && score < HIGH_RISK_SENTIMENT_THRESHOLD) {
        if (streak === 0) {
          currentStartIndex = index;
        }
        streak += 1;
        if (streak > bestStreak) {
          bestStreak = streak;
          bestStartIndex = currentStartIndex;
        }
      } else {
        streak = 0;
        currentStartIndex = -1;
      }
    }

    if (bestStreak >= 3 && bestStartIndex >= 0) {
      const startCall = calls[bestStartIndex];
      const endCall = calls[bestStartIndex + bestStreak - 1];
      const lastSentiment = endCall.row.customer_sentiment_score ?? null;
      const primaryIsland = getPrimaryIsland(calls);
      details.push({
        phone,
        streakLength: bestStreak,
        streakStart: startCall.date,
        streakEnd: endCall.date,
        lastSentiment,
        primaryIsland,
      });
    }
  }

  details.sort((a, b) => b.streakEnd.getTime() - a.streakEnd.getTime());

  return {
    totalHighRisk: details.length,
    details,
  };
}

export function getTempoResolucao(rows: PerCallDetail[], timelinesParam?: PhoneTimeline[]): TempoResolucaoResult {
  const timelines = timelinesParam ?? buildPhoneTimelines(rows);
  const details: TempoResolucaoDetail[] = [];

  for (const timeline of timelines) {
    const { phone, calls } = timeline;
    let firstDivergentDate: Date | null = null;
    for (const call of calls) {
      if (call.row.divergente === 1 && !firstDivergentDate) {
        firstDivergentDate = call.date;
      }
      if (firstDivergentDate && call.row.divergente === 0) {
        const diffDays = (call.date.getTime() - firstDivergentDate.getTime()) / MS_PER_DAY;
        if (diffDays >= 0) {
          details.push({
            phone,
            firstDivergentDate,
            resolutionDate: call.date,
            diffDays,
          });
        }
        break;
      }
    }
  }

  const averageDays =
    details.length > 0 ? details.reduce((sum, item) => sum + item.diffDays, 0) / details.length : null;

  return {
    averageDays,
    details,
  };
}
