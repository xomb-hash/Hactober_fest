import { useState, useEffect } from 'react';
import { Trash2, FileText, Play } from 'lucide-react';
import type { ExtractionRequest } from '../types/helixguard';
import { SAMPLE_REPORT_TEXT } from '../services/mockHelixguardApi';

interface Props {
  onRun: (req: ExtractionRequest) => void;
  onLoadSample: () => void;
  errors: { message: string; field?: string }[];
  loading: boolean;
  initialDocumentText?: string;
  sampleTrigger?: number;
}

const FIELD_OPTIONS = [
  'Observed sequence',
  'Reference sequence',
  'Variant sequence',
  'Consensus sequence',
  'Query sequence',
];

export function DocumentInput({
  onRun,
  onLoadSample,
  errors,
  loading,
  initialDocumentText = '',
  sampleTrigger = 0,
}: Props) {
  const [documentText, setDocumentText] = useState(initialDocumentText || SAMPLE_REPORT_TEXT);
  const [referenceSequence, setReferenceSequence] = useState('ATCGATCG');
  const [targetField, setTargetField] = useState('Observed sequence');
  const [alphabet, setAlphabet] = useState<'DNA' | 'RNA'>('DNA');

  useEffect(() => {
    if (sampleTrigger > 0) {
      setDocumentText(SAMPLE_REPORT_TEXT);
      setReferenceSequence('ATCGATCG');
      setTargetField('Observed sequence');
      setAlphabet('DNA');
    }
  }, [sampleTrigger]);

  const handleLoadSample = () => {
    setDocumentText(SAMPLE_REPORT_TEXT);
    setReferenceSequence('ATCGATCG');
    setTargetField('Observed sequence');
    setAlphabet('DNA');
    onLoadSample();
  };

  const handleRun = () => {
    onRun({ documentText, referenceSequence, targetField, alphabet });
  };

  const docErr = errors.find((e) => e.field === 'documentText');
  const refErr = errors.find((e) => e.field === 'referenceSequence');

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Document Input</span>
        <div className="flex items-center gap-2">
          <button
            id="load-sample-doc-btn"
            onClick={handleLoadSample}
            className="btn-secondary text-xs"
          >
            <FileText size={13} />
            Sample report
          </button>
          <button
            id="clear-document-btn"
            onClick={() => setDocumentText('')}
            className="btn-ghost text-xs"
            disabled={!documentText}
          >
            <Trash2 size={13} />
            Clear
          </button>
        </div>
      </div>

      <div className="card-body space-y-4">
        {/* Demo notice */}
        <div className="flex items-start gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-md">
          <span className="text-amber-600 mt-0.5 flex-shrink-0 text-sm">⚠</span>
          <p className="text-xs text-amber-800 leading-snug">
            <strong>Demo only.</strong> Use synthetic data. This application does not provide clinical diagnoses or treatment recommendations.
          </p>
        </div>

        {/* Document textarea */}
        <div>
          <label htmlFor="document-textarea" className="label">
            Report text
          </label>
          <textarea
            id="document-textarea"
            value={documentText}
            onChange={(e) => setDocumentText(e.target.value)}
            rows={8}
            className={`input resize-y font-mono text-xs ${docErr ? 'border-red-400 focus:ring-red-500' : ''}`}
            placeholder="Paste a sequencing report or genomic document here…"
            aria-describedby={docErr ? 'doc-error' : undefined}
          />
          <div className="flex items-center justify-between mt-1">
            <span className="text-[10px] text-slate-400">{documentText.length.toLocaleString()} characters</span>
            {docErr && <span id="doc-error" className="text-[10px] text-red-600">{docErr.message}</span>}
          </div>
        </div>

        {/* Reference sequence */}
        <div>
          <label htmlFor="reference-sequence" className="label">
            Reference sequence
          </label>
          <input
            id="reference-sequence"
            type="text"
            value={referenceSequence}
            onChange={(e) => setReferenceSequence(e.target.value.toUpperCase())}
            className={`input font-mono tracking-widest ${refErr ? 'border-red-400 focus:ring-red-500' : ''}`}
            placeholder="e.g. ATCGATCG"
            aria-describedby={refErr ? 'ref-error' : undefined}
            spellCheck={false}
          />
          {refErr && <span id="ref-error" className="text-[10px] text-red-600 mt-1 block">{refErr.message}</span>}
        </div>

        {/* Controls row */}
        <div className="grid grid-cols-2 gap-3">
          {/* Field selector */}
          <div>
            <label htmlFor="field-selector" className="label">Target field</label>
            <select
              id="field-selector"
              value={targetField}
              onChange={(e) => setTargetField(e.target.value)}
              className="input"
            >
              {FIELD_OPTIONS.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>

          {/* Alphabet */}
          <div>
            <label className="label">Sequence alphabet</label>
            <div className="flex gap-2 mt-1" role="radiogroup" aria-label="Sequence alphabet">
              {(['DNA', 'RNA'] as const).map((a) => (
                <label
                  key={a}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-sm font-medium cursor-pointer transition-colors ${
                    alphabet === a
                      ? 'bg-accent-50 border-accent-400 text-accent-700'
                      : 'bg-white border-slate-300 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="alphabet"
                    value={a}
                    checked={alphabet === a}
                    onChange={() => setAlphabet(a)}
                    className="sr-only"
                  />
                  {a}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* General errors */}
        {errors.filter((e) => !e.field).map((e, i) => (
          <p key={i} className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{e.message}</p>
        ))}

        {/* Run button */}
        <button
          id="extract-align-btn"
          onClick={handleRun}
          disabled={loading}
          className="btn-primary w-full justify-center py-2"
        >
          <Play size={14} />
          {loading ? 'Processing…' : 'Extract & Align'}
        </button>
      </div>
    </div>
  );
}
