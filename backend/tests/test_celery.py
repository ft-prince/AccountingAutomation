from config.celery import app, debug_task


def test_debug_task_runs_eagerly() -> None:
    result = debug_task.apply()
    assert result.get().startswith("ok:")


def test_all_apps_autodiscovered() -> None:
    app.loader.import_default_modules()
    assert "config.celery.debug_task" in app.tasks
