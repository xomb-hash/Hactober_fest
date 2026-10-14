import { useState, useEffect, useRef } from 'react';
import { Trash2, FileText, Play, Upload, FileCheck, X, AlertCircle, Loader2, Sparkles, Image as ImageIcon, Dna, ShieldCheck } from 'lucide-react';
import type { ExtractionRequest, HelixGuardApiResponse } from '../types/helixguard';
import { SAMPLE_REPORT_TEXT } from '../services/mockHelixguardApi';

interface Props {
  onRun: (req: ExtractionRequest) => void;
  onLoadSample: () => void;
  onClear?: () => void;
  result?: HelixGuardApiResponse | null;
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
  '.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp',
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
  onClear,
  result,
  errors,
  loading,
  initialDocumentText = '',
  sampleTrigger = 0,
}: Props) {
  const [documentText, setDocumentText] = useState(initialDocumentText || SAMPLE_REPORT_TEXT);
  const [referenceSequence, setReferenceSequence] = useState('ATCGATCG');
  const [targetField, setTargetField] = useState('Observed sequence');
  const [alphabet, setAlphabet] = useState<'DNA' | 'RNA'>('DNA');
  const [useAi, setUseAi] = useState(true);
  const [useTokenMask, setUseTokenMask] = useState(true);
  const [useDatabase, setUseDatabase] = useState(true);

  // File upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFileMeta | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (sampleTrigger > 0) {
      setDocumentText(SAMPLE_REPORT_TEXT);
      setReferenceSequence('ATCGATCG');
      setTargetField('Observed sequence');
      setAlphabet('DNA');
      setUploadedFile(null);
      setUploadError(null);
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl);
        setImagePreviewUrl(null);
      }
    }
  }, [sampleTrigger]);

  const handleLoadSample = () => {
    setDocumentText(SAMPLE_REPORT_TEXT);
    setReferenceSequence('ATCGATCG');
    setTargetField('Observed sequence');
    setAlphabet('DNA');
    setUploadedFile(null);
    setUploadError(null);
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
      setImagePreviewUrl(null);
    }
    onLoadSample();
  };

  const handleClear = () => {
    setDocumentText('');
    setUploadedFile(null);
    setUploadError(null);
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
      setImagePreviewUrl(null);
    }
    onClear?.();
  };

  const processFile = async (file: File) => {
    setUploadError(null);
    setIsUploading(true);

    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    const isImageFormat = [
      '.png', '.jpg', '.jpeg', '.webp', '.tiff', '.tif', '.bmp',
    ].includes(ext) || file.type.startsWith('image/');

    if (isImageFormat) {
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
      const preview = URL.createObjectURL(file);
      setImagePreviewUrl(preview);
    } else {
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl);
        setImagePreviewUrl(null);
      }
    }

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

    // 2. Binary / Images / PDF / DOCX: call backend upload-document API
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
        type: data.file_type === 'image_ocr' ? 'IMAGE OCR (RapidOCR)' : data.file_type.toUpperCase(),
        characterCount: data.character_count,
      });
    } catch (err: any) {
      setUploadError(err.message || 'Failed to extract text from document or image.');
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
    onRun({
      documentText,
      referenceSequence: useDatabase ? 'DATABASE' : referenceSequence,
      targetField,
      alphabet,
      useAi,
      searchDatabase: useDatabase,
      useTokenMask,
    });
  };

  const handleSelectCandidate = (cand: { start: number; end: number }) => {
    onRun({
      documentText,
      referenceSequence: useDatabase ? 'DATABASE' : referenceSequence,
      targetField,
      alphabet,
      useAi,
      searchDatabase: useDatabase,
      useTokenMask,
      selectedSpan: cand,
    });
  };

  const docErr = errors.find((e) => e.field === 'documentText');
  const refErr = errors.find((e) => e.field === 'referenceSequence');

  const candidates = result?.extractionResult?.candidateSpans;
  const isAbstained = result?.extractionResult?.extractionStatus === 'abstained';

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-2">
          <span className="card-title">Document Input</span>
          {result?.extractionResult?.formatDetected && result.extractionResult.formatDetected !== 'text' && (
            <span className="text-[10px] bg-purple-100 text-purple-800 font-mono uppercase px-1.5 py-0.5 rounded border border-purple-200">
              {result.extractionResult.formatDetected} Adapter
            </span>
          )}
        </div>
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
            title="Upload any document or image (.png, .jpg, .webp, .pdf, .docx, .md, .txt, .fasta)"
          >
            {isUploading ? <Loader2 size={13} className="animate-spin text-accent-600" /> : <Upload size={13} />}
            {isUploading ? 'OCR Running…' : 'Upload doc / image'}
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
            disabled={!documentText && !uploadedFile && !imagePreviewUrl && !result}
            title="Clear all text, uploaded file, and verification results"
          >
            <Trash2 size={13} />
            Clear All
          </button>
        </div>
      </div>

      <div className="card-body space-y-4">
        {/* Interactive Human-in-the-Loop Disambiguation (R2-2) */}
        {isAbstained && candidates && candidates.length > 0 && (
          <div className="p-3 bg-amber-50/90 border border-amber-300 rounded-md space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-900">
                <AlertCircle size={15} className="text-amber-600 flex-shrink-0" />
                <span>Interactive Disambiguation — Multiple Candidate Sequences Located</span>
              </div>
              <span className="text-[10px] bg-amber-200/80 text-amber-950 font-mono px-2 py-0.5 rounded font-medium">
                {candidates.length} candidates
              </span>
            </div>
            <p className="text-[11px] text-amber-800 leading-snug">
              The automated scout abstained because multiple candidates exist in the source document.
              <strong> Click on the intended sequence span below</strong> to deterministically verify and align it:
            </p>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {candidates.map((c, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSelectCandidate({ start: c.start, end: c.end })}
                  className="w-full text-left p-2.5 rounded bg-white hover:bg-amber-100/60 border border-amber-200 hover:border-amber-400 transition-all text-xs flex items-center justify-between group shadow-2xs cursor-pointer"
                >
                  <div className="min-w-0 flex-1 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-medium">
                        Offsets [{c.start}:{c.end}) ({c.end - c.start} bp)
                      </span>
                      {c.label && (
                        <span className="text-[10px] text-purple-700 font-medium truncate">
                          {c.label}
                        </span>
                      )}
                    </div>
                    <div className="font-mono text-[11px] text-slate-800 truncate mt-1">
                      {c.preview}…
                    </div>
                  </div>
                  <span className="text-[11px] text-amber-700 font-semibold group-hover:text-amber-900 flex-shrink-0 bg-amber-100/60 group-hover:bg-amber-200 px-2 py-1 rounded border border-amber-200">
                    Verify this span →
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Demo notice */}
        <div className="flex items-start gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-md">
          <span className="text-amber-600 mt-0.5 flex-shrink-0 text-sm">⚠</span>
          <p className="text-xs text-amber-800 leading-snug">
            <strong>Demo only.</strong> Use synthetic data. This application does not provide clinical diagnoses or treatment recommendations.
          </p>
        </div>

        {/* Image Preview Banner */}
        {imagePreviewUrl && (
          <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 border border-slate-200 rounded-md">
            <div className="relative flex-shrink-0">
              <img
                src={imagePreviewUrl}
                alt="Source preview"
                className="h-14 w-20 object-contain rounded border border-slate-300 bg-white p-0.5 shadow-xs"
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                <ImageIcon size={14} className="text-accent-600" />
                <span>Image Scan Uploaded</span>
                <span className="text-[10px] bg-accent-100 text-accent-700 px-1.5 py-0.5 rounded font-mono font-normal">
                  RapidOCR ONNX Local
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5 truncate">
                Text recognized locally. Review the transcribed report in the field below before extraction.
              </p>
            </div>
            <button
              onClick={() => {
                URL.revokeObjectURL(imagePreviewUrl);
                setImagePreviewUrl(null);
              }}
              className="text-slate-400 hover:text-slate-600 p-1"
              title="Close image thumbnail"
            >
              <X size={14} />
            </button>
          </div>
        )}

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
              Drag &amp; drop image (.png, .jpg), PDF, DOCX, MD, TXT, or FASTA files here
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
                  Drop file here to extract text (images, .pdf, .docx, .md, .fasta)
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
              placeholder="Paste a sequencing report or upload image/document (supports .png, .jpg, .pdf, .docx, .md, .txt, .fasta)..."
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

        {/* Reference Mode Selection */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="label mb-0">Reference Target</label>
            <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-md text-xs">
              <button
                type="button"
                onClick={() => setUseDatabase(true)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                  useDatabase
                    ? 'bg-white text-purple-700 shadow-xs border border-purple-200'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Viral Database (19,625 Genomes)
              </button>
              <button
                type="button"
                onClick={() => setUseDatabase(false)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                  !useDatabase
                    ? 'bg-white text-slate-800 shadow-xs border border-slate-200'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Custom Sequence
              </button>
            </div>
          </div>

          {useDatabase ? (
            <div className="flex items-center justify-between p-3 bg-purple-50/70 border border-purple-200 rounded-md text-xs text-purple-900">
              <div className="flex items-center gap-2.5">
                <Dna size={18} className="text-purple-600 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-purple-950 flex items-center gap-1.5">
                    <span>RefSeq Viral Multi-FASTA Database</span>
                    <span className="text-[10px] bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-mono font-normal">
                      19,625 Genomes
                    </span>
                  </div>
                  <div className="text-[11px] text-purple-700 mt-0.5">
                    Finds the closest matching genome via k-mer prefiltering &amp; C++ Smith-Waterman alignment.
                  </div>
                </div>
              </div>
              <span className="text-[10px] bg-purple-200/60 text-purple-900 font-mono px-2 py-0.5 rounded font-medium border border-purple-300/50">
                viral.1.1.genomic.fna
              </span>
            </div>
          ) : (
            <div>
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

        {/* AI Scout Assist Toggle */}
        <div className="flex items-center justify-between px-3 py-2 bg-purple-50/70 border border-purple-200 rounded-md">
          <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-800 select-none">
            <input
              type="checkbox"
              id="ai-scout-assist-toggle"
              checked={useAi}
              onChange={(e) => setUseAi(e.target.checked)}
              className="rounded border-purple-300 text-purple-600 focus:ring-purple-500 h-4 w-4"
            />
            <div className="flex items-center gap-1.5">
              <Sparkles size={14} className="text-purple-600" />
              <span>AI Scout Assist (Ollama Cloud · <code className="bg-purple-100 text-purple-800 px-1 py-0.5 rounded text-[11px] font-mono">gemma4:31b</code>)</span>
            </div>
          </label>
          <span className="text-[11px] font-medium text-purple-700">
            {useAi ? 'Active (Key Pool)' : 'Deterministic Only'}
          </span>
        </div>

        {/* R2-1 Privacy Guard / Token-Masked Scout Toggle */}
        <div className="flex items-center justify-between px-3 py-2 bg-emerald-50/70 border border-emerald-200 rounded-md">
          <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-800 select-none">
            <input
              type="checkbox"
              id="token-mask-privacy-toggle"
              checked={useTokenMask}
              onChange={(e) => setUseTokenMask(e.target.checked)}
              className="rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500 h-4 w-4"
            />
            <div className="flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-emerald-600" />
              <span>Privacy Guard (Token-Masked Scout · LLM never sees nucleotides)</span>
            </div>
          </label>
          <span className="text-[11px] font-medium text-emerald-700">
            {useTokenMask ? 'Enforced (R2 Privacy)' : 'Raw Fallback'}
          </span>
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
          {useDatabase ? <Dna size={14} /> : <Play size={14} />}
          {loading ? 'Processing…' : useDatabase ? 'Extract & Identify Closest Genome' : 'Extract & Align'}
        </button>

      </div>
    </div>
  );
}
