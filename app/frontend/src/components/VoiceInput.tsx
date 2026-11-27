import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Mic, Stop } from './icons';

/**
 * Mic button for the kiosk's "details" box. Tries, in order:
 *   1. NVIDIA speech-to-text through the backend (when /api/health says it is configured),
 *   2. the browser's built-in speech recognition (Chrome and Edge),
 *   3. nothing: the button is hidden and the patient types.
 * The recognised words are only put into the text box. The patient still checks them on the
 * confirm screen before anything is saved.
 */

type Mode = 'nvidia' | 'browser' | 'none';

interface Props {
  lang: 'hi' | 'en';
  nvidiaAvailable: boolean;
  onText: (text: string) => void;
}

// Minimal typing for the Web Speech API, which TypeScript's DOM library does not include.
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

function browserRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition || w.webkitSpeechRecognition || null) as (new () => SpeechRecognitionLike) | null;
}

const TARGET_RATE = 16000;
const MAX_SECONDS = 30;

function encodeWav(samples: Float32Array, inputRate: number): Blob {
  // Downsample by averaging, then write 16-bit mono PCM with a WAV header.
  const ratio = inputRate / TARGET_RATE;
  const outLength = Math.floor(samples.length / ratio);
  const pcm = new Int16Array(outLength);
  for (let i = 0; i < outLength; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += samples[j];
    const v = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
    pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + pcm.length * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, TARGET_RATE, true);
  view.setUint32(28, TARGET_RATE * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, 'data');
  view.setUint32(40, pcm.length * 2, true);
  new Int16Array(buffer, 44).set(pcm);
  return new Blob([buffer], { type: 'audio/wav' });
}

export function VoiceInput({ lang, nvidiaAvailable, onText }: Props) {
  const initialMode: Mode = nvidiaAvailable ? 'nvidia' : browserRecognition() ? 'browser' : 'none';
  const [mode, setMode] = useState<Mode>(initialMode);
  const [state, setState] = useState<'idle' | 'listening' | 'working'>('idle');
  const [message, setMessage] = useState('');
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => setMode(nvidiaAvailable ? 'nvidia' : browserRecognition() ? 'browser' : 'none'), [nvidiaAvailable]);
  useEffect(() => () => stopRef.current?.(), []);

  const t = (hi: string, en: string) => (lang === 'hi' ? hi : en);
  const speechLang = lang === 'hi' ? 'hi-IN' : 'en-IN';

  const fallBack = (why: string) => {
    if (browserRecognition()) {
      setMode('browser');
      setMessage(t('फिर से बोलें।', 'Please try speaking again.'));
    } else {
      setMode('none');
      setMessage(t('आवाज़ काम नहीं कर रही, कृपया लिखें।', 'Voice is not available, please type.'));
    }
    console.warn('NVIDIA speech-to-text unavailable:', why);
  };

  const startNvidia = async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true } });
    } catch {
      setMessage(t('माइक की अनुमति नहीं मिली।', 'Microphone permission was not given.'));
      return;
    }
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    const chunks: Float32Array[] = [];
    processor.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    source.connect(processor);
    processor.connect(ctx.destination);
    setState('listening');
    setMessage(t('बोलिए… रुकने के लिए फिर दबाएँ।', 'Speak now… press again to stop.'));

    let stopped = false;
    const stop = async () => {
      if (stopped) return;
      stopped = true;
      stopRef.current = null;
      clearTimeout(timer);
      processor.disconnect();
      source.disconnect();
      stream.getTracks().forEach((tr) => tr.stop());
      const rate = ctx.sampleRate;
      await ctx.close();
      const total = chunks.reduce((n, c) => n + c.length, 0);
      if (total < rate * 0.3) {
        setState('idle');
        setMessage(t('कुछ सुनाई नहीं दिया।', 'Nothing was heard.'));
        return;
      }
      const all = new Float32Array(total);
      let off = 0;
      for (const c of chunks) {
        all.set(c, off);
        off += c.length;
      }
      setState('working');
      setMessage(t('समझ रहे हैं…', 'Working it out…'));
      try {
        const res = await api.transcribe(encodeWav(all, rate), speechLang);
        if (res.fallback_needed) {
          fallBack(res.note ?? 'unknown');
        } else if (res.text) {
          onText(res.text);
          setMessage(t('नीचे लिखा हुआ जाँच लें।', 'Check the words below.'));
        } else {
          setMessage(t('कुछ समझ नहीं आया, फिर से बोलें।', 'Could not make out the words, please try again.'));
        }
      } catch (e) {
        fallBack(String(e));
      }
      setState('idle');
    };
    const timer = setTimeout(stop, MAX_SECONDS * 1000);
    stopRef.current = () => void stop();
  };

  const startBrowser = () => {
    const Rec = browserRecognition();
    if (!Rec) {
      setMode('none');
      return;
    }
    const rec = new Rec();
    rec.lang = speechLang;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      const text = Array.from(e.results)
        .map((r) => r[0]?.transcript ?? '')
        .join(' ')
        .trim();
      if (text) {
        onText(text);
        setMessage(t('नीचे लिखा हुआ जाँच लें।', 'Check the words below.'));
      }
    };
    rec.onerror = (e) => {
      setMessage(
        e.error === 'not-allowed'
          ? t('माइक की अनुमति नहीं मिली।', 'Microphone permission was not given.')
          : t('आवाज़ समझ नहीं आई, कृपया लिखें।', 'Could not hear clearly, please type.'),
      );
    };
    rec.onend = () => {
      stopRef.current = null;
      setState('idle');
    };
    stopRef.current = () => rec.stop();
    setState('listening');
    setMessage(t('बोलिए…', 'Speak now…'));
    rec.start();
  };

  if (mode === 'none') {
    return message ? <p className="muted">{message}</p> : null;
  }

  const onClick = () => {
    if (state === 'listening') {
      stopRef.current?.();
      return;
    }
    setMessage('');
    if (mode === 'nvidia') void startNvidia();
    else startBrowser();
  };

  return (
    <div className="voice-row">
      <button
        type="button"
        className={`btn btn-quiet voice-btn ${state === 'listening' ? 'listening' : ''}`}
        onClick={onClick}
        disabled={state === 'working'}
        aria-pressed={state === 'listening'}
      >
        {state === 'listening' ? <Stop size={22} /> : <Mic size={22} />}
        {state === 'listening' ? t('रोकें', 'Stop') : t('बोलकर बताएँ', 'Speak your answer')}
      </button>
      {message && (
        <span className="muted" role="status">
          {message}
        </span>
      )}
    </div>
  );
}
