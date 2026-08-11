import pandas as pd

from src.validation.common_rules import (
    is_non_negative,
    is_unique,
    not_null,
    split_valid_invalid,
)


def test_not_null():
    df = pd.DataFrame({"a": [1, None, 3]})
    assert not_null(df, "a").tolist() == [True, False, True]


def test_is_unique():
    df = pd.DataFrame({"a": [1, 2, 2, 3]})
    assert is_unique(df, "a").tolist() == [True, True, False, True]


def test_is_non_negative():
    df = pd.DataFrame({"a": [-1, 0, 5]})
    assert is_non_negative(df, "a").tolist() == [False, True, True]


def test_split_valid_invalid():
    df = pd.DataFrame({"a": [1, -1, 2]})
    mask = is_non_negative(df, "a")
    valid, rejected = split_valid_invalid(df, mask)
    assert len(valid) == 2
    assert len(rejected) == 1