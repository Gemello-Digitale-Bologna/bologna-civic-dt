import osmnx as ox
import pytest
import requests

from bologna_civic_dt.ingestion import osm


def _server(monkeypatch, answers: list) -> list:
    """ox.features_from_polygon answering `answers` in turn (an exception is
    raised); the waits recorded, not waited."""
    waits = []

    def features_from_polygon(polygon, tags):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(ox, "features_from_polygon", features_from_polygon)
    monkeypatch.setattr(osm.time, "sleep", waits.append)
    return waits


def _status(code: int) -> Exception:
    return ox._errors.ResponseStatusCodeError(f"'overpass-api.de' responded: {code} Bad Gateway <html>...")


def test_a_server_error_is_tried_again(monkeypatch):
    waits = _server(monkeypatch, [_status(502), requests.ConnectionError("reset"), "fountains"])
    assert osm.features(None, {"amenity": "fountain"}) == "fountains"
    assert waits == list(osm.RETRY_WAITS_S)


def test_a_server_down_for_good_says_what_to_do(monkeypatch):
    _server(monkeypatch, [_status(502)] * 3)
    with pytest.raises(RuntimeError, match="OVERPASS_URL"):
        osm.features(None, {"amenity": "fountain"})


def test_a_bad_query_is_not_tried_again(monkeypatch):
    waits = _server(monkeypatch, [_status(400)])
    with pytest.raises(ox._errors.ResponseStatusCodeError):
        osm.features(None, {"amenity": "fountain"})
    assert waits == []
