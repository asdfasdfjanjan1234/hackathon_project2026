import numpy as np

from wattcast import classify


def test_scores_counts_and_f1():
    actual = np.array([True, True, False, False, False])
    predicted = np.array([True, False, True, False, False])
    s = classify.scores(actual, predicted)
    assert (s["tp"], s["fp"], s["fn"], s["tn"]) == (1, 1, 1, 2)
    assert s["accuracy"] == 0.6 and s["precision"] == 0.5 and s["recall"] == 0.5 and s["f1"] == 0.5


def test_never_in_use_has_no_precision_and_zero_f1():
    """A model that never forecasts "in use" gets the always-idle accuracy, no precision and F1 0."""
    s = classify.scores(np.array([True, False, False, False]), np.zeros(4, bool))
    assert s["accuracy"] == 0.75 and s["precision"] is None and s["recall"] == 0 and s["f1"] == 0


def test_nothing_in_use_anywhere_is_undefined():
    s = classify.scores(np.zeros(3, bool), np.zeros(3, bool))
    assert s["accuracy"] == 1 and s["precision"] is None and s["recall"] is None and s["f1"] is None


def test_pooled_adds_counts():
    a = classify.from_counts(1, 0, 1, 2)
    b = classify.from_counts(0, 1, 0, 3)
    assert classify.pooled([a, b]) == classify.from_counts(1, 1, 1, 5)
