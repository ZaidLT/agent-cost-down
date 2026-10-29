import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_cost_down.demo import test_catalog as make_catalog

spec = importlib.util.spec_from_file_location('forecast', Path('scripts/reservation_forecast.py'))
forecast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forecast)


@pytest.mark.parametrize('value', ['0', '-1', 'nan', 'inf'])
def test_invalid_credit_amount(value):
    with pytest.raises(forecast.argparse.ArgumentTypeError):
        forecast.positive_amount(value)


def test_exact_reservation_is_admissible(tmp_path, capsys, monkeypatch):
    catalog = tmp_path / 'models.json'
    catalog.write_text(make_catalog().model_dump_json())
    monkeypatch.setattr(forecast, 'maximum_cost', lambda config: 1.0)
    monkeypatch.setattr(forecast, 'ALLOCATIONS', {'development': 0.20})
    forecast.main(SimpleNamespace(models=catalog, usable_usd=5, concurrency=1,
                                  output_tokens=4096, transport_retries=2, request_bytes=32768))
    output = capsys.readouterr().out
    assert 'BLOCKED' not in output
    assert 'OK' in output
