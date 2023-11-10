from __future__ import annotations

import json
import sys
from unittest import TestCase

import optuna
from optuna import get_all_study_summaries
from optuna.study import StudyDirection
from optuna_dashboard._app import create_app
from optuna_dashboard._app import create_new_study
from optuna_dashboard._preference_setting import register_preference_feedback_component
from optuna_dashboard._preferential_history import NewHistory
from optuna_dashboard._preferential_history import remove_history
from optuna_dashboard._preferential_history import report_history
from optuna_dashboard._serializer import serialize_preference_history
from optuna_dashboard.preferential import create_study
import pytest

from .wsgi_client import send_request


def objective(trial: optuna.trial.Trial) -> float:
    x = trial.suggest_float("x", -1, 1)
    return x


class APITestCase(TestCase):
    def test_get_study_summaries(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        create_new_study(storage, "foo1", [StudyDirection.MINIMIZE])
        create_new_study(storage, "foo2", [StudyDirection.MINIMIZE])

        app = create_app(storage)
        status, _, body = send_request(
            app,
            "/api/studies/",
            "GET",
            content_type="application/json",
        )
        self.assertEqual(status, 200)
        study_summaries = json.loads(body)["study_summaries"]
        self.assertEqual(len(study_summaries), 2)

    def test_get_study_details_without_after_param(self) -> None:
        study = optuna.create_study()
        study_id = study._study_id
        study.optimize(objective, n_trials=2)
        app = create_app(study._storage)

        status, _, body = send_request(
            app,
            f"/api/studies/{study_id}",
            "GET",
            content_type="application/json",
        )
        self.assertEqual(status, 200)
        all_trials = json.loads(body)["trials"]
        self.assertEqual(len(all_trials), 2)

    def test_get_study_details_with_after_param_partial(self) -> None:
        study = optuna.create_study()
        study_id = study._study_id
        study.optimize(objective, n_trials=2)
        app = create_app(study._storage)

        status, _, body = send_request(
            app,
            f"/api/studies/{study_id}",
            "GET",
            queries={"after": "1"},
            content_type="application/json",
        )
        self.assertEqual(status, 200)
        all_trials = json.loads(body)["trials"]
        self.assertEqual(len(all_trials), 1)

    def test_get_study_details_with_after_param_full(self) -> None:
        study = optuna.create_study()
        study_id = study._study_id
        study.optimize(objective, n_trials=2)
        app = create_app(study._storage)

        status, _, body = send_request(
            app,
            f"/api/studies/{study_id}",
            "GET",
            queries={"after": "2"},
            content_type="application/json",
        )
        self.assertEqual(status, 200)
        all_trials = json.loads(body)["trials"]
        self.assertEqual(len(all_trials), 0)

    def test_get_study_details_with_after_param_illegal(self) -> None:
        study = optuna.create_study()
        study_id = study._study_id
        study.optimize(objective, n_trials=2)
        app = create_app(study._storage)

        status, _, body = send_request(
            app,
            f"/api/studies/{study_id}",
            "GET",
            queries={"after": "-1"},
            content_type="application/json",
        )
        self.assertEqual(status, 400)

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_get_best_trials_of_preferential_study(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(n_generate=4, storage=storage)
        for _ in range(3):
            study.ask()
        study.report_preference(study.trials[0], study.trials[1])

        assert len(study.best_trials) == 1

        app = create_app(storage)
        study_id = study._study._study_id
        status, _, body = send_request(
            app,
            f"/api/studies/{study_id}",
            "GET",
            content_type="application/json",
        )
        self.assertEqual(status, 200)

        best_trials = json.loads(body)["best_trials"]
        assert len(best_trials) == 1
        assert best_trials[0]["number"] == 0

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_report_preference(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(n_generate=4, storage=storage)
        for _ in range(3):
            study.ask()

        app = create_app(storage)
        study_id = study._study._study_id
        status, _, _ = send_request(
            app,
            f"/api/studies/{study_id}/preference",
            "POST",
            body=json.dumps(
                {
                    "mode": "ChooseWorst",
                    "candidates": [0, 1, 2],
                    "clicked": 1,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(status, 204)

        preferences = study.get_preferences()
        preferences.sort(key=lambda x: (x[0].number, x[1].number))
        assert len(preferences) == 2
        better, worse = preferences[0]
        assert better.number == 0
        assert worse.number == 1
        better, worse = preferences[1]
        assert better.number == 2
        assert worse.number == 1

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_report_preference_when_typo_mode(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(storage=storage, n_generate=3)
        for _ in range(3):
            study.ask()

        app = create_app(storage)
        study_id = study._study._study_id
        status, _, _ = send_request(
            app,
            f"/api/studies/{study_id}/preference",
            "POST",
            body=json.dumps(
                {
                    "mode": "ChoseWorst",
                    "candidates": [0, 1, 2],
                    "clicked": 1,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(status, 400)

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_change_component(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(storage=storage, n_generate=3)
        register_preference_feedback_component(study, "note")
        for _ in range(3):
            study.ask()

        app = create_app(storage)
        study_id = study._study._study_id
        status, _, _ = send_request(
            app,
            f"/api/studies/{study_id}/preference_feedback_component",
            "PUT",
            body=json.dumps({"output_type": "artifact", "artifact_key": "image"}),
            content_type="application/json",
        )
        self.assertEqual(status, 204)

        status, _, body = send_request(
            app,
            f"/api/studies/{study_id}",
            "GET",
            content_type="application/json",
        )
        self.assertEqual(status, 200)

        study_detail = json.loads(body)
        assert study_detail["feedback_component_type"]["output_type"] == "artifact"
        assert study_detail["feedback_component_type"]["artifact_key"] == "image"

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_skip_trial(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(n_generate=4, storage=storage)
        trials: list[optuna.Trial] = []
        for _ in range(3):
            trial = study.ask()
            trials.append(trial)
        study.report_preference(study.trials[0], study.trials[1])
        study.report_preference(study.trials[2], study.trials[1])

        app = create_app(storage)
        study_id = study._study._study_id
        status, _, _ = send_request(
            app,
            f"/api/studies/{study_id}/{trials[0]._trial_id}/skip",
            "POST",
            content_type="application/json",
        )
        self.assertEqual(status, 204)

        best_trials = study.best_trials
        assert len(best_trials) == 1
        assert best_trials[0].number == 2

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_remove_history(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(storage=storage, n_generate=3)
        for _ in range(3):
            study.ask()

        app = create_app(storage)
        study_id = study._study._study_id
        history_id = report_history(
            study_id,
            storage,
            NewHistory(
                mode="ChooseWorst",
                candidates=[0, 1, 2],
                clicked=2,
            ),
        )
        histories = serialize_preference_history(storage.get_study_system_attrs(study_id))
        assert len(histories) == 1
        assert not histories[0]["is_removed"]

        status, _, _ = send_request(
            app,
            f"/api/studies/{study_id}/preference/{history_id}",
            "DELETE",
            content_type="application/json",
        )
        self.assertEqual(status, 204)
        histories = serialize_preference_history(storage.get_study_system_attrs(study_id))
        assert len(histories) == 1
        assert histories[0]["is_removed"]
        assert len(study.get_preferences()) == 0

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="BoTorch dropped Python3.7 support")
    def test_restore_history(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        study = create_study(storage=storage, n_generate=3)
        for _ in range(3):
            study.ask()

        app = create_app(storage)
        study_id = study._study._study_id
        history_id = report_history(
            study_id,
            storage,
            NewHistory(
                mode="ChooseWorst",
                candidates=[0, 1, 2],
                clicked=2,
            ),
        )
        remove_history(study_id, storage, history_id)
        histories = serialize_preference_history(storage.get_study_system_attrs(study_id))
        assert len(histories) == 1
        assert histories[0]["is_removed"]
        assert len(study.get_preferences()) == 0

        status, _, _ = send_request(
            app,
            f"/api/studies/{study_id}/preference/{history_id}",
            "POST",
            content_type="application/json",
        )
        self.assertEqual(status, 204)
        histories = serialize_preference_history(storage.get_study_system_attrs(study_id))
        assert len(histories) == 1
        assert not histories[0]["is_removed"]
        preferences = study.get_preferences()
        preferences.sort(key=lambda x: (x[0].number, x[1].number))
        assert len(preferences) == 2
        better, worse = preferences[0]
        assert better.number == 0
        assert worse.number == 2
        better, worse = preferences[1]
        assert better.number == 1
        assert worse.number == 2

    def test_create_study(self) -> None:
        for name, directions, expected_status in [
            ("single-objective success", ["minimize"], 201),
            ("multi-objective success", ["minimize", "maximize"], 201),
            ("invalid direction name", ["invalid-direction", "maximize"], 400),
        ]:
            with self.subTest(name):
                storage = optuna.storages.InMemoryStorage()
                self.assertEqual(len(get_all_study_summaries(storage)), 0)

                app = create_app(storage)
                request_body = {
                    "study_name": "foo",
                    "directions": directions,
                }
                status, _, _ = send_request(
                    app,
                    "/api/studies",
                    "POST",
                    content_type="application/json",
                    body=json.dumps(request_body),
                )
                self.assertEqual(status, expected_status)

                if expected_status == 201:
                    self.assertEqual(len(get_all_study_summaries(storage)), 1)
                else:
                    self.assertEqual(len(get_all_study_summaries(storage)), 0)

    def test_create_study_duplicated(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        create_new_study(storage, "foo", [StudyDirection.MINIMIZE])
        self.assertEqual(len(get_all_study_summaries(storage)), 1)

        app = create_app(storage)
        request_body = {
            "study_name": "foo",
            "direction": "minimize",
        }
        status, _, _ = send_request(
            app,
            "/api/studies",
            "POST",
            content_type="application/json",
            body=json.dumps(request_body),
        )
        self.assertEqual(status, 400)
        self.assertEqual(len(get_all_study_summaries(storage)), 1)

    def test_delete_study(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        create_new_study(storage, "foo1", [StudyDirection.MINIMIZE])
        create_new_study(storage, "foo2", [StudyDirection.MINIMIZE])
        self.assertEqual(len(get_all_study_summaries(storage)), 2)

        app = create_app(storage)
        status, _, _ = send_request(
            app,
            "/api/studies/1",
            "DELETE",
            content_type="application/json",
        )
        self.assertEqual(status, 204)
        self.assertEqual(len(get_all_study_summaries(storage)), 1)

    def test_delete_study_not_found(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        app = create_app(storage)
        status, _, _ = send_request(
            app,
            "/api/studies/1",
            "DELETE",
            content_type="application/json",
        )
        self.assertEqual(status, 404)


class BottleRequestHookTestCase(TestCase):
    def test_ignore_trailing_slashes(self) -> None:
        storage = optuna.storages.InMemoryStorage()
        app = create_app(storage)

        endpoints = ["/api/studies", "/api/studies/"]
        for endpoint in endpoints:
            with self.subTest(msg=endpoint):
                status, _, body = send_request(
                    app,
                    endpoint,
                    "GET",
                    content_type="application/json",
                )
                self.assertEqual(status, 200)
