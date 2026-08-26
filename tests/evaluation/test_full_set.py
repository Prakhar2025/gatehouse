"""Full-set generator: split integrity, strata quotas, determinism (doc 07)."""

from __future__ import annotations

import collections

import pytest

from gatehouse.evaluation.full_set import (
    _BAD_DOMAINS_PLAIN,
    DEV_SEED,
    DEV_SET_SIZE,
    FULL_COUNTS,
    FULL_SET_SIZE,
    HOLDOUT_SET_SIZE,
    check_no_overlap,
    generate_dev_set,
    generate_holdout_set,
)


class TestSplitSizes:
    def test_counts_table_sums_to_full_set(self) -> None:
        assert sum(FULL_COUNTS.values()) == FULL_SET_SIZE

    def test_each_stratum_divides_by_five(self) -> None:
        for name, count in FULL_COUNTS.items():
            assert count % 5 == 0, f"{name} cannot split 80/20 exactly"

    def test_dev_and_holdout_sizes(self) -> None:
        dev = generate_dev_set()
        hold = generate_holdout_set()
        assert len(dev) == DEV_SET_SIZE
        assert len(hold) == HOLDOUT_SET_SIZE

    def test_per_stratum_80_20(self) -> None:
        dev = collections.Counter(c.stratum for c in generate_dev_set())
        hold = collections.Counter(c.stratum for c in generate_holdout_set())
        for name, total in FULL_COUNTS.items():
            assert hold[name] == total // 5
            assert dev[name] == total - total // 5


class TestSplitIntegrity:
    def test_no_text_overlap_between_splits(self) -> None:
        dev = generate_dev_set()
        hold = generate_holdout_set()
        check_no_overlap(dev, hold)  # raises on any shared text

    def test_overlap_detector_fires_on_shared_text(self) -> None:
        from gatehouse.evaluation.schemas import EvalCase

        twin = EvalCase(
            id="twin",
            stratum="kyc_scam",
            lang="en",
            difficulty="easy",
            ground_truth="scam",
            text=generate_dev_set()[0].text,
        )
        with pytest.raises(ValueError, match="overlap"):
            check_no_overlap(generate_dev_set(), [twin])

    def test_reference_ranges_disjoint_by_split(self) -> None:
        dev_refs = {c.text.split()[-1] for c in generate_dev_set() if c.text[-5:].isdigit()}
        # Belt-and-braces: no dev ref token may appear inside any hold-out text.
        hold_texts = [c.text for c in generate_holdout_set()]
        for ref in list(dev_refs)[:50]:
            assert not any(ref in t for t in hold_texts), f"ref {ref} leaked across splits"


class TestDeterminism:
    def test_same_seed_byte_identical(self) -> None:
        a = generate_dev_set(DEV_SEED)
        b = generate_dev_set(DEV_SEED)
        assert [c.model_dump_json() for c in a] == [c.model_dump_json() for c in b]

    def test_different_seed_different_refs(self) -> None:
        a = {c.id: c.text for c in generate_dev_set(seed=1)}
        b = {c.id: c.text for c in generate_holdout_set(seed=2)}
        assert set(a.values()).isdisjoint(b.values())


class TestLabelsAndLanguages:
    def test_ground_truth_matches_stratum_family(self) -> None:
        benign = {
            "legit_bank_offer",
            "delivery_update",
            "govt_notice_legit",
            "family_chatter",
            "newsletter_promo",
            "otp_forward",
            "govt_legit_trap",
        }
        for case in generate_dev_set() + generate_holdout_set():
            expected = "benign" if case.stratum in benign else "scam"
            assert case.ground_truth == expected

    def test_both_languages_present_per_stratum_in_dev(self) -> None:
        langs = collections.defaultdict(set)
        for case in generate_dev_set():
            langs[case.stratum].add(case.lang)
        empty_hi = {name for name, seen in langs.items() if "hi" not in seen}
        assert not empty_hi, f"strata without Hindi coverage: {sorted(empty_hi)}"

    def test_difficulty_tiers_present(self) -> None:
        difficulties = {c.difficulty for c in generate_dev_set()}
        assert {"easy", "medium", "hard"} <= difficulties


class TestSlotHygiene:
    def test_no_unfilled_slots_anywhere(self) -> None:
        for case in generate_dev_set() + generate_holdout_set():
            assert "{" not in case.text and "}" not in case.text

    def test_reserved_example_domains_only(self) -> None:
        banned = _BAD_DOMAINS_PLAIN
        cases = generate_dev_set() + generate_holdout_set()
        scam_texts = [c.text for c in cases if c.ground_truth == "scam"]
        benign_texts = [c.text for c in cases if c.ground_truth == "benign"]
        assert any(any(dom in text for dom in banned) for text in scam_texts), (
            "reserved scam domains must actually appear in the scam texts"
        )
        assert any("[.]" in text for text in scam_texts), (
            "the defanged VPA rendering must also be exercised somewhere"
        )
        for text in benign_texts:
            assert not any(dom in text for dom in banned)
            assert "[.]" not in text
