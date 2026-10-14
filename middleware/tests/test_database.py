"""
Unit tests for Genome Database, k-mer prefiltering, poly-A tail handling,
and candidate ranking with Smith-Waterman.
"""

import unittest
import tempfile
import os
from fastapi.testclient import TestClient

from middleware.main import app
from middleware.database import (
    GenomeRecord,
    GenomeDatabase,
    compute_sequence_complexity,
    parse_fna_records,
)

client = TestClient(app)

SAMPLE_MULTI_FASTA = """\
>NC_008987.1 Hyposoter fugitivus ichnovirus DNA, segment D2, complete sequence
TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATGAAACTAAACATATTAAACACAACCATTTAT
TTGAATCTAAGGAACACTATAAACCATTTACCGACATTAACACTAATTGGATTTAGCTGCACCAGAGCCGGAACCACTGA
TGTTGCGCGCCGAGTCCAGCAGCATTTCTGTGTCCGTACGTTCACCCATGGAATAATATTCCACGATGTCCGGATTGTCT
>NC_023162.1 Carp picornavirus 1 isolate F37/06, complete genome
AGCTACAGGAAAGAGAGAGATAATCACAGCACATAAATACAACTACAGAAGAGAGCCTTT
GTAGGTCATCTGTAAATTCAGTGGTTCATCATAGCAACATTTAGTAACTTGTAGCAGTTT
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
>NC_032097.1 Desmodus rotundus parvovirus strain DRA25, complete cds
CAGCGCCCCCGCCCTCCGGATGCGGGCTGGGCCAATTAGCAACGTAGGAAATGTGACGTC
GATGCTGACGTACGTATCGTAGCTAGCTAGCTAGCGATCGATCGATCGATCGATCGATCG
>NC_999999.1 Synthetic close twin A, complete sequence
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
>NC_999998.1 Synthetic close twin B, complete sequence
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCT
"""


class TestGenomeDatabaseParser(unittest.TestCase):
    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile("w", delete=False, suffix=".fna")
        self.tmp_file.write(SAMPLE_MULTI_FASTA)
        self.tmp_file.close()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.remove(self.tmp_file.name)

    def test_parse_headers_accession_and_organism(self):
        records = parse_fna_records(self.tmp_file.name)
        self.assertEqual(len(records), 5)

        r0 = records[0]
        self.assertEqual(r0.accession, "NC_008987.1")
        self.assertEqual(r0.organism, "Hyposoter fugitivus ichnovirus DNA, segment D2, complete sequence")
        self.assertFalse(r0.has_poly_a_tail)

        r1 = records[1]
        self.assertEqual(r1.accession, "NC_023162.1")
        self.assertEqual(r1.organism, "Carp picornavirus 1 isolate F37/06, complete genome")
        self.assertTrue(r1.has_poly_a_tail)

    def test_wrapped_lines_joined(self):
        records = parse_fna_records(self.tmp_file.name)
        r0 = records[0]
        # Should be single contiguous string
        self.assertNotIn("\n", r0.sequence)
        self.assertNotIn("\r", r0.sequence)
        self.assertTrue(r0.length > 80)
        self.assertTrue(r0.sequence.startswith("TTACCTGCACAGCTCTGCAT"))

    def test_low_complexity_poly_a_detection(self):
        poly_a = "A" * 30
        is_low, entropy, max_freq = compute_sequence_complexity(poly_a)
        self.assertTrue(is_low)
        self.assertEqual(max_freq, 1.0)
        self.assertAlmostEqual(entropy, 0.0, places=2)

        normal_seq = "AGCTACAGGAAAGAGAGAGATAATCACAGCACATAAATACAACTACAGA"
        is_low_norm, entropy_norm, max_freq_norm = compute_sequence_complexity(normal_seq)
        self.assertFalse(is_low_norm)
        self.assertTrue(entropy_norm > 1.2)


class TestGenomeDatabaseSearch(unittest.TestCase):
    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile("w", delete=False, suffix=".fna")
        self.tmp_file.write(SAMPLE_MULTI_FASTA)
        self.tmp_file.close()

        self.db = GenomeDatabase(k=11, step=8)
        self.db.load(self.tmp_file.name, use_cache=False)

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.remove(self.tmp_file.name)

    def test_prefilter_identifies_correct_genome(self):
        # Query from Desmodus rotundus parvovirus
        query = "CAGCGCCCCCGCCCTCCGGATGCGGGCTGGGCCAATTAGCAAC"
        hits = self.db.prefilter(query, top_n=3)
        self.assertTrue(len(hits) > 0)
        top_rec = self.db.records[hits[0][0]]
        self.assertEqual(top_rec.accession, "NC_032097.1")

    def test_search_and_rank_success(self):
        query = "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATG"
        resp = self.db.identify_closest_genome(query, top_k=3)
        self.assertEqual(resp.status, "success")
        self.assertFalse(resp.abstain)
        self.assertIsNotNone(resp.closest_match)
        self.assertEqual(resp.closest_match.accession, "NC_008987.1")
        self.assertIn("Hyposoter fugitivus ichnovirus", resp.closest_match.organism)
        self.assertTrue(resp.closest_match.alignment_score > 50)

    def test_poly_a_query_abstains_with_low_complexity_flag(self):
        poly_a_query = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        resp = self.db.identify_closest_genome(poly_a_query, top_k=3)
        self.assertTrue(resp.abstain)
        self.assertEqual(resp.status, "abstained")
        self.assertIn("POLY_A", resp.abstain_reason)

    def test_ambiguous_close_scores_abstains(self):
        # Query identical to both Synthetic Twin A and Twin B except 1 base
        query = "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"
        resp = self.db.identify_closest_genome(query, top_k=3, score_margin_threshold=0.05)
        # Scores between Twin A and Twin B will be nearly tied
        self.assertTrue(resp.abstain)
        self.assertIn("AMBIGUOUS_GENOMIC_MATCH", resp.abstain_reason)


class TestGenomeIdentificationEndpoints(unittest.TestCase):
    def test_identify_genome_endpoint_valid_query(self):
        # Test query from Ichnovirus
        query = "TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATG"
        resp = client.post(
            "/identify-genome",
            json={"query_sequence": query, "top_k": 3}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["status"], ["success", "abstained"])
        self.assertTrue(len(data["top_candidates"]) > 0)
        self.assertEqual(data["query_length"], len(query))

    def test_extract_and_identify_endpoint(self):
        doc = (
            "CLINICAL VIROLOGY SEQUENCING REPORT\n"
            "Patient: SYN-VIR-01\n"
            "Observed sequence: TTACCTGCACAGCTCTGCATAGTCCTACACTGATACGGATGAAAGAAATG\n"
            "Status: Validated\n"
        )
        resp = client.post(
            "/extract-and-identify",
            json={
                "document_text": doc,
                "field_type": "Observed sequence",
                "use_ai": False,
                "top_k": 3,
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["extraction"]["validation_status"], "verified")
        self.assertTrue(data["extraction"]["source_match"])
        self.assertIsNotNone(data["identification"])
        self.assertIsNotNone(data["closest_organism"])
        self.assertIn("Hyposoter fugitivus ichnovirus", data["closest_organism"])
