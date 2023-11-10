from __future__ import annotations

import sys

import optuna
from optuna_dashboard._serializer import serialize_attrs
from optuna_dashboard._serializer import serialize_study_detail
from optuna_dashboard._serializer import serialize_study_summary
from optuna_dashboard._storage import get_study_summaries
from optuna_dashboard.preferential import create_study
import pytest


def test_serialize_bytes() -> None:
    serialized = serialize_attrs({"bytes": b"This is a bytes object."})
    assert serialized[0]["value"] == "<binary object>"


def test_serialize_dict() -> None:
    serialized = serialize_attrs(
        {
            "key": {"foo": "bar"},
        }
    )
    assert len(serialized) <= 1


@pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
def test_get_study_detail_is_preferential() -> None:
    storage = optuna.storages.InMemoryStorage()
    study = create_study(n_generate=4, storage=storage)
    study_summaries = get_study_summaries(storage)
    assert len(study_summaries) == 1

    study_summary = study_summaries[0]
    study_detail = serialize_study_detail(
        study_summary, [], study.trials, [], [], [], False, {}, []
    )
    assert study_detail["is_preferential"]


def test_get_study_detail_is_not_preferential() -> None:
    storage = optuna.storages.InMemoryStorage()
    study = optuna.create_study(storage=storage)
    study_summaries = get_study_summaries(storage)
    assert len(study_summaries) == 1

    study_summary = study_summaries[0]
    study_detail = serialize_study_detail(
        study_summary, [], study.trials, [], [], [], False, {}, []
    )
    assert not study_detail["is_preferential"]


@pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
def test_get_study_summary_is_preferential() -> None:
    storage = optuna.storages.InMemoryStorage()
    create_study(n_generate=4, storage=storage)
    study_summaries = get_study_summaries(storage)
    assert len(study_summaries) == 1

    study_summary = serialize_study_summary(study_summaries[0])
    assert study_summary["is_preferential"]


def test_get_study_summary_is_not_preferential() -> None:
    storage = optuna.storages.InMemoryStorage()
    optuna.create_study(storage=storage)
    study_summaries = get_study_summaries(storage)
    assert len(study_summaries) == 1
    study_summary = serialize_study_summary(study_summaries[0])
    assert not study_summary["is_preferential"]
