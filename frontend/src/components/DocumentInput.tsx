import { useState, useEffect, useRef } from 'react';
import { Trash2, FileText, Play, Upload, FileCheck, X, AlertCircle, Loader2 } from 'lucide-react';
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

interface UploadedFileMeta {
  name: string;
  size: string;
  type: string;
  characterCount: number;
}

const FIELD_OPTIONS = [
  'Observed sequence',
  'Reference sequence',
  'Variant sequence',
  'Consensus sequence',
  'Query sequence',
];

const ACCEPTED_FILE_EXTENSIONS = [
  '.txt', '.text', '.md', '.markdown',
  '.pdf', '.docx', '.doc',
  '.fasta', '.fa', '.fna', '.seq',
  '.sam', '.vcf', '.csv', '.tsv', '.json',
].join(',');

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

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

  // File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFileMeta | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  useEffect(() => {
    if (sampleTrigger > 0) {
      setDocumentText(SAMPLE_REPORT_TEXT);
      setReferenceSequence('ATCGATCG');
      setTargetField('Observed sequence');
      setAlphabet('DNA');
      setUploadedFile(null);
      setUploadError(null);
    }
  }, [sampleTrigger]);

  const handleLoadSample = () => {
    setDocumentText(SAMPLE_REPORT_TEXT);
    setReferenceSequence('ATCGATCG');
    setTargetField('Observed sequence');
    setAlphabet('DNA');
    setUploadedFile(null);
    setUploadError(null);
    onLoadSample();
  };

  const handleClear = () => {
    setDocumentText('');
    setUploadedFile(null);
    setUploadError(null);
  };

  const processFile = async (file: File) => {
    setUploadError(null);
    setIsUploading(true);

    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    const isTextFormat = [
      '.txt', '.text', '.md', '.markdown', '.fasta', '.fa',
      '.fna', '.seq', '.sam', '.vcf', '.csv', '.tsv', '.json',
    ].includes(ext);

    // 1. If text/markdown/fasta, parse instantly client-side via FileReader
    if (isTextFormat) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = (e.target?.result as string) || '';
        const cleaned = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
        setDocumentText(cleaned);
        setUploadedFile({
          name: file.name,
          size: formatFileSize(file.size),
          type: ext.replace('.', '').toUpperCase(),
          characterCount: cleaned.length,
        });
        setIsUploading(false);
      };
      reader.onerror = () => {
        setUploadError('Failed to read text file locally.');
        setIsUploading(false);
      };
      reader.readAsText(file);
      return;
    }

    // 2. Binary / Complex formats (.pdf, .docx, .doc): call backend upload-document API
    const formData = new FormData();
    formData.append('file', file);

    try {
      let res = await fetch('/upload-document', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        // Fallback to /api/upload-document
        res = await fetch('/api/upload-document', {
          method: 'POST',
          body: formData,
        });
      }

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setDocumentText(data.text);
      setUploadedFile({
        name: file.name,
        size: formatFileSize(file.size),
        type: data.file_type.toUpperCase(),
        characterCount: data.character_count,
      });
    } catch (err: any) {
      setUploadError(err.message || 'Failed to extract text from document.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processFile(file);
    }
    // Reset file input value to allow selecting same file again
    if (e.target) e.target.value = '';
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      processFile(file);
    }
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
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileInputChange}
            accept={ACCEPTED_FILE_EXTENSIONS}
            className="hidden"
            id="hidden-document-upload-input"
          />

          <button
            id="upload-document-btn"
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="btn-secondary text-xs flex items-center gap-1.5"
            title="Upload any document (.pdf, .docx, .md, .txt, .fasta, .sam, .vcf)"
          >
            {isUploading ? <Loader2 size={13} className="animate-spin text-accent-600" /> : <Upload size={13} />}
            {isUploading ? 'Parsing…' : 'Upload document'}
          </button>

          <button
            id="load-sample-doc-btn"
            type="button"
            onClick={handleLoadSample}
            className="btn-secondary text-xs"
            title="Load standard synthetic clinical report"
          >
            <FileText size={13} />
            Sample report
          </button>

          <button
            id="clear-document-btn"
            type="button"
            onClick={handleClear}
            className="btn-ghost text-xs"
            disabled={!documentText && !uploadedFile}
            title="Clear current text and uploaded file"
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

        {/* Upload feedback badge */}
        {uploadedFile && (
          <div className="flex items-center justify-between px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-md text-xs text-emerald-800">
            <div className="flex items-center gap-2 truncate">
              <FileCheck size={15} className="text-emerald-600 flex-shrink-0" />
              <span className="font-medium truncate">{uploadedFile.name}</span>
              <span className="text-[11px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded font-mono">
                {uploadedFile.type}
              </span>
              <span className="text-[11px] text-emerald-600">
                ({uploadedFile.size} • {uploadedFile.characterCount.toLocaleString()} chars)
              </span>
            </div>
            <button
              onClick={() => setUploadedFile(null)}
              className="text-emerald-600 hover:text-emerald-800 p-0.5"
              title="Dismiss file info"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Upload error banner */}
        {uploadError && (
          <div className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-xs text-red-700">
            <AlertCircle size={15} className="text-red-500 flex-shrink-0" />
            <span className="truncate">{uploadError}</span>
            <button
              onClick={() => setUploadError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              <X size={13} />
            </button>
          </div>
        )}

        {/* Document textarea with drag & drop */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label htmlFor="document-textarea" className="label mb-0">
              Report text
            </label>
            <span className="text-[11px] text-slate-400">
              Drag &amp; drop PDF, DOCX, MD, TXT, or FASTA files here
            </span>
          </div>

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`relative rounded-md transition-all ${
              isDraggingOver ? 'ring-2 ring-accent-500 bg-accent-50/40' : ''
            }`}
          >
            {isDraggingOver && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-accent-50/90 rounded-md border-2 border-dashed border-accent-400 pointer-events-none">
                <Upload size={24} className="text-accent-600 animate-bounce mb-1" />
                <span className="text-xs font-semibold text-accent-800">
                  Drop file here to extract text (.pdf, .docx, .md, .txt, .fasta)
                </span>
              </div>
            )}

            <textarea
              id="document-textarea"
              value={documentText}
              onChange={(e) => setDocumentText(e.target.value)}
              rows={8}
              className={`input resize-y font-mono text-xs ${
                docErr ? 'border-red-400 focus:ring-red-500' : ''
              }`}
              placeholder="Paste a sequencing report or click 'Upload document' above (supports .pdf, .docx, .md, .txt, .fasta)..."
              aria-describedby={docErr ? 'doc-error' : undefined}
            />
          </div>

          <div className="flex items-center justify-between mt-1">
            <span className="text-[10px] text-slate-400">
              {documentText.length.toLocaleString()} characters
            </span>
            {docErr && (
              <span id="doc-error" className="text-[10px] text-red-600">
                {docErr.message}
              </span>
            )}
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
            className={`input font-mono tracking-widest ${
              refErr ? 'border-red-400 focus:ring-red-500' : ''
            }`}
            placeholder="e.g. ATCGATCG"
            aria-describedby={refErr ? 'ref-error' : undefined}
            spellCheck={false}
          />
          {refErr && (
            <span id="ref-error" className="text-[10px] text-red-600 mt-1 block">
              {refErr.message}
            </span>
          )}
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
          <p key={i} className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {e.message}
          </p>
        ))}

        {/* Run button */}
        <button
          id="extract-align-btn"
          onClick={handleRun}
          disabled={loading || isUploading}
          className="btn-primary w-full justify-center py-2"
        >
          <Play size={14} />
          {loading ? 'Processing…' : 'Extract & Align'}
        </button>
      </div>
    </div>
  );
}
