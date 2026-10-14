import type { AlignmentResult, ScoringParams } from '../types/helixguard';

/**
 * Smith–Waterman local alignment (deterministic).
 * Returns the full DP matrix and traceback alignment strings.
 */
export function smithWaterman(
  reference: string,
  query: string,
  params: ScoringParams
): AlignmentResult {
  const m = reference.length;
  const n = query.length;

  // Build (m+1) x (n+1) matrix
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  let maxVal = 0;
  let maxRow = 0;
  let maxCol = 0;

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const matchScore =
        reference[i - 1] === query[j - 1] ? params.match : params.mismatch;
      const diag = dp[i - 1][j - 1] + matchScore;
      const up = dp[i - 1][j] + params.gap;
      const left = dp[i][j - 1] + params.gap;
      dp[i][j] = Math.max(0, diag, up, left);
      if (dp[i][j] > maxVal) {
        maxVal = dp[i][j];
        maxRow = i;
        maxCol = j;
      }
    }
  }

  // Traceback from max cell
  const alignRef: string[] = [];
  const alignQuery: string[] = [];
  let i = maxRow;
  let j = maxCol;

  while (i > 0 && j > 0 && dp[i][j] > 0) {
    const cur = dp[i][j];
    const matchScore =
      reference[i - 1] === query[j - 1] ? params.match : params.mismatch;
    if (cur === dp[i - 1][j - 1] + matchScore) {
      alignRef.unshift(reference[i - 1]);
      alignQuery.unshift(query[j - 1]);
      i--;
      j--;
    } else if (cur === dp[i - 1][j] + params.gap) {
      alignRef.unshift(reference[i - 1]);
      alignQuery.unshift('-');
      i--;
    } else {
      alignRef.unshift('-');
      alignQuery.unshift(query[j - 1]);
      j--;
    }
  }

  return {
    referenceSequence: reference,
    querySequence: query,
    alignedReference: alignRef.join(''),
    alignedQuery: alignQuery.join(''),
    alignmentScore: maxVal,
    maxScoringCell: { row: maxRow, col: maxCol, value: maxVal },
    dpMatrix: dp,
    scoringParams: params,
    skipped: false,
  };
}

export const DEFAULT_SCORING: ScoringParams = { match: 2, mismatch: -1, gap: -1 };
