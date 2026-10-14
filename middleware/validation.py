"""
Validation logic for genomic sequences.
Enforces strict alphabet rules, length bounds, and prohibits silent U <-> T conversions.
"""

from typing import Tuple, List, Optional, Set

# Standard nucleotide sets
DNA_STANDARD: Set[str] = {"A", "C", "G", "T"}
RNA_STANDARD: Set[str] = {"A", "C", "G", "U"}

# IUPAC ambiguity codes
# R = A/G, Y = C/T(U), S = G/C, W = A/T(U), K = G/T(U), M = A/C
# B = C/G/T(U), D = A/G/T(U), H = A/C/T(U), V = A/C/G, N = any
IUPAC_AMBIGUITY: Set[str] = {"R", "Y", "S", "W", "K", "M", "B", "D", "H", "V", "N"}
DNA_IUPAC: Set[str] = DNA_STANDARD | IUPAC_AMBIGUITY
RNA_IUPAC: Set[str] = RNA_STANDARD | IUPAC_AMBIGUITY

MAX_SEQUENCE_LENGTH = 100_000


def validate_alphabet(
    sequence: str,
    alphabet: str = "DNA",
    allow_iupac: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validates that every character in the sequence belongs strictly to the expected alphabet.
    
    IMPORTANT:
    - Never silently convert U <-> T.
    - If alphabet is DNA, 'U' is considered an invalid character.
    - If alphabet is RNA, 'T' is considered an invalid character.
    - Preserves deterministic reporting of invalid characters found.
    """
    if not sequence:
        return True, []

    alphabet_upper = alphabet.upper()
    if alphabet_upper == "DNA":
        valid_set = DNA_IUPAC if allow_iupac else DNA_STANDARD
    elif alphabet_upper == "RNA":
        valid_set = RNA_IUPAC if allow_iupac else RNA_STANDARD
    else:
        raise ValueError(f"Unsupported alphabet: {alphabet}. Supported: 'DNA', 'RNA'.")

    invalid_chars: List[str] = []
    seen_invalid: Set[str] = set()

    for ch in sequence:
        ch_upper = ch.upper()
        if ch_upper not in valid_set:
            if ch not in seen_invalid:
                seen_invalid.add(ch)
                invalid_chars.append(ch)

    return (len(invalid_chars) == 0, invalid_chars)


def validate_sequence_input(
    sequence: Optional[str],
    max_length: int = MAX_SEQUENCE_LENGTH
) -> Tuple[bool, Optional[str]]:
    """
    Validates structural properties of a sequence string (presence, non-empty, length limits).
    """
    if sequence is None or not sequence.strip():
        return False, "EMPTY_SEQUENCE"

    clean_len = len(sequence.strip())
    if clean_len > max_length:
        return False, f"SEQUENCE_EXCEEDS_MAX_LENGTH_{max_length}"

    return True, None


def validate_reference_sequence(
    sequence: Optional[str],
    alphabet: str = "DNA",
    allow_iupac: bool = False,
    max_length: int = MAX_SEQUENCE_LENGTH
) -> Tuple[bool, Optional[str]]:
    """
    Validates a user-supplied reference sequence.
    Ensures non-empty, within limits, and contains only characters in the specified alphabet.
    """
    valid_struct, err = validate_sequence_input(sequence, max_length=max_length)
    if not valid_struct:
        return False, err

    assert sequence is not None
    valid_alpha, invalid_chars = validate_alphabet(
        sequence.strip(),
        alphabet=alphabet,
        allow_iupac=allow_iupac
    )
    if not valid_alpha:
        return False, f"INVALID_ALPHABET_CHARS: {','.join(invalid_chars)} (expected {alphabet})"

    return True, None
