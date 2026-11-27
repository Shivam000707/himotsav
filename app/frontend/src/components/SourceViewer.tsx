import { useEffect, useRef, useState } from 'react';
import { pageImageUrl, type BBox } from '../api';
import { Alert, Check, Close, Info } from './icons';

export interface SourceTarget {
  kind: 'observation' | 'medication' | 'document';
  id: number;
  title: string;
  valueDisplay: string;
  rawDisplay?: string;
  documentId: number;
  pageNo: number;
  pageW?: number | null;
  pageH?: number | null;
  bbox: BBox | null;
  blockText?: string | null;
  unverified: boolean;
  uncertain?: boolean;
  note?: string | null;
  verifiedByClinician: boolean;
  editedValue: string | null;
  sourceOrg: string | null;
  sourceMode?: 'ai' | 'scripted' | null;
}

interface Props {
  target: SourceTarget | null;
  onClose: () => void;
  onVerify: (target: SourceTarget) => Promise<void>;
  onSaveEdit: (target: SourceTarget, edited: string) => Promise<void>;
}

const PAD = 0.015; // extra margin around the box in the zoomed crop, as a fraction of the page

/** Zoomed crop of the source line, with the marker on it. Positions are percentages, so it scales with the drawer. */
function Crop({ url, bbox, pageW, pageH }: { url: string; bbox: BBox; pageW: number; pageH: number }) {
  const x0 = Math.max(0, bbox.xmin - PAD);
  const y0 = Math.max(0, bbox.ymin - PAD);
  const x1 = Math.min(1, bbox.xmax + PAD);
  const y1 = Math.min(1, bbox.ymax + PAD);
  const bw = Math.max(0.01, x1 - x0);
  const bh = Math.max(0.01, y1 - y0);
  // The container keeps the crop's real aspect ratio; the image is scaled so the crop fills it.
  const aspect = (bw * pageW) / (bh * pageH);
  return (
    <div className="crop" style={{ aspectRatio: `${aspect}` }}>
      <img
        src={url}
        alt=""
        style={{
          width: `${100 / bw}%`,
          left: `${(-x0 / bw) * 100}%`,
          top: `${(-y0 / bh) * 100}%`,
        }}
      />
      <div
        className="paper-mark"
        style={{
          left: `${((bbox.xmin - x0) / bw) * 100}%`,
          top: `${((bbox.ymin - y0) / bh) * 100}%`,
          width: `${((bbox.xmax - bbox.xmin) / bw) * 100}%`,
          height: `${((bbox.ymax - bbox.ymin) / bh) * 100}%`,
        }}
      />
    </div>
  );
}

function ViewerBody({ target, onClose, onVerify, onSaveEdit }: Props & { target: SourceTarget }) {
  const [editVal, setEditVal] = useState(target.editedValue ?? target.valueDisplay);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [imgLoaded, setImgLoaded] = useState(false);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  const imgUrl = pageImageUrl(target.documentId, target.pageNo);
  const bbox = target.bbox;
  const editable = target.kind !== 'document';

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    if (imgLoaded) boxRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [imgLoaded]);

  const run = async (fn: () => Promise<void>) => {
    setSaving(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const unchanged = editVal.trim() === (target.editedValue ?? target.valueDisplay);

  return (
    <div className="scrim" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Source of ${target.title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer-head">
          <div className="drawer-title">
            <h2>{target.title}</h2>
            {editable && (
              <p className="drawer-value">
                <span className="mark mark-static">{target.valueDisplay}</span>
              </p>
            )}
            {target.rawDisplay && target.rawDisplay !== target.valueDisplay && (
              <p className="muted">Printed on the paper as {target.rawDisplay}</p>
            )}
            <p className="muted small">
              {target.sourceOrg ?? 'Uploaded document'}, page {target.pageNo}
            </p>
          </div>
          <button ref={closeRef} className="btn btn-quiet drawer-close" onClick={onClose}>
            <Close size={18} />
            Close
          </button>
        </header>

        <div className="drawer-body">
          {target.sourceMode === 'scripted' && (
            <div className="banner banner-info">
              <Info size={20} />
              <span>Offline demo data. This value was entered from the synthetic answer key, not read by AI.</span>
            </div>
          )}
          {editable && (target.unverified || !bbox) && (
            <div className="banner banner-warn">
              <Alert size={20} />
              <span>No exact place on the paper. The AI&rsquo;s reading could not be matched to one line, so check the page yourself.</span>
            </div>
          )}
          {target.uncertain && !target.verifiedByClinician && (
            <div className="banner banner-warn">
              <Alert size={20} />
              <span>The AI marked this as unsure{target.note ? `: ${target.note}` : '.'}</span>
            </div>
          )}

          {bbox && target.pageW && target.pageH ? (
            <section className="drawer-sec">
              <h3>Where it was read</h3>
              <Crop url={imgUrl} bbox={bbox} pageW={target.pageW} pageH={target.pageH} />
              {target.blockText && <p className="muted small">Text found there: &ldquo;{target.blockText}&rdquo;</p>}
            </section>
          ) : null}

          {editable && (
            <section className="drawer-sec">
              <h3>Your check</h3>
              {target.verifiedByClinician ? (
                <p className="verified-line">
                  <Check size={22} strokeWidth={3} />
                  Checked by the doctor{target.editedValue ? `, corrected to “${target.editedValue}”` : ''}
                </p>
              ) : (
                <button className="btn btn-primary" disabled={saving} onClick={() => run(() => onVerify(target))}>
                  <Check size={20} strokeWidth={3} />
                  This matches the paper
                </button>
              )}
              <div className="field">
                <label className="field-label" htmlFor="source-edit">
                  If it does not match, type the right value
                </label>
                <div className="edit-inputs">
                  <input
                    id="source-edit"
                    className="input"
                    type="text"
                    value={editVal}
                    maxLength={200}
                    onChange={(e) => setEditVal(e.target.value)}
                  />
                  <button
                    className="btn btn-quiet"
                    disabled={saving || !editVal.trim() || unchanged}
                    onClick={() => run(() => onSaveEdit(target, editVal.trim()))}
                  >
                    Save correction
                  </button>
                </div>
              </div>
              {error && (
                <p className="form-error" role="alert">
                  <Alert size={20} />
                  {error}
                </p>
              )}
            </section>
          )}

          <section className="drawer-sec">
            <h3>The whole page</h3>
            <div className="sheet">
              <img
                src={imgUrl}
                alt={`Page ${target.pageNo} of ${target.sourceOrg ?? 'the document'}`}
                className="sheet-img"
                onLoad={() => setImgLoaded(true)}
              />
              {bbox && imgLoaded && (
                <div
                  ref={boxRef}
                  className="paper-mark paper-mark-draw"
                  style={{
                    left: `${bbox.xmin * 100}%`,
                    top: `${bbox.ymin * 100}%`,
                    width: `${(bbox.xmax - bbox.xmin) * 100}%`,
                    height: `${(bbox.ymax - bbox.ymin) * 100}%`,
                  }}
                />
              )}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

export function SourceViewer(props: Props) {
  if (!props.target) return null;
  // Keyed by target so the edit box and image state reset when a different value is opened.
  return <ViewerBody key={`${props.target.kind}-${props.target.id}`} {...props} target={props.target} />;
}
