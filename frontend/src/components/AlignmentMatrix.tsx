import { useState } from 'react';
import type { AlignmentResult } from '../types/helixguard';

interface Props {
  result: AlignmentResult;
}

// Colour scale: low → high score
function cellColor(value: number, max: number): string {
  if (max === 0) return '#f8fafc';
  const ratio = value / max;
  if (value <= 0) return '#f8fafc';
  if (ratio < 0.25) return '#dcfce7';
  if (ratio < 0.5)  return '#86efac';
  if (ratio < 0.75) return '#22c55e';
  return '#15803d';
}

function cellTextColor(value: number, max: number): string {
  if (max === 0) return '#94a3b8';
  const ratio = value / max;
  if (value <= 0) return '#94a3b8';
  return ratio >= 0.75 ? '#ffffff' : '#15803d';
}

export function AlignmentMatrix({ result }: Props) {
  const [showTable, setShowTable] = useState(false);

  if (result.skipped) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Alignment</span>
        </div>
        <div className="card-body">
          <div className="flex items-start gap-2 p-3 bg-slate-50 border border-slate-200 rounded-md">
            <span className="text-slate-400 mt-0.5">—</span>
            <p className="text-sm text-slate-600">{result.skipReason}</p>
          </div>
        </div>
      </div>
    );
  }

  const { referenceSequence, querySequence, alignedReference, alignedQuery,
          alignmentScore, maxScoringCell, dpMatrix, scoringParams } = result;

  const maxVal = maxScoringCell.value;
  const refChars = ['', ...referenceSequence.split('')];
  const queryChars = ['', ...querySequence.split('')];

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Smith–Waterman Alignment</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-mono">
            match {scoringParams.match > 0 ? '+' : ''}{scoringParams.match} / 
            mismatch {scoringParams.mismatch} / 
            gap {scoringParams.gap}
          </span>
          <button
            onClick={() => setShowTable(!showTable)}
            className="btn-ghost text-xs"
            aria-pressed={showTable}
          >
            {showTable ? 'Heatmap view' : 'Table view'}
          </button>
        </div>
      </div>
      <div className="card-body space-y-4">

        {/* Summary row */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-center">
            <p className="text-[10px] text-slate-400 uppercase tracking-wider">Score</p>
            <p className="text-xl font-bold text-emerald-700 font-mono mt-0.5">{alignmentScore}</p>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-center">
            <p className="text-[10px] text-slate-400 uppercase tracking-wider">Max cell</p>
            <p className="text-sm font-mono text-slate-700 mt-0.5">
              ({maxScoringCell.row}, {maxScoringCell.col})
            </p>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-center">
            <p className="text-[10px] text-slate-400 uppercase tracking-wider">Length</p>
            <p className="text-sm font-mono text-slate-700 mt-0.5">
              {referenceSequence.length} × {querySequence.length}
            </p>
          </div>
        </div>

        {/* Aligned sequences */}
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-600">Local alignment</p>
          <div className="bg-slate-50 border border-slate-200 rounded-md p-3 overflow-x-auto">
            <div className="font-mono text-sm space-y-1 min-w-fit">
              <div className="flex items-center gap-2">
                <span className="text-[10px] w-10 text-slate-400 flex-shrink-0">REF</span>
                <span className="tracking-wider">{alignedReference.split('').map((ch, i) => {
                  const isGap = ch === '-';
                  return <span key={i} className={isGap ? 'text-slate-300' : 'text-slate-800'}>{ch}</span>;
                })}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] w-10 text-slate-400 flex-shrink-0">QRY</span>
                <span className="tracking-wider">{alignedQuery.split('').map((ch, i) => {
                  const refCh = alignedReference[i];
                  const isMatch = ch === refCh;
                  const isGap = ch === '-';
                  return (
                    <span key={i} className={
                      isGap ? 'text-slate-300' :
                      isMatch ? 'text-emerald-700' : 'text-red-600'
                    }>{ch}</span>
                  );
                })}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] w-10 flex-shrink-0"></span>
                <span className="tracking-wider text-slate-400">{alignedReference.split('').map((ch, i) => {
                  if (ch === '-' || alignedQuery[i] === '-') return <span key={i}> </span>;
                  return <span key={i} className={ch === alignedQuery[i] ? 'text-emerald-500' : 'text-red-400'}>
                    {ch === alignedQuery[i] ? '|' : '×'}
                  </span>;
                })}</span>
              </div>
            </div>
          </div>
        </div>

        {/* DP Matrix */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-slate-600">
              Dynamic programming matrix {showTable ? '(table)' : '(heatmap)'}
            </p>
            {/* Legend */}
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
              <span>Low</span>
              <div className="flex gap-0.5">
                {['#f8fafc','#dcfce7','#86efac','#22c55e','#15803d'].map((c) => (
                  <div key={c} style={{ background: c }} className="w-4 h-3 rounded-sm border border-slate-200" />
                ))}
              </div>
              <span>High</span>
            </div>
          </div>

          <div className="overflow-auto max-h-80 rounded-md border border-slate-200">
            {showTable ? (
              /* Accessible table view */
              <table className="text-[10px] font-mono border-collapse w-full" aria-label="Smith-Waterman DP matrix">
                <thead>
                  <tr>
                    {refChars.map((ch, j) => (
                      <th key={j} scope="col" className="px-2 py-1 text-slate-500 border border-slate-200 bg-slate-50 font-semibold sticky top-0">
                        {j === 0 ? '' : ch}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dpMatrix.map((row, i) => (
                    <tr key={i}>
                      <th scope="row" className="px-2 py-1 text-slate-500 border border-slate-200 bg-slate-50 font-semibold sticky left-0">
                        {i === 0 ? '' : queryChars[i]}
                      </th>
                      {row.map((val, j) => {
                        const isMax = i === maxScoringCell.row && j === maxScoringCell.col;
                        return (
                          <td
                            key={j}
                            className={`px-2 py-1 text-center border border-slate-100 ${isMax ? 'ring-2 ring-inset ring-emerald-500' : ''}`}
                            aria-label={`Row ${i}, col ${j}: ${val}`}
                          >
                            {val}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              /* Heatmap view */
              <div role="img" aria-label="Smith-Waterman DP matrix heatmap">
                <table className="border-collapse" aria-hidden="true">
                  <thead>
                    <tr>
                      {refChars.map((ch, j) => (
                        <th key={j} className="px-1 py-0.5 text-[9px] text-slate-400 font-semibold min-w-[28px] sticky top-0 bg-white border-b border-slate-200">
                          {j === 0 ? '' : ch}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dpMatrix.map((row, i) => (
                      <tr key={i}>
                        <td className="px-1 py-0.5 text-[9px] text-slate-400 font-semibold sticky left-0 bg-white border-r border-slate-200 min-w-[20px]">
                          {i === 0 ? '' : queryChars[i]}
                        </td>
                        {row.map((val, j) => {
                          const isMax = i === maxScoringCell.row && j === maxScoringCell.col;
                          const bg = cellColor(val, maxVal);
                          const color = cellTextColor(val, maxVal);
                          return (
                            <td
                              key={j}
                              style={{ background: bg, color, outline: isMax ? '2px solid #16a34a' : 'none', outlineOffset: '-1px' }}
                              className="text-center text-[9px] font-mono font-medium w-7 h-6 border border-slate-100"
                              title={`[${i},${j}] = ${val}${isMax ? ' (max)' : ''}`}
                            >
                              {val}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">
            Max-scoring cell highlighted with green outline at ({maxScoringCell.row}, {maxScoringCell.col}) = {maxScoringCell.value}.
            Scoring: match {scoringParams.match > 0 ? '+' : ''}{scoringParams.match}, 
            mismatch {scoringParams.mismatch}, gap {scoringParams.gap}.
          </p>
        </div>
      </div>
    </div>
  );
}
