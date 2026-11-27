import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type IntakeQuestion } from '../api';

type Step = 'lang' | 'notice' | 'questions' | 'upload' | 'done';

interface UploadRow {
  name: string;
  status: 'uploading' | 'done' | 'error';
  count: number;
}

export function KioskPage() {
  const nav = useNavigate();
  const [step, setStep] = useState<Step>('lang');
  const [lang, setLang] = useState<'hi' | 'en'>('hi');
  const [patientId, setPatientId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<IntakeQuestion[]>([]);
  const [qIdx, setQIdx] = useState(0);

  const [draftVal, setDraftVal] = useState<unknown>('');
  const [details, setDetails] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [uploads, setUploads] = useState<UploadRow[]>([]);

  useEffect(() => {
    if (step === 'questions') {
      api.getQuestions(lang).then(setQuestions);
    }
  }, [step, lang]);

  const startSession = async (chosenLang: 'hi' | 'en') => {
    setLang(chosenLang);
    const p = await api.createPatient({
      display_name: chosenLang === 'hi' ? 'मरीज़ (Demo)' : 'Patient (Demo)',
      age: 58,
      language: chosenLang,
    });
    setPatientId(p.id);
    setStep('notice');
  };

  const currentQ = questions[qIdx];

  const resetDraftForNext = (nextIdx: number) => {
    const nextQ = questions[nextIdx];
    if (!nextQ) return;
    if (nextQ.type === 'multi_choice' || nextQ.type === 'meds_multi') {
      setDraftVal([]);
    } else {
      setDraftVal('');
    }
    setDetails('');
    setConfirming(false);
  };

  const handleConfirmSave = async () => {
    if (!patientId || !currentQ) return;
    await api.upsertAnswer(patientId, {
      question_id: currentQ.id,
      value: draftVal,
      raw_text: details || null,
      confirmed: true,
    });

    if (qIdx + 1 < questions.length) {
      const next = qIdx + 1;
      setQIdx(next);
      resetDraftForNext(next);
    } else {
      setStep('upload');
    }
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || !patientId) return;
    for (const file of Array.from(files)) {
      setUploads((u) => [...u, { name: file.name, status: 'uploading', count: 0 }]);
      try {
        const res = await api.uploadDocument(patientId, file);
        const total = res.observations.length + res.medications.length;
        setUploads((u) =>
          u.map((row) =>
            row.name === file.name ? { ...row, status: 'done', count: total } : row,
          ),
        );
      } catch {
        setUploads((u) =>
          u.map((row) =>
            row.name === file.name ? { ...row, status: 'error', count: 0 } : row,
          ),
        );
      }
    }
  };

  const toggleMulti = (val: string) => {
    const arr = Array.isArray(draftVal) ? (draftVal as string[]) : [];
    if (val === 'none') {
      setDraftVal(['none']);
      return;
    }
    const filtered = arr.filter((x) => x !== 'none');
    if (filtered.includes(val)) {
      setDraftVal(filtered.filter((x) => x !== val));
    } else {
      setDraftVal([...filtered, val]);
    }
  };

  const toggleMed = (medName: string) => {
    const arr = Array.isArray(draftVal)
      ? (draftVal as Array<{ name: string; frequency: string }>)
      : [];
    if (arr.some((m) => m.name === medName)) {
      setDraftVal(arr.filter((m) => m.name !== medName));
    } else {
      setDraftVal([...arr, { name: medName, frequency: '1-0-1' }]);
    }
  };

  return (
    <main className="kiosk-wrap">
      {step === 'lang' && (
        <section className="kiosk-card">
          <h1>MediKiosk-DM</h1>
          <p className="muted">Choose your language / भाषा चुनें</p>
          <div className="kiosk-btn-col">
            <button className="btn-kiosk-big" onClick={() => startSession('hi')}>
              हिन्दी
            </button>
            <button className="btn-doc-big" onClick={() => startSession('en')}>
              English
            </button>
          </div>
        </section>
      )}

      {step === 'notice' && (
        <section className="kiosk-card">
          <h2>{lang === 'hi' ? 'जरूरी जानकारी' : 'Before we begin'}</h2>
          <p className="kiosk-prompt">
            {lang === 'hi'
              ? 'यह नकली (डेमो) डेटा वाला सिस्टम है। आपके जवाब आपके डॉक्टर को दिखाए जाएँगे।'
              : 'This is a demo with made-up data. Your doctor will see your answers.'}
          </p>
          <button
            className="btn-kiosk-big"
            onClick={() => {
              setStep('questions');
            }}
          >
            {lang === 'hi' ? 'आगे बढ़ें' : 'Continue'}
          </button>
        </section>
      )}

      {step === 'questions' && currentQ && (
        <section className="kiosk-card">
          <div className="muted small">
            {qIdx + 1} / {questions.length}
          </div>
          <h2 className="kiosk-prompt">{currentQ.text}</h2>

          {!confirming ? (
            <>
              {(currentQ.type === 'number' || currentQ.type === 'text') && (
                <input
                  className="kiosk-input"
                  type={currentQ.type === 'number' ? 'number' : 'text'}
                  value={String(draftVal ?? '')}
                  onChange={(e) => setDraftVal(e.target.value)}
                  placeholder={lang === 'hi' ? 'यहाँ लिखें…' : 'Type here…'}
                />
              )}

              {(currentQ.type === 'single_choice' || currentQ.type === 'yes_no') && (
                <div className="chip-grid">
                  {currentQ.options?.map((opt) => (
                    <button
                      key={opt.value}
                      className={`kiosk-chip ${draftVal === opt.value ? 'selected' : ''}`}
                      onClick={() => setDraftVal(opt.value)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}

              {currentQ.type === 'multi_choice' && (
                <div className="chip-grid">
                  {currentQ.options?.map((opt) => {
                    const selected = Array.isArray(draftVal) && (draftVal as string[]).includes(opt.value);
                    return (
                      <button
                        key={opt.value}
                        className={`kiosk-chip ${selected ? 'selected' : ''}`}
                        onClick={() => toggleMulti(opt.value)}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              )}

              {currentQ.type === 'meds_multi' && (
                <div className="chip-grid">
                  {currentQ.options?.map((opt) => {
                    const arr = Array.isArray(draftVal)
                      ? (draftVal as Array<{ name: string; frequency: string }>)
                      : [];
                    const selected = arr.some((m) => m.name === opt.value);
                    return (
                      <button
                        key={opt.value}
                        className={`kiosk-chip ${selected ? 'selected' : ''}`}
                        onClick={() => toggleMed(opt.value)}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              )}

              {currentQ.allow_details && (
                <textarea
                  className="kiosk-input"
                  rows={2}
                  value={details}
                  onChange={(e) => setDetails(e.target.value)}
                  placeholder={lang === 'hi' ? 'अतिरिक्त जानकारी (वैकल्पिक)…' : 'Optional details…'}
                />
              )}

              <button className="btn-kiosk-big" onClick={() => setConfirming(true)}>
                {lang === 'hi' ? 'आगे' : 'Next'}
              </button>
            </>
          ) : (
            <div className="confirm-box">
              <strong>{lang === 'hi' ? 'हमने यह समझा:' : 'What we understood:'}</strong>
              <p className="confirm-val">{JSON.stringify(draftVal)}</p>
              {details && <p className="muted">{details}</p>}
              <div className="confirm-actions">
                <button className="btn-primary" onClick={handleConfirmSave}>
                  {lang === 'hi' ? 'सही है' : 'Correct'}
                </button>
                <button className="btn-secondary" onClick={() => setConfirming(false)}>
                  {lang === 'hi' ? 'बदलें' : 'Change'}
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {step === 'upload' && (
        <section className="kiosk-card">
          <h2>{lang === 'hi' ? 'पुरानी रिपोर्ट और पर्चे अपलोड करें' : 'Upload old reports & prescriptions'}</h2>
          <input
            type="file"
            accept="image/*,application/pdf"
            capture="environment"
            multiple
            onChange={(e) => handleFiles(e.target.files)}
          />
          <div className="upload-list">
            {uploads.map((u, idx) => (
              <div key={idx} className="upload-row">
                <span>{u.name}</span>
                <span>
                  {u.status === 'uploading' && 'Reading…'}
                  {u.status === 'done' && `Read ${u.count} values`}
                  {u.status === 'error' && 'Could not read, staff will check'}
                </span>
              </div>
            ))}
          </div>
          <button className="btn-kiosk-big" onClick={() => setStep('done')}>
            {lang === 'hi' ? 'पूरा हुआ' : 'Finish'}
          </button>
        </section>
      )}

      {step === 'done' && (
        <section className="kiosk-card">
          <h2>{lang === 'hi' ? 'धन्यवाद!' : 'Thank you!'}</h2>
          <p className="kiosk-prompt">
            {lang === 'hi'
              ? 'कृपया अपनी बारी की प्रतीक्षा करें। आपके डॉक्टर को यह जानकारी मिल जाएगी।'
              : 'Please wait to be called. Your doctor will see this.'}
          </p>
          {patientId && (
            <button className="btn-doc-big" onClick={() => nav(`/doctor/${patientId}`)}>
              Open Doctor Dashboard →
            </button>
          )}
        </section>
      )}
    </main>
  );
}
