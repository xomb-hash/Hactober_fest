#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace helixguard {

// Scoring parameters for local alignment
struct ScoringParams {
    int match = 2;
    int mismatch = -1;
    int gap = -1;
};

// Represents a 0-indexed coordinate in the DP matrix
struct Cell {
    size_t row = 0;
    size_t column = 0;
};

// Traceback aligned sequence pair (with '-' denoting indels/gaps)
struct TracebackResult {
    std::string aligned_reference;
    std::string aligned_query;
};

// Complete output of Smith-Waterman local alignment
struct AlignmentResult {
    int alignment_score = 0;
    Cell max_cell;
    std::vector<std::vector<int>> matrix;
    size_t rows = 0;
    size_t columns = 0;
    ScoringParams scoring;
    TracebackResult traceback;
};

// Direction pointers used during dynamic programming traceback
enum class TracebackDir : std::uint8_t {
    STOP = 0,
    DIAG = 1,
    UP = 2,
    LEFT = 3
};

// Normalizes a sequence string to uppercase
std::string normalize_sequence(const std::string& seq);

// Validates sequence characters (ACGT / ACGU) and length limits.
// Returns true if valid, or false with explanation in out_error if provided.
bool is_valid_sequence(const std::string& seq,
                       std::string* out_error = nullptr,
                       size_t max_length = 10000);

// Validates scoring parameters.
// Returns true if valid, or false with explanation in out_error if provided.
bool is_valid_scoring(const ScoringParams& params,
                      std::string* out_error = nullptr);

// Computes Smith-Waterman local alignment for reference and query sequences.
// H[i][j] = max(0, H[i-1][j-1] + sub, H[i-1][j] + gap, H[i][j-1] + gap)
// Sequences are normalized to uppercase.
// Throws std::invalid_argument if inputs fail validation.
AlignmentResult align(const std::string& reference,
                      const std::string& query,
                      const ScoringParams& scoring = ScoringParams{});

} // namespace helixguard
