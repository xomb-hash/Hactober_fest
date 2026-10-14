#include "test_alignment.hpp"
#include "../alignment.hpp"

#include <cassert>
#include <chrono>
#include <iostream>
#include <string>
#include <vector>

namespace helixguard {
namespace {

int g_tests_passed = 0;
int g_tests_failed = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "[-] ASSERTION FAILED: " << msg << " (" << __FILE__ << ":" << __LINE__ << ")" << std::endl; \
            g_tests_failed++; \
            return; \
        } \
    } while (0)

#define RUN_TEST(fn) \
    do { \
        int before_failed = g_tests_failed; \
        std::cout << "[RUN]  " << #fn << "..." << std::endl; \
        fn(); \
        if (g_tests_failed == before_failed) { \
            std::cout << "[PASS] " << #fn << std::endl; \
            g_tests_passed++; \
        } else { \
            std::cerr << "[FAIL] " << #fn << std::endl; \
        } \
    } while (0)

// 1. Known score for exact match
void test_exact_match() {
    ScoringParams scoring{2, -1, -1};

    // 4-base exact match
    auto res1 = align("ACGT", "ACGT", scoring);
    TEST_ASSERT(res1.alignment_score == 8, "ACGT exact match score must be 8");
    TEST_ASSERT(res1.max_cell.row == 4 && res1.max_cell.column == 4, "Max cell should be {4, 4}");
    TEST_ASSERT(res1.traceback.aligned_reference == "ACGT", "Aligned ref should be ACGT");
    TEST_ASSERT(res1.traceback.aligned_query == "ACGT", "Aligned query should be ACGT");

    // 8-base exact match
    auto res2 = align("ATCGATCG", "ATCGATCG", scoring);
    TEST_ASSERT(res2.alignment_score == 16, "ATCGATCG exact match score must be 16");
    TEST_ASSERT(res2.max_cell.row == 8 && res2.max_cell.column == 8, "Max cell should be {8, 8}");
    TEST_ASSERT(res2.traceback.aligned_reference == "ATCGATCG", "Aligned ref should be ATCGATCG");
    TEST_ASSERT(res2.traceback.aligned_query == "ATCGATCG", "Aligned query should be ATCGATCG");

    // Exact match with local substring in longer sequences
    auto res3 = align("GGGATCGATCGTTT", "CCCATCGATCGAAA", scoring);
    TEST_ASSERT(res3.alignment_score == 16, "Local exact match score must be 16");
    TEST_ASSERT(res3.traceback.aligned_reference == "ATCGATCG", "Local aligned ref should be ATCGATCG");
    TEST_ASSERT(res3.traceback.aligned_query == "ATCGATCG", "Local aligned query should be ATCGATCG");
}

// 2. Known score for mismatches
void test_mismatches() {
    ScoringParams scoring{2, -1, -1};

    // Reference example: ATCGATCG vs ATCGTTCG (single substitution at pos 4: A vs T)
    auto res = align("ATCGATCG", "ATCGTTCG", scoring);
    TEST_ASSERT(res.alignment_score == 13, "Score for ATCGATCG vs ATCGTTCG must be 13");
    TEST_ASSERT(res.max_cell.row == 8 && res.max_cell.column == 8, "Max cell should be {8, 8}");
    TEST_ASSERT(res.traceback.aligned_reference == "ATCGATCG", "Aligned ref must be ATCGATCG");
    TEST_ASSERT(res.traceback.aligned_query == "ATCGTTCG", "Aligned query must be ATCGTTCG");

    // All mismatches
    auto res_all_mismatch = align("AAAA", "CCCC", scoring);
    TEST_ASSERT(res_all_mismatch.alignment_score == 0, "Complete mismatch score must be 0");
    TEST_ASSERT(res_all_mismatch.traceback.aligned_reference.empty(), "Aligned ref must be empty for 0 score");
    TEST_ASSERT(res_all_mismatch.traceback.aligned_query.empty(), "Aligned query must be empty for 0 score");

    // Multiple internal mismatches flanked by matches
    // 10 matches (10*2 = 20) and 2 mismatches (2*-1 = -2) -> score 18
    auto res_multi = align("ACGTACGTACGT", "ACCTACGTTCGT", scoring);
    TEST_ASSERT(res_multi.alignment_score == 18, "Score with 2 mismatches should be 18");
    TEST_ASSERT(res_multi.max_cell.row == 12 && res_multi.max_cell.column == 12, "Max cell should be {12, 12}");
    TEST_ASSERT(res_multi.traceback.aligned_reference == "ACGTACGTACGT", "Ref aligned matches");
    TEST_ASSERT(res_multi.traceback.aligned_query == "ACCTACGTTCGT", "Query aligned matches");
}

// 3. Empty sequences
void test_empty_sequences() {
    std::string err;
    TEST_ASSERT(!is_valid_sequence("", &err), "Empty sequence must be invalid");
    TEST_ASSERT(!err.empty(), "Error message must be set for empty sequence");

    bool threw = false;
    try {
        align("", "ATCG");
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    TEST_ASSERT(threw, "align() must throw std::invalid_argument for empty reference");

    threw = false;
    try {
        align("ATCG", "");
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    TEST_ASSERT(threw, "align() must throw std::invalid_argument for empty query");

    threw = false;
    try {
        align("", "");
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    TEST_ASSERT(threw, "align() must throw std::invalid_argument for both empty");
}

// 4. Single character sequences
void test_single_character() {
    ScoringParams scoring{2, -1, -1};

    // Single match
    auto res_match = align("A", "A", scoring);
    TEST_ASSERT(res_match.alignment_score == 2, "Single char match score must be 2");
    TEST_ASSERT(res_match.rows == 2 && res_match.columns == 2, "Matrix dims must be 2x2");
    TEST_ASSERT(res_match.max_cell.row == 1 && res_match.max_cell.column == 1, "Max cell must be {1, 1}");
    TEST_ASSERT(res_match.traceback.aligned_reference == "A", "Aligned ref must be A");
    TEST_ASSERT(res_match.traceback.aligned_query == "A", "Aligned query must be A");

    // Single mismatch
    auto res_mismatch = align("A", "G", scoring);
    TEST_ASSERT(res_mismatch.alignment_score == 0, "Single char mismatch score must be 0");
    TEST_ASSERT(res_mismatch.rows == 2 && res_mismatch.columns == 2, "Matrix dims must be 2x2");
    TEST_ASSERT(res_mismatch.traceback.aligned_reference.empty(), "Traceback empty on score 0");

    // Single char against multi char
    auto res_sub = align("T", "ACGT", scoring);
    TEST_ASSERT(res_sub.alignment_score == 2, "Single char sub-match score must be 2");
    TEST_ASSERT(res_sub.max_cell.row == 1 && res_sub.max_cell.column == 4, "Max cell should be at col 4");
    TEST_ASSERT(res_sub.traceback.aligned_reference == "T", "Aligned ref must be T");
    TEST_ASSERT(res_sub.traceback.aligned_query == "T", "Aligned query must be T");
}

// 5. Gap handling (indels)
void test_gap_handling() {
    ScoringParams scoring{2, -1, -1};

    // Insertion in reference / deletion in query
    // ref: ATCGGATCG vs qry: ATCGATCG
    auto res_del = align("ATCGGATCG", "ATCGATCG", scoring);
    TEST_ASSERT(res_del.alignment_score == 15, "Score for deletion should be 15");
    TEST_ASSERT(res_del.traceback.aligned_reference == "ATCGGATCG", "Aligned ref");
    TEST_ASSERT(res_del.traceback.aligned_query == "ATC-GATCG" || res_del.traceback.aligned_query == "ATCG-ATCG",
                "Query should contain a gap '-'");

    // Deletion in reference / insertion in query
    auto res_ins = align("ATCGATCG", "ATCGGATCG", scoring);
    TEST_ASSERT(res_ins.alignment_score == 15, "Score for insertion should be 15");
    TEST_ASSERT(res_ins.traceback.aligned_reference == "ATC-GATCG" || res_ins.traceback.aligned_reference == "ATCG-ATCG",
                "Ref should contain a gap '-'");
    TEST_ASSERT(res_ins.traceback.aligned_query == "ATCGGATCG", "Aligned query");

    // Multiple internal gaps
    auto res_gaps = align("AAACCCGGG", "AAAGGG", scoring);
    TEST_ASSERT(res_gaps.alignment_score > 0, "Gapped alignment score must be positive");
    TEST_ASSERT(res_gaps.traceback.aligned_query.find('-') != std::string::npos,
                "Traceback query should have gaps");
}

// 6. Matrix dimensions check
void test_matrix_dimensions() {
    ScoringParams scoring{2, -1, -1};

    std::string ref = "ACGTA";      // length 5
    std::string qry = "CGTACTG";    // length 7

    auto res = align(ref, qry, scoring);
    TEST_ASSERT(res.rows == 6, "Rows must be ref.length() + 1 = 6");
    TEST_ASSERT(res.columns == 8, "Columns must be qry.length() + 1 = 8");
    TEST_ASSERT(res.matrix.size() == 6, "Matrix row size must match rows");

    for (size_t i = 0; i < res.rows; ++i) {
        TEST_ASSERT(res.matrix[i].size() == 8, "Each matrix row must have length == columns");
    }

    // First row must be entirely zero
    for (size_t j = 0; j < res.columns; ++j) {
        TEST_ASSERT(res.matrix[0][j] == 0, "First row must be zero");
    }

    // First column must be entirely zero
    for (size_t i = 0; i < res.rows; ++i) {
        TEST_ASSERT(res.matrix[i][0] == 0, "First column must be zero");
    }
}

// 7. Invalid characters rejected
void test_invalid_characters() {
    std::string err;

    // Numbers, special characters, whitespace
    TEST_ASSERT(!is_valid_sequence("ACGT123", &err), "Numbers should be rejected");
    TEST_ASSERT(!is_valid_sequence("AC GT", &err), "Spaces should be rejected");
    TEST_ASSERT(!is_valid_sequence("ACGT-ACGT", &err), "Dashes in input should be rejected");
    TEST_ASSERT(!is_valid_sequence("ACGTN", &err), "Ambiguity IUPAC N should be rejected");
    TEST_ASSERT(!is_valid_sequence("XYZ", &err), "Non-nucleotides should be rejected");

    // RNA 'U' is accepted
    TEST_ASSERT(is_valid_sequence("ACGU", &err), "RNA sequence ACGU should be valid");
    auto res_rna = align("ACGU", "ACGU");
    TEST_ASSERT(res_rna.alignment_score == 8, "RNA match should score 8");

    // Case normalization: lowercase is accepted
    TEST_ASSERT(is_valid_sequence("acgt", &err), "Lowercase acgt should be valid");
    auto res_lower = align("acgt", "ACGT");
    TEST_ASSERT(res_lower.alignment_score == 8, "Lowercase aligned with uppercase should score 8");

    // Throw check
    bool threw = false;
    try {
        align("ACGTX", "ACGT");
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    TEST_ASSERT(threw, "align() must throw for invalid characters");
}

// 8. Large input handling & limits
void test_large_input() {
    std::string err;

    // Limit check: 10001 characters must be rejected
    std::string too_long(10001, 'A');
    TEST_ASSERT(!is_valid_sequence(too_long, &err), "Sequence > 10000 must be rejected");
    TEST_ASSERT(err.find("exceeds maximum allowed limit") != std::string::npos, "Correct error message");

    bool threw = false;
    try {
        align(too_long, "ACGT");
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    TEST_ASSERT(threw, "align() must throw for sequence > 10000");

    // Length 10000 boundary is valid
    std::string max_valid(10000, 'A');
    TEST_ASSERT(is_valid_sequence(max_valid, &err), "Sequence == 10000 should be valid");

    // Performance test: 500x500 alignment
    std::string seq_a;
    std::string seq_b;
    seq_a.reserve(500);
    seq_b.reserve(500);
    const char bases[] = "ACGT";
    for (size_t i = 0; i < 500; ++i) {
        seq_a.push_back(bases[i % 4]);
        seq_b.push_back(bases[(i + 1) % 4]);
    }

    auto start = std::chrono::high_resolution_clock::now();
    auto res = align(seq_a, seq_b);
    auto end = std::chrono::high_resolution_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    TEST_ASSERT(res.rows == 501 && res.columns == 501, "500x500 dimensions correct");
    std::cout << "      (500x500 alignment completed in " << ms << " ms)" << std::endl;
    TEST_ASSERT(ms < 1000, "500x500 alignment should complete in under 1 second");
}

// 9. Scoring parameters validation
void test_scoring_parameters() {
    std::string err;

    // match <= 0
    ScoringParams bad1{0, -1, -1};
    TEST_ASSERT(!is_valid_scoring(bad1, &err), "Match <= 0 must be invalid");

    // mismatch >= match
    ScoringParams bad2{2, 2, -1};
    TEST_ASSERT(!is_valid_scoring(bad2, &err), "Mismatch >= match must be invalid");

    // gap >= match
    ScoringParams bad3{2, -1, 3};
    TEST_ASSERT(!is_valid_scoring(bad3, &err), "Gap >= match must be invalid");

    // Custom valid scoring
    ScoringParams custom{3, -2, -2};
    TEST_ASSERT(is_valid_scoring(custom, &err), "Custom scoring should be valid");
    auto res = align("ACGT", "ACGT", custom);
    TEST_ASSERT(res.alignment_score == 12, "ACGT with match=3 should score 12");
}

} // anonymous namespace

int run_alignment_tests() {
    g_tests_passed = 0;
    g_tests_failed = 0;

    std::cout << "========================================" << std::endl;
    std::cout << "  HelixGuard Smith-Waterman Unit Tests  " << std::endl;
    std::cout << "========================================" << std::endl;

    RUN_TEST(test_exact_match);
    RUN_TEST(test_mismatches);
    RUN_TEST(test_empty_sequences);
    RUN_TEST(test_single_character);
    RUN_TEST(test_gap_handling);
    RUN_TEST(test_matrix_dimensions);
    RUN_TEST(test_invalid_characters);
    RUN_TEST(test_large_input);
    RUN_TEST(test_scoring_parameters);

    std::cout << "========================================" << std::endl;
    std::cout << "Results: " << g_tests_passed << " passed, " << g_tests_failed << " failed." << std::endl;
    std::cout << "========================================" << std::endl;

    return (g_tests_failed == 0) ? 0 : 1;
}

} // namespace helixguard

#ifdef STANDALONE_TEST_RUNNER
int main() {
    return helixguard::run_alignment_tests();
}
#endif
