import pandas as pd
import pytest
from rapidfuzz.distance import DamerauLevenshtein, Levenshtein

from analysis import compare, load_data
from normalizer import METHODS, Normalizer


@pytest.fixture(scope="module")
def normalizer():
    return Normalizer()


@pytest.mark.parametrize("method", METHODS)
def test_empty_and_codes(normalizer, method):
    output = normalizer.normalize_many(["", "CLP IHM OS 50cv 220V RO001", "xyzqk"], method)
    assert output == ["", "clp ihm os 50cv 220v ro001", "xyzqk"]


def test_regex_boundaries(normalizer):
    assert normalizer.normalize_many(["  MOT.\n c/ temp. alta s/ press. n parte  "], "Regex") == [
        "motor com temperatura alta sem pressão não parte"
    ]
    assert normalizer.normalize_many(["motor motorizado sc/ pressão"], "Regex") == [
        "motor motorizado sc/ pressão"
    ]


@pytest.mark.parametrize("method", list(METHODS)[1:])
def test_portuguese_dictionary_outside_domain(normalizer, method):
    assert "afericao" not in normalizer.domain
    assert normalizer.normalize_many(["afericao relatorio"], method) == ["aferição relatório"]
    assert normalizer.normalize_many(["cadeira perto da bomba"], method) == [
        "cadeira perto da bomba"
    ]


def test_exact_dictionary_and_accents(normalizer):
    assert normalizer.normalize_many(["boma com flga no mancl e ruiod"], "Dicionário") == [
        "bomba com folga no mancal e ruído"
    ]
    assert normalizer.normalize_many(["NA\u0303O abre a VA\u0301LVULA"], "Dicionário") == [
        "não abre a válvula"
    ]


def test_transposition_and_edit_limit(normalizer):
    assert Levenshtein.distance("macnal", "mancal") == 2
    assert DamerauLevenshtein.distance("macnal", "mancal") == 1
    assert normalizer.normalize_many(["macnal"], "Damerau–Levenshtein", 1) == ["mancal"]
    assert normalizer.normalize_many(["macnal"], "Levenshtein", 1) != ["mancal"]
    assert normalizer.normalize_many(["mancl"], "Levenshtein") == ["mancal"]


def test_validation(normalizer):
    with pytest.raises(ValueError):
        normalizer.normalize_many(["texto"], "outro")
    with pytest.raises(ValueError):
        normalizer.normalize_many(["texto"], "Levenshtein", 3)
    with pytest.raises(ValueError):
        normalizer.normalize_many(["texto"], "Jaro–Winkler", threshold=0.3)
    with pytest.raises(TypeError):
        normalizer.normalize_many([None], "Regex")


def test_dataset_and_comparison_keep_original(normalizer):
    data = load_data()
    assert len(data) == 3000
    original = data.head(3).copy()
    result, metrics = compare(original, normalizer)
    pd.testing.assert_frame_equal(result[original.columns], original)
    assert set(METHODS) <= set(result.columns)
    assert len(metrics) == 5
    assert metrics["Tempo do lote (ms)"].ge(0).all()
