import { Dna, ShieldCheck, AlertTriangle, ExternalLink, AlertCircle } from 'lucide-react';
import type { GenomeIdentificationResult, GenomeCandidate } from '../types/helixguard';

interface Props {
  identification: GenomeIdentificationResult;
}

export function GenomeIdentificationCard({ identification }: Props) {
  const { closestMatch, topCandidates, abstain, abstainReason, totalCandidatesEvaluated, searchTimeMs } = identification;

  return (
    <div className="card border-purple-200 bg-gradient-to-br from-white to-purple-50/20 shadow-xs">
      <div className="card-header bg-purple-50/50 border-b border-purple-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Dna size={16} className="text-purple-600" />
          <span className="card-title text-purple-950">Viral Genome Database Match</span>
          <span className="text-[10px] bg-purple-100 text-purple-800 font-mono px-1.5 py-0.5 rounded font-normal">
            RefSeq {totalCandidatesEvaluated.toLocaleString()} Genomes
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400 text-[11px]">{searchTimeMs.toFixed(1)}ms</span>
          {abstain ? (
            <span className="badge-warning flex items-center gap-1">
              <AlertTriangle size={12} />
              Abstained
            </span>
          ) : (
            <span className="badge-verified flex items-center gap-1">
              <ShieldCheck size={12} />
              Definitive Match
            </span>
          )}
        </div>
      </div>

      <div className="card-body space-y-4">
        {/* Safety Abstain Banner */}
        {abstain && abstainReason && (
          <div className="flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-200 rounded-md text-amber-900 text-xs">
            <AlertCircle size={16} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="font-semibold text-amber-950">Safety Gating Abstained on Attribution</div>
              <p className="leading-relaxed text-amber-800">{abstainReason}</p>
            </div>
          </div>
        )}

        {/* Primary Closest Genome Hero */}
        {closestMatch ? (
          <div className={`p-4 rounded-lg border transition-all ${
            abstain
              ? 'bg-amber-50/40 border-amber-200'
              : 'bg-white border-purple-200 shadow-xs'
          }`}>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1 flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-medium">
                    {closestMatch.accession}
                  </span>
                  <a
                    href={`https://www.ncbi.nlm.nih.gov/nuccore/${closestMatch.accession}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-purple-600 hover:text-purple-800 flex items-center gap-0.5"
                    title="View NCBI RefSeq record"
                  >
                    <span>NCBI</span>
                    <ExternalLink size={11} />
                  </a>
                  {closestMatch.hasPolyATail && (
                    <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded" title="Genome contains poly-A tail">
                      Poly-A Terminus
                    </span>
                  )}
                  {closestMatch.lowComplexity && (
                    <span className="text-[10px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">
                      Low Complexity Region
                    </span>
                  )}
                </div>

                <h3 className="text-sm font-semibold text-slate-900 leading-snug">
                  {closestMatch.organism}
                </h3>
              </div>

              {/* Score pill */}
              <div className="text-right flex-shrink-0">
                <div className="text-xl font-bold text-purple-700 font-mono">
                  {closestMatch.alignmentScore}
                </div>
                <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                  Smith–Waterman
                </div>
              </div>
            </div>

            {/* Target coordinates bar */}
            <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-slate-50 p-1.5 rounded">
                <span className="text-[10px] text-slate-400 block">Matched Region</span>
                <span className="font-mono text-slate-700 font-medium">
                  bp {closestMatch.targetStart} – {closestMatch.targetEnd}
                </span>
              </div>
              <div className="bg-slate-50 p-1.5 rounded">
                <span className="text-[10px] text-slate-400 block">Shared K-mers</span>
                <span className="font-mono text-slate-700 font-medium">
                  {closestMatch.sharedKmers} hits (k=13)
                </span>
              </div>
              <div className="bg-slate-50 p-1.5 rounded">
                <span className="text-[10px] text-slate-400 block">Query Length</span>
                <span className="font-mono text-slate-700 font-medium">
                  {closestMatch.matchedLength} bp
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-6 text-slate-400 text-xs italic">
            No matching viral genome found above similarity threshold.
          </div>
        )}

        {/* Top-N Candidates Ranked Table */}
        {topCandidates.length > 1 && (
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
              <span>Top Candidate Genomes Evaluated</span>
              <span className="text-[11px] text-slate-400 font-normal">Ranked by SW alignment score</span>
            </div>

            <div className="border border-slate-200 rounded-md overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="py-2 px-2.5 w-12 text-center">Rank</th>
                    <th className="py-2 px-2.5 w-28">Accession</th>
                    <th className="py-2 px-2.5">Organism / Strain</th>
                    <th className="py-2 px-2.5 text-right w-16">K-mers</th>
                    <th className="py-2 px-2.5 text-right w-20">SW Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {topCandidates.map((c: GenomeCandidate) => (
                    <tr
                      key={c.accession}
                      className={c.rank === 1 ? 'bg-purple-50/30 font-medium' : 'hover:bg-slate-50/50'}
                    >
                      <td className="py-2 px-2.5 text-center text-slate-500">{c.rank}</td>
                      <td className="py-2 px-2.5 font-semibold text-purple-700">
                        <a
                          href={`https://www.ncbi.nlm.nih.gov/nuccore/${c.accession}`}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline flex items-center gap-1"
                        >
                          {c.accession}
                        </a>
                      </td>
                      <td className="py-2 px-2.5 font-sans truncate max-w-xs text-slate-800" title={c.organism}>
                        {c.organism}
                      </td>
                      <td className="py-2 px-2.5 text-right text-slate-600">{c.sharedKmers}</td>
                      <td className="py-2 px-2.5 text-right font-bold text-purple-800">
                        {c.alignmentScore}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
