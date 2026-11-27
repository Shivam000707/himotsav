import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, type IntakeQuestion } from '../api';
import { Alert, Back, Camera, Check, Info, Logo } from '../components/icons';
import { VoiceInput } from '../components/VoiceInput';

type Step = 'lang' | 'notice' | 'questions' | 'upload' | 'done';
type Lang = 'hi' | 'en';
type MedPick = { name: string; frequency: string };

interface UploadRow {
  key: number;
  name: string;
  status: 'uploading' | 'done' | 'failed' | 'error';
  count: number;
  message?: string;
}

const FREQ_LABEL: Record<string, { hi: string; en: string }> = {
  '1-0-1': { hi: 'सुबह और रात', en: 'Morning and night' },
  '1-0-0': { hi: 'सिर्फ़ सुबह', en: 'Morning only' },
  '0-0-1': { hi: 'सिर्फ़ रात', en: 'Night only' },
  '1-1-1': { hi: 'दिन में 3 बार', en: '3 times a day' },
  '0-1-0': { hi: 'सिर्फ़ दोपहर', en: 'Afternoon only' },
};

function emptyValue(q: IntakeQuestion | undefined): unknown {
  return q && (q.type === 'multi_choice' || q.type === 'meds_multi') ? [] : '';
}

/** One tappable answer. Round mark for "pick one", square mark for "pick any". */
function Option({
  selected,
  multi,
  onClick,
  children,
}: {
  selected: boolean;
  multi: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role={multi ? 'checkbox' : 'radio'}
      aria-checked={selected}
      className={`opt ${selected ? 'on' : ''}`}
      onClick={onClick}
    >
      <span className={`opt-mark ${multi ? 'square' : 'round'}`} aria-hidden="true">
        {selected && <Check size={18} strokeWidth={3.2} />}
      </span>
      <span className="opt-label">{children}</span>
    </button>
  );
}

function ActionBar({ children }: { children: ReactNode }) {
  return (
    <div className="kiosk-bar">
      <div className="kiosk-bar-in">{children}</div>
    </div>
  );
}

export function KioskPage() {
  const [step, setStep] = useState<Step>('lang');
  const [lang, setLang] = useState<Lang>('hi');
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [patientId, setPatientId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<IntakeQuestion[]>([]);
  const [qIdx, setQIdx] = useState(0);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [details, setDetails] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [nvidiaAsr, setNvidiaAsr] = useState(false);
  const [publicDemo, setPublicDemo] = useState(false);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  const t = (hi: string, en: string) => (lang === 'hi' ? hi : en);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setNvidiaAsr(h.asr_configured);
        setPublicDemo(!!h.public_demo);
      })
      .catch(() => setNvidiaAsr(false));
  }, []);

  // Each new screen starts at the top, and the screen reader hears the new heading.
  useEffect(() => {
    window.scrollTo(0, 0);
    headingRef.current?.focus({ preventScroll: true });
  }, [step, qIdx, confirming]);

  const currentQ = questions[qIdx];
  const draftVal = currentQ ? (values[currentQ.id] ?? emptyValue(currentQ)) : '';
  const draftDetails = currentQ ? (details[currentQ.id] ?? '') : '';
  const setDraftVal = (v: unknown) => currentQ && setValues((prev) => ({ ...prev, [currentQ.id]: v }));
  const setDraftDetails = (v: string) => currentQ && setDetails((prev) => ({ ...prev, [currentQ.id]: v }));

  const startSession = async () => {
    setError('');
    const ageNum = age.trim() === '' ? NaN : Number(age);
    if (!Number.isInteger(ageNum) || ageNum < 1 || ageNum > 120) {
      setError(t('कृपया सही उम्र लिखें (1 से 120)।', 'Please enter a valid age (1 to 120).'));
      return;
    }
    setBusy(true);
    try {
      const [p, qs] = await Promise.all([
        api.createPatient({
          display_name: name.trim() || t('मरीज़ (डेमो)', 'Patient (demo)'),
          age: ageNum,
          language: lang,
        }),
        api.getQuestions(lang),
      ]);
      setPatientId(p.id);
      setQuestions(qs);
      setQIdx(0);
      setStep('questions');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const optionLabel = (q: IntakeQuestion, v: string) => q.options?.find((o) => o.value === v)?.label ?? v;

  const answerText = (q: IntakeQuestion, v: unknown): string => {
    if (q.type === 'meds_multi') {
      const meds = (v as MedPick[]) ?? [];
      return meds
        .map((m) =>
          m.name === 'dont_know'
            ? optionLabel(q, m.name)
            : `${optionLabel(q, m.name)} (${FREQ_LABEL[m.frequency]?.[lang] ?? m.frequency})`,
        )
        .join(', ');
    }
    if (Array.isArray(v)) return (v as string[]).map((x) => optionLabel(q, x)).join(', ');
    if (q.type === 'number') return `${v} ${lang === 'hi' ? (q.unit_hi ?? '') : (q.unit_en ?? '')}`.trim();
    if (q.type === 'text') return String(v || '') || t('(कुछ नहीं)', '(nothing)');
    return optionLabel(q, String(v));
  };

  const validate = (q: IntakeQuestion, v: unknown): string => {
    if (q.type === 'text') return '';
    if (q.type === 'number') {
      const n = Number(v);
      if (String(v).trim() === '' || !Number.isFinite(n) || n < 0 || n > 80) {
        return t('कृपया एक संख्या लिखें।', 'Please enter a number.');
      }
      return '';
    }
    if (Array.isArray(v) ? v.length === 0 : !v) {
      return t('कृपया एक जवाब चुनें।', 'Please choose an answer.');
    }
    return '';
  };

  const goNext = () => {
    if (!currentQ) return;
    const msg = validate(currentQ, draftVal);
    setError(msg);
    if (!msg) setConfirming(true);
  };

  const handleConfirmSave = async () => {
    if (!patientId || !currentQ) return;
    setBusy(true);
    setError('');
    try {
      const value = currentQ.type === 'number' ? Number(draftVal) : draftVal;
      await api.upsertAnswer(patientId, {
        question_id: currentQ.id,
        value,
        raw_text: draftDetails.trim() || null,
        confirmed: true,
      });
      setConfirming(false);
      if (qIdx + 1 < questions.length) setQIdx(qIdx + 1);
      else setStep('upload');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const goBack = () => {
    setError('');
    setConfirming(false);
    if (qIdx > 0) setQIdx(qIdx - 1);
    else setStep('notice');
  };

  const toggleMulti = (val: string) => {
    const arr = Array.isArray(draftVal) ? (draftVal as string[]) : [];
    if (val === 'none') {
      setDraftVal(arr.includes('none') ? [] : ['none']);
      return;
    }
    const filtered = arr.filter((x) => x !== 'none');
    setDraftVal(filtered.includes(val) ? filtered.filter((x) => x !== val) : [...filtered, val]);
  };

  const meds = (Array.isArray(draftVal) ? draftVal : []) as MedPick[];
  const toggleMed = (medName: string) => {
    if (medName === 'dont_know') {
      setDraftVal(meds.some((m) => m.name === 'dont_know') ? [] : [{ name: 'dont_know', frequency: '' }]);
      return;
    }
    const others = meds.filter((m) => m.name !== 'dont_know');
    setDraftVal(
      others.some((m) => m.name === medName)
        ? others.filter((m) => m.name !== medName)
        : [...others, { name: medName, frequency: currentQ?.frequencies?.[0] ?? '1-0-1' }],
    );
  };
  const setMedFreq = (medName: string, frequency: string) =>
    setDraftVal(meds.map((m) => (m.name === medName ? { ...m, frequency } : m)));

  const stepNumber = (delta: number) => {
    const n = Math.max(0, Math.min(80, (Number(draftVal) || 0) + delta));
    setDraftVal(String(n));
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || !patientId) return;
    const list = Array.from(files);
    const base = Date.now();
    setUploads((u) => [...u, ...list.map((f, i) => ({ key: base + i, name: f.name, status: 'uploading' as const, count: 0 }))]);
    // One at a time: each file makes several NVIDIA calls and the free tier is rate-limited.
    for (const [i, file] of list.entries()) {
      const key = base + i;
      try {
        const res = await api.uploadDocument(patientId, file);
        const count = res.observations.length + res.medications.length;
        setUploads((u) =>
          u.map((row) =>
            row.key === key ? { ...row, status: res.document.status === 'done' ? 'done' : 'failed', count } : row,
          ),
        );
      } catch (e) {
        const message = e instanceof ApiError ? e.message : String(e);
        setUploads((u) => u.map((row) => (row.key === key ? { ...row, status: 'error', message } : row)));
      }
    }
  };

  const uploading = uploads.some((u) => u.status === 'uploading');
  const totalSegments = questions.length + 1;
  const segmentsDone = step === 'upload' ? questions.length : qIdx + (confirming ? 1 : 0);
  const wideOptions = !!currentQ && (currentQ.type === 'yes_no' || currentQ.type === 'meds_multi');

  const progress = (
    <div className="kiosk-progress">
      <ol className="segments" aria-hidden="true">
        {Array.from({ length: totalSegments }, (_, i) => (
          <li key={i} className={i < segmentsDone ? 'done' : i === segmentsDone ? 'now' : ''} />
        ))}
      </ol>
      <p className="kiosk-count" role="status">
        {step === 'upload'
          ? t('आख़िरी चरण', 'Last step')
          : t(`सवाल ${qIdx + 1} / ${questions.length}`, `Question ${qIdx + 1} of ${questions.length}`)}
      </p>
    </div>
  );

  return (
    <div className="kiosk" lang={lang}>
      <header className="board">
        <div className="board-in">
          <Logo size={34} />
          <div>
            <p className="board-name">MediKiosk-DM</p>
            <p className="board-sub">
              <span lang="hi">मधुमेह फॉलो-अप</span> <span aria-hidden="true">/</span> Diabetes follow-up
            </p>
          </div>
        </div>
      </header>

      <main className="kiosk-main">
        {step === 'lang' && (
          <section className="kiosk-sec">
            <h1 className="q-text" ref={headingRef} tabIndex={-1}>
              <span lang="hi">अपनी भाषा चुनें</span>
              <span className="q-text-en">Choose your language</span>
            </h1>
            <div className="lang-tiles">
              <button
                className="lang-tile"
                onClick={() => {
                  setLang('hi');
                  setStep('notice');
                }}
              >
                <span className="lang-name" lang="hi">
                  हिन्दी
                </span>
                <span className="lang-sub" lang="hi">
                  हिन्दी में जवाब दें
                </span>
              </button>
              <button
                className="lang-tile"
                onClick={() => {
                  setLang('en');
                  setStep('notice');
                }}
              >
                <span className="lang-name" lang="en">
                  English
                </span>
                <span className="lang-sub" lang="en">
                  Answer in English
                </span>
              </button>
            </div>
          </section>
        )}

        {step === 'notice' && (
          <>
            <section className="kiosk-sec">
              <h1 className="q-text" ref={headingRef} tabIndex={-1}>
                {t('शुरू करने से पहले', 'Before we begin')}
              </h1>
              <div className="banner banner-info kiosk-notice">
                <Alert size={22} />
                <p>
                  {t(
                    'यह डेमो है, इसमें नकली (बनावटी) जानकारी ही डालें। आपके जवाब डॉक्टर को दिखाए जाएँगे। यह मशीन कोई इलाज या सलाह नहीं देती।',
                    'This is a demo, so please use made-up details only. Your answers will be shown to your doctor. This kiosk does not give medical advice.',
                  )}
                </p>
              </div>
              <div className="kiosk-fields">
                <label className="field">
                  <span className="field-label">{t('नाम (वैकल्पिक)', 'Name (optional)')}</span>
                  <input
                    className="input input-big"
                    value={name}
                    maxLength={100}
                    autoComplete="off"
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field-label">{t('उम्र (साल)', 'Age (years)')}</span>
                  <input
                    className="input input-big input-short"
                    inputMode="numeric"
                    autoComplete="off"
                    value={age}
                    onChange={(e) => setAge(e.target.value.replace(/\D/g, '').slice(0, 3))}
                  />
                </label>
              </div>
              {error && (
                <p className="form-error" role="alert">
                  <Alert size={22} />
                  {error}
                </p>
              )}
            </section>
            <ActionBar>
              <button className="btn btn-quiet btn-big" onClick={() => setStep('lang')}>
                <Back size={22} />
                {t('पीछे', 'Back')}
              </button>
              <button className="btn btn-primary btn-big grow" disabled={busy} onClick={startSession}>
                {busy ? t('रुकिए…', 'Please wait…') : t('आगे बढ़ें', 'Continue')}
              </button>
            </ActionBar>
          </>
        )}

        {step === 'questions' && currentQ && (
          <>
            <section className="kiosk-sec">
              {progress}

              {!confirming ? (
                <>
                  <h1 className="q-text" ref={headingRef} tabIndex={-1}>
                    {currentQ.text}
                  </h1>
                  {currentQ.type === 'multi_choice' && (
                    <p className="q-hint">{t('जितने लागू हों, सब चुनें।', 'Choose all that apply.')}</p>
                  )}
                  {currentQ.type === 'meds_multi' && (
                    <p className="q-hint">
                      {t('जो दवाएँ आप लेते हैं, सब चुनें।', 'Choose every medicine you take.')}
                    </p>
                  )}

                  {currentQ.type === 'number' && (
                    <div className="num-row">
                      <button
                        type="button"
                        className="num-step"
                        aria-label={t('एक कम करें', 'One less')}
                        onClick={() => stepNumber(-1)}
                      >
                        −
                      </button>
                      <input
                        className="input input-num"
                        inputMode="decimal"
                        value={String(draftVal ?? '')}
                        onChange={(e) => setDraftVal(e.target.value.replace(/[^\d.]/g, '').slice(0, 4))}
                        aria-label={currentQ.text}
                      />
                      <button
                        type="button"
                        className="num-step"
                        aria-label={t('एक ज़्यादा करें', 'One more')}
                        onClick={() => stepNumber(1)}
                      >
                        +
                      </button>
                      <span className="num-unit">{lang === 'hi' ? currentQ.unit_hi : currentQ.unit_en}</span>
                    </div>
                  )}

                  {currentQ.type === 'text' && (
                    <textarea
                      className="input input-big"
                      rows={4}
                      value={String(draftVal ?? '')}
                      onChange={(e) => setDraftVal(e.target.value)}
                      placeholder={t('यहाँ लिखें (वैकल्पिक)…', 'Type here (optional)…')}
                      aria-label={currentQ.text}
                    />
                  )}

                  {(currentQ.type === 'single_choice' || currentQ.type === 'yes_no') && (
                    <div className={`opts ${wideOptions ? 'cols-2' : ''}`} role="radiogroup" aria-label={currentQ.text}>
                      {currentQ.options?.map((opt) => (
                        <Option
                          key={opt.value}
                          multi={false}
                          selected={draftVal === opt.value}
                          onClick={() => setDraftVal(opt.value)}
                        >
                          {opt.label}
                        </Option>
                      ))}
                    </div>
                  )}

                  {currentQ.type === 'multi_choice' && (
                    <div className="opts" role="group" aria-label={currentQ.text}>
                      {currentQ.options?.map((opt) => (
                        <Option
                          key={opt.value}
                          multi
                          selected={Array.isArray(draftVal) && (draftVal as string[]).includes(opt.value)}
                          onClick={() => toggleMulti(opt.value)}
                        >
                          {opt.label}
                        </Option>
                      ))}
                    </div>
                  )}

                  {currentQ.type === 'meds_multi' && (
                    <>
                      <div className="opts cols-2" role="group" aria-label={currentQ.text}>
                        {currentQ.options?.map((opt) => (
                          <Option
                            key={opt.value}
                            multi
                            selected={meds.some((m) => m.name === opt.value)}
                            onClick={() => toggleMed(opt.value)}
                          >
                            {opt.label}
                          </Option>
                        ))}
                      </div>
                      {meds.filter((m) => m.name !== 'dont_know').length > 0 && (
                        <div className="freq-list">
                          <p className="q-hint">{t('हर दवा आप कब लेते हैं?', 'When do you take each one?')}</p>
                          {meds
                            .filter((m) => m.name !== 'dont_know')
                            .map((m) => (
                              <fieldset key={m.name} className="freq-card">
                                <legend>{optionLabel(currentQ, m.name)}</legend>
                                <div className="seg" role="radiogroup">
                                  {(currentQ.frequencies ?? ['1-0-1']).map((f) => (
                                    <button
                                      key={f}
                                      type="button"
                                      role="radio"
                                      aria-checked={m.frequency === f}
                                      className={`seg-btn ${m.frequency === f ? 'on' : ''}`}
                                      onClick={() => setMedFreq(m.name, f)}
                                      title={f}
                                    >
                                      {FREQ_LABEL[f]?.[lang] ?? f}
                                    </button>
                                  ))}
                                </div>
                              </fieldset>
                            ))}
                        </div>
                      )}
                    </>
                  )}

                  {currentQ.allow_details && (
                    <div className="details-box">
                      <label className="field">
                        <span className="field-label">{t('कुछ और बताना है? (वैकल्पिक)', 'Anything to add? (optional)')}</span>
                        <textarea
                          className="input"
                          rows={2}
                          value={draftDetails}
                          maxLength={2000}
                          onChange={(e) => setDraftDetails(e.target.value)}
                          placeholder={t('यहाँ लिखें या बोलें…', 'Type here or speak…')}
                        />
                      </label>
                      <VoiceInput
                        lang={lang}
                        nvidiaAvailable={nvidiaAsr}
                        onText={(text) => setDraftDetails(draftDetails ? `${draftDetails} ${text}` : text)}
                      />
                    </div>
                  )}

                  {error && (
                    <p className="form-error" role="alert">
                      <Alert size={22} />
                      {error}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <h1 className="q-text" ref={headingRef} tabIndex={-1}>
                    {t('क्या हमने ठीक समझा?', 'Did we understand you?')}
                  </h1>
                  <div className="slip">
                    <p className="slip-q">{currentQ.text}</p>
                    <p className="slip-a hand">{answerText(currentQ, draftVal)}</p>
                    {draftDetails.trim() && <p className="slip-words hand">&ldquo;{draftDetails.trim()}&rdquo;</p>}
                  </div>
                  {error && (
                    <p className="form-error" role="alert">
                      <Alert size={22} />
                      {error}
                    </p>
                  )}
                </>
              )}
            </section>

            <ActionBar>
              {!confirming ? (
                <>
                  <button className="btn btn-quiet btn-big" onClick={goBack}>
                    <Back size={22} />
                    {t('पीछे', 'Back')}
                  </button>
                  <button className="btn btn-primary btn-big grow" onClick={goNext}>
                    {t('आगे', 'Next')}
                  </button>
                </>
              ) : (
                <>
                  <button className="btn btn-quiet btn-big" disabled={busy} onClick={() => setConfirming(false)}>
                    {t('बदलें', 'Change')}
                  </button>
                  <button className="btn btn-primary btn-big grow" disabled={busy} onClick={handleConfirmSave}>
                    {busy ? (
                      t('सेव हो रहा है…', 'Saving…')
                    ) : (
                      <>
                        <Check size={24} strokeWidth={3} />
                        {t('हाँ, सही है', 'Yes, correct')}
                      </>
                    )}
                  </button>
                </>
              )}
            </ActionBar>
          </>
        )}

        {step === 'upload' && (
          <>
            <section className="kiosk-sec">
              {progress}
              <h1 className="q-text" ref={headingRef} tabIndex={-1}>
                {t('पुरानी रिपोर्ट और पर्चे', 'Old reports and prescriptions')}
              </h1>
              <p className="q-hint">
                {t(
                  'हर रिपोर्ट या पर्चे की फ़ोटो लें, या फ़ाइल चुनें। हर एक को पढ़ने में थोड़ा समय लगता है। रिपोर्ट नहीं है तो सीधे “पूरा हुआ” दबाएँ।',
                  'Take a photo of each report or prescription, or choose a file. Each one takes a little while to read. If you have none, just press Finish.',
                )}
              </p>

              {publicDemo ? (
                <div className="banner banner-info">
                  <Info size={22} />
                  <p>
                    {t(
                      'इस सार्वजनिक डेमो में रिपोर्ट अपलोड बंद है। “पूरा हुआ” दबाएँ।',
                      'Report uploads are switched off on this public demo. Press Finish.',
                    )}
                  </p>
                </div>
              ) : (
              <label className="drop">
                <Camera size={36} />
                <span className="drop-title">{t('फ़ोटो लें या फ़ाइल चुनें', 'Take a photo or choose a file')}</span>
                <span className="drop-sub">JPG, PNG, WebP, PDF</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  multiple
                  onChange={(e) => {
                    void handleFiles(e.target.files);
                    e.target.value = '';
                  }}
                />
              </label>
              )}

              {uploads.length > 0 && (
                <ul className="upload-list" aria-live="polite">
                  {uploads.map((u) => (
                    <li key={u.key} className={`upload-row status-${u.status}`}>
                      <span className="upload-icon" aria-hidden="true">
                        {u.status === 'uploading' && <span className="spinner" />}
                        {u.status === 'done' && u.count > 0 && <Check size={22} strokeWidth={3} />}
                        {((u.status === 'done' && u.count === 0) || u.status === 'failed' || u.status === 'error') && (
                          <Alert size={22} />
                        )}
                      </span>
                      <span className="upload-name">{u.name}</span>
                      <span className="upload-msg">
                        {u.status === 'uploading' && t('पढ़ रहे हैं…', 'Reading…')}
                        {u.status === 'done' &&
                          (u.count > 0
                            ? t(`${u.count} जानकारी मिली`, `Read ${u.count} values`)
                            : t('कोई जाँच या दवा नहीं मिली। स्टाफ़ देखेगा।', 'Nothing found. Staff will check.'))}
                        {u.status === 'failed' && t('पढ़ नहीं पाए। स्टाफ़ देखेगा।', 'Could not read. Staff will check.')}
                        {u.status === 'error' && (u.message ?? t('अपलोड नहीं हुआ', 'Upload failed'))}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <ActionBar>
              <button
                className="btn btn-quiet btn-big"
                disabled={uploading}
                onClick={() => {
                  setStep('questions');
                  setQIdx(Math.max(0, questions.length - 1));
                }}
              >
                <Back size={22} />
                {t('पीछे', 'Back')}
              </button>
              <button className="btn btn-primary btn-big grow" disabled={uploading} onClick={() => setStep('done')}>
                {uploading ? t('पढ़ रहे हैं, रुकिए…', 'Still reading, please wait…') : t('पूरा हुआ', 'Finish')}
              </button>
            </ActionBar>
          </>
        )}

        {step === 'done' && (
          <section className="kiosk-sec done">
            <span className="done-mark" aria-hidden="true">
              <Check size={52} strokeWidth={3} />
            </span>
            <h1 className="q-text" ref={headingRef} tabIndex={-1}>
              {t('धन्यवाद', 'Thank you')}
            </h1>
            <p className="done-text">
              {t(
                'कृपया अपनी बारी की प्रतीक्षा करें। आपकी जानकारी डॉक्टर तक पहुँच गई है।',
                'Please wait to be called. Your doctor now has this information.',
              )}
            </p>
            <div className="staff-row">
              {patientId && (
                <Link className="btn btn-quiet" to={`/doctor/${patientId}`} lang="en">
                  Staff: open this patient
                </Link>
              )}
              <a className="btn-link" href="/kiosk" lang="en">
                Staff: start for the next patient
              </a>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
