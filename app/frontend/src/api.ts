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

export interface Observation {
  id: number;
  patient_id: number;
  document_id: number;
  page_id: number;
  block_id: number | null;
  page_no?: number;
  source_org?: string | null;
  bbox?: BBox | null;
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

export interface Medication {
  id: number;
  patient_id: number;
  source: string;
  document_id: number | null;
  page_id: number | null;
  block_id: number | null;
  page_no?: number;
  source_org?: string | null;
  bbox?: BBox | null;
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

export interface RuleResult {
  rule_id: string;
  name: string;
  question: string;
  status: 'ok' | 'flag' | 'missing' | 'check' | 'note';
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

export interface PatientSummary {
  disclaimer: string;
  patient: Patient;
  latest_results: Observation[];
  medications: Medication[];
  rules: RuleResult[];
  answers: IntakeAnswer[];
  unanswered_questions: string[];
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
  type: string;
  options?: QuestionOption[];
  frequencies?: string[];
  unit_hi?: string;
  unit_en?: string;
  allow_details?: boolean;
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`${res.status}: ${txt}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listPatients: () => req<Patient[]>('/api/patients'),
  createPatient: (body: { display_name: string; age: number; language: string }) =>
    req<Patient>('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  seedDemo: (mode: 'cached' | 'live' = 'cached') =>
    req<{ patient_id: number; display_name: string }>(`/api/demo/seed?mode=${mode}`, {
      method: 'POST',
    }),
  getQuestions: (lang: string) => req<IntakeQuestion[]>(`/api/intake/questions?lang=${lang}`),
  upsertAnswer: (
    patientId: number,
    body: { question_id: string; value: unknown; raw_text?: string | null; confirmed: boolean },
  ) =>
    req<IntakeAnswer>(`/api/patients/${patientId}/answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  uploadDocument: async (patientId: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return req<{
      document: { id: number; status: string; kind: string };
      observations: Observation[];
      medications: Medication[];
    }>(`/api/patients/${patientId}/documents`, {
      method: 'POST',
      body: fd,
    });
  },
  getSummary: (patientId: number) => req<PatientSummary>(`/api/patients/${patientId}/summary`),
  getTimeline: (patientId: number) => req<TimelineData>(`/api/patients/${patientId}/timeline`),
  patchObservation: (id: number, body: { edited_value?: string; verified_by_clinician?: boolean }) =>
    req<Observation>(`/api/observations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  patchMedication: (id: number, body: { edited_value?: string; verified_by_clinician?: boolean }) =>
    req<Medication>(`/api/medications/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  saveDoctorNote: (patientId: number, text: string) =>
    req(`/api/patients/${patientId}/note`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),
};
