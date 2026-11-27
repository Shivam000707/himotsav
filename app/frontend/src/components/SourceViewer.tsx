import { useState } from 'react';
import type { BBox } from '../api';

export interface SourceTarget {
  kind: 'observation' | 'medication';
  id: number;
  title: string;
  valueDisplay: string;
  documentId: number;
  pageNo: number;
  bbox: BBox | null;
  unverified: boolean;
  verifiedByClinician: boolean;
  editedValue: string | null;
  sourceOrg: string | null;
}

interface Props {
  target: SourceTarget | null;
  onClose: () => void;
  onVerify: (target: SourceTarget) => Promise<void>;
  onSaveEdit: (target: SourceTarget, edited: string) => Promise<void>;
}

export function SourceViewer({ target, onClose, onVerify, onSaveEdit }: Props) {
  const [editVal, setEditVal] = useState(target?.editedValue ?? target?.valueDisplay ?? '');
  const [saving, setSaving] = useState(false);

  if (!target) return null;

  const imgUrl = `/api/documents/${target.documentId}/pages/${target.pageNo}/image`;
  const bbox = target.bbox;

  const handleVerify = async () => {
    setSaving(true);
    try {
      await onVerify(target);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async () => {
    setSaving(true);
    try {
      await onSaveEdit(target, editVal);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="source-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <h3>{target.title}</h3>
            <p className="muted">
              {target.sourceOrg ?? 'Uploaded document'} · Page {target.pageNo}
            </p>
          </div>
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        {(target.unverified || !bbox) && (
          <div className="banner-warn">
            Unverified: no exact source bounding box was matched on this page.
          </div>
        )}

        {bbox && (
          <div className="crop-box-wrap">
            <div className="crop-label">Zoomed region</div>
            <div
              className="crop-preview"
              style={{
                backgroundImage: `url(${imgUrl})`,
                backgroundPosition: `${bbox.xmin * 100}% ${bbox.ymin * 100}%`,
                backgroundSize: `${Math.max(150, 100 / Math.max(0.15, bbox.xmax - bbox.xmin))}%`,
              }}
            />
          </div>
        )}

        <div className="drawer-actions">
          <div className="edit-row">
            <input
              type="text"
              value={editVal}
              onChange={(e) => setEditVal(e.target.value)}
              aria-label="Edited value"
            />
            <button className="btn-secondary" disabled={saving} onClick={handleEdit}>
              Save edit
            </button>
          </div>
          <button
            className="btn-primary"
            disabled={saving || target.verifiedByClinician}
            onClick={handleVerify}
          >
            {target.verifiedByClinician ? 'Verified by clinician' : 'Verify against source'}
          </button>
        </div>

        <div className="full-page-wrap">
          <img src={imgUrl} alt={`Document page ${target.pageNo}`} className="full-page-img" />
          {bbox && (
            <div
              className="bbox-overlay"
              style={{
                left: `${bbox.xmin * 100}%`,
                top: `${bbox.ymin * 100}%`,
                width: `${(bbox.xmax - bbox.xmin) * 100}%`,
                height: `${(bbox.ymax - bbox.ymin) * 100}%`,
              }}
            />
          )}
        </div>
      </aside>
    </div>
  );
}
