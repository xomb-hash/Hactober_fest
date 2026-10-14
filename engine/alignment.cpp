#include "alignment.hpp"

#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace helixguard {

std::string normalize_sequence(const std::string& seq) {
    std::string normalized;
    normalized.reserve(seq.size());
    for (char c : seq) {
        normalized.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(c))));
    }
    return normalized;
}

bool is_valid_sequence(const std::string& seq,
                       std::string* out_error,
                       size_t max_length) {
    if (seq.empty()) {
        if (out_error) {
            *out_error = "Sequence cannot be empty.";
        }
        return false;
    }

    if (seq.size() > max_length) {
        if (out_error) {
            *out_error = "Sequence length (" + std::to_string(seq.size()) +
                         ") exceeds maximum allowed limit of " + std::to_string(max_length) + ".";
        }
        return false;
    }

    for (size_t i = 0; i < seq.size(); ++i) {
        char c = static_cast<char>(std::toupper(static_cast<unsigned char>(seq[i])));
        if (c != 'A' && c != 'C' && c != 'G' && c != 'T' && c != 'U') {
            if (out_error) {
                *out_error = "Invalid character '" + std::string(1, seq[i]) + "' at index " +
                             std::to_string(i) + ". Only A, C, G, T, U are permitted.";
            }
            return false;
        }
    }

    return true;
}

bool is_valid_scoring(const ScoringParams& params,
                      std::string* out_error) {
    if (params.match <= 0) {
        if (out_error) {
            *out_error = "Match score must be strictly positive (got " +
                         std::to_string(params.match) + ").";
        }
        return false;
    }

    if (params.mismatch >= params.match) {
        if (out_error) {
            *out_error = "Mismatch penalty (" + std::to_string(params.mismatch) +
                         ") must be strictly less than match score (" +
                         std::to_string(params.match) + ").";
        }
        return false;
    }

    if (params.gap >= params.match) {
        if (out_error) {
            *out_error = "Gap penalty (" + std::to_string(params.gap) +
                         ") must be strictly less than match score (" +
                         std::to_string(params.match) + ").";
        }
        return false;
    }

    return true;
}

AlignmentResult align(const std::string& reference,
                      const std::string& query,
                      const ScoringParams& scoring) {
    std::string err;
    if (!is_valid_sequence(reference, &err)) {
        throw std::invalid_argument("Reference sequence invalid: " + err);
    }
    if (!is_valid_sequence(query, &err)) {
        throw std::invalid_argument("Query sequence invalid: " + err);
    }
    if (!is_valid_scoring(scoring, &err)) {
        throw std::invalid_argument("Scoring parameters invalid: " + err);
    }

    std::string ref_norm = normalize_sequence(reference);
    std::string qry_norm = normalize_sequence(query);

    const size_t m = ref_norm.size();
    const size_t n = qry_norm.size();

    AlignmentResult result;
    result.rows = m + 1;
    result.columns = n + 1;
    result.scoring = scoring;
    result.matrix.assign(result.rows, std::vector<int>(result.columns, 0));

    // Direction matrix for traceback
    std::vector<std::vector<TracebackDir>> trace(
        result.rows,
        std::vector<TracebackDir>(result.columns, TracebackDir::STOP)
    );

    int max_score = 0;
    Cell max_cell = {0, 0};

    for (size_t i = 1; i <= m; ++i) {
        const char r_char = ref_norm[i - 1];
        for (size_t j = 1; j <= n; ++j) {
            const char q_char = qry_norm[j - 1];
            const int sub_score = (r_char == q_char) ? scoring.match : scoring.mismatch;

            const int diag = result.matrix[i - 1][j - 1] + sub_score;
            const int up   = result.matrix[i - 1][j] + scoring.gap;
            const int left = result.matrix[i][j - 1] + scoring.gap;

            int best = 0;
            TracebackDir dir = TracebackDir::STOP;

            if (diag > best) {
                best = diag;
                dir = TracebackDir::DIAG;
            }
            if (up > best) {
                best = up;
                dir = TracebackDir::UP;
            }
            if (left > best) {
                best = left;
                dir = TracebackDir::LEFT;
            }

            result.matrix[i][j] = best;
            trace[i][j] = dir;

            if (best > max_score) {
                max_score = best;
                max_cell = {i, j};
            }
        }
    }

    result.alignment_score = max_score;
    result.max_cell = max_cell;

    // Traceback starting from the max-scoring cell back to a cell with score 0
    std::string aln_ref;
    std::string aln_qry;

    if (max_score > 0) {
        size_t curr_i = max_cell.row;
        size_t curr_j = max_cell.column;

        while (curr_i > 0 && curr_j > 0 && result.matrix[curr_i][curr_j] > 0) {
            TracebackDir dir = trace[curr_i][curr_j];
            if (dir == TracebackDir::DIAG) {
                aln_ref.push_back(ref_norm[curr_i - 1]);
                aln_qry.push_back(qry_norm[curr_j - 1]);
                --curr_i;
                --curr_j;
            } else if (dir == TracebackDir::UP) {
                aln_ref.push_back(ref_norm[curr_i - 1]);
                aln_qry.push_back('-');
                --curr_i;
            } else if (dir == TracebackDir::LEFT) {
                aln_ref.push_back('-');
                aln_qry.push_back(qry_norm[curr_j - 1]);
                --curr_j;
            } else {
                break;
            }
        }

        std::reverse(aln_ref.begin(), aln_ref.end());
        std::reverse(aln_qry.begin(), aln_qry.end());
    }

    result.traceback.aligned_reference = aln_ref;
    result.traceback.aligned_query = aln_qry;

    return result;
}

} // namespace helixguard
