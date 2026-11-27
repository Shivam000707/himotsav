export interface BBox {
  xmin: number;
  ymin: number;
  xmax: number;
  ymax: number;
}

export interface Patient {
  id: number;
  display_name: string;
  age: number;
  language: string;
  created_at: string;
}

/** Fields the backend attaches to every observation and medication so the source can be shown. */
interface SourceFields {
  page_no?: number;
  page_w?: number | null;
  page_h?: number | null;
  source_org?: string | null;
  source_mode?: 'ai' | 'scripted' | null;
  block_text?: string | null;
  bbox?: BBox | null;
}

export interface Observation extends SourceFields {
  id: number;
  patient_id: number;
  document_id: number;
  page_id: number;
  block_id: number | null;
  test: string;
  label_as_written: string;
  value_raw: string;
  unit_raw: string | null;
  value_num: number | null;
  unit_std: string | null;
  value_std: number | null;
  converted: boolean;
  obs_date: string | null;
  uncertain: boolean;
  unverified: boolean;
  note: string | null;
  verified_by_clinician: boolean;
  edited_value: string | null;
}

export interface Medication extends SourceFields {
  id: number;
  patient_id: number;
  source: 'rx' | 'intake';
  document_id: number | null;
  page_id: number | null;
  block_id: number | null;
  name_as_written: string;
  generic_name: string | null;
  strength: string | null;
  frequency: string | null;
  rx_date: string | null;
  uncertain: boolean;
  unverified: boolean;
  note: string | null;
  verified_by_clinician: boolean;
  edited_value: string | null;
  intake_status?: string;
}

export type RuleStatus = 'ok' | 'flag' | 'missing' | 'check' | 'note';

export interface RuleResult {
  rule_id: string;
  name: string;
  question: string;
  status: RuleStatus;
  evidence_text: string;
  evidence_refs: string[];
}

export interface IntakeAnswer {
  id: number;
  patient_id: number;
  question_id: string;
  value_json: string;
  raw_text: string | null;
  confirmed: boolean;
  answered_at: string;
}

export interface AnswerDisplay {
  question_id: string;
  topic: string;
  answer: string;
  patient_words: string | null;
}

export interface SummaryDocument {
  id: number;
  kind: string;
  source_org: string | null;
  doc_date: string | null;
  status: 'pending' | 'done' | 'failed';
  error: string | null;
  page_count: number;
  source_mode: 'ai' | 'scripted';
  original_filename: string | null;
  n_observations: number;
  n_medications: number;
}

export interface PatientSummary {
  disclaimer: string;
  today: string;
  patient: Patient;
  latest_results: Observation[];
  medications: Medication[];
  rules: RuleResult[];
  answers: IntakeAnswer[];
  answers_display: AnswerDisplay[];
  unanswered_questions: string[];
  unanswered_topics: string[];
  documents: SummaryDocument[];
  doctor_note: string;
}

export interface TimelineData {
  observations_by_test: Record<string, Observation[]>;
  medications: Medication[];
}

export interface QuestionOption {
  value: string;
  label: string;
}

export interface IntakeQuestion {
  id: string;
  topic: string;
  text: string;
  type: 'number' | 'text' | 'single_choice' | 'yes_no' | 'multi_choice' | 'meds_multi';
  options?: QuestionOption[];
  frequencies?: string[];
  unit_hi?: string;
  unit_en?: string;
  allow_details?: boolean;
}

export interface Health {
  ok: boolean;
  nvidia_key_present: boolean;
  asr_configured: boolean;
  asr_lang: string;
  models: { parse: string; text: string; vision: string };
  today: string;
  demo_today_set: boolean;
  public_demo?: boolean;
}

export interface SeedResult {
  patient_id: number;
  display_name: string;
  mode: string;
  documents_total: number;
  documents_failed: { paper: string; error: string }[];
}

export interface UploadResult {
  document: SummaryDocument & { id: number };
  observations: Observation[];
  medications: Medication[];
}

/** Error carrying the backend's own message (FastAPI's "detail"), so screens can show it. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Where the API lives. Empty in development (Vite proxies /api to port 8000). On Vercel, set VITE_API_BASE
 * to the backend's address, for example https://medikiosk-production.up.railway.app (no trailing slash).
 */
const API_BASE = ((import.meta.env.VITE_API_BASE as string | undefined) ?? '').replace(/\/+$/, '');
const CANNOT_REACH = API_BASE
  ? 'Cannot reach the backend. It may be starting up: wait a minute and try again.'
  : 'Cannot reach the backend. Is it running on port 8000?';

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${url}`, init);
  } catch {
    throw new ApiError(0, CANNOT_REACH);
  }
  if (!res.ok) {
    const txt = await res.text();
    let message = txt || res.statusText;
    try {
      const body = JSON.parse(txt);
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg?: string }) => d.msg).join('; ');
    } catch {
      /* not JSON: keep the text */
    }
    if (res.status === 502 || res.status === 503 || res.status === 504) message = CANNOT_REACH;
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req<Health>('/api/health'),
  listPatients: () => req<Patient[]>('/api/patients'),
  createPatient: (body: { display_name: string; age: number; language: string }) =>
    req<Patient>('/api/patients', json('POST', body)),
  seedDemo: (mode: 'live' | 'cached' | 'scripted') =>
    req<SeedResult>(`/api/demo/seed?mode=${mode}`, { method: 'POST' }),
  getQuestions: (lang: string) => req<IntakeQuestion[]>(`/api/intake/questions?lang=${lang}`),
  upsertAnswer: (
    patientId: number,
    body: { question_id: string; value: unknown; raw_text?: string | null; confirmed: boolean },
  ) => req<IntakeAnswer>(`/api/patients/${patientId}/answers`, json('POST', body)),
  uploadDocument: (patientId: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return req<UploadResult>(`/api/patients/${patientId}/documents`, { method: 'POST', body: fd });
  },
  getSummary: (patientId: number) => req<PatientSummary>(`/api/patients/${patientId}/summary`),
  getTimeline: (patientId: number) => req<TimelineData>(`/api/patients/${patientId}/timeline`),
  patchObservation: (id: number, body: { edited_value?: string; verified_by_clinician?: boolean }) =>
    req<Observation>(`/api/observations/${id}`, json('PATCH', body)),
  patchMedication: (id: number, body: { edited_value?: string; verified_by_clinician?: boolean }) =>
    req<Medication>(`/api/medications/${id}`, json('PATCH', body)),
  saveDoctorNote: (patientId: number, text: string) =>
    req<unknown>(`/api/patients/${patientId}/note`, json('PUT', { text })),
  transcribe: (wav: Blob, lang: string) => {
    const fd = new FormData();
    fd.append('file', wav, 'speech.wav');
    return req<{ text: string; fallback_needed: boolean; note: string | null }>(
      `/api/asr?lang=${encodeURIComponent(lang)}`,
      { method: 'POST', body: fd },
    );
  },
};

export function pageImageUrl(documentId: number, pageNo: number): string {
  return `${API_BASE}/api/documents/${documentId}/pages/${pageNo}/image`;
}
