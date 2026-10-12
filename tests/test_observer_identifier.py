import datetime as dt
from unittest.mock import patch

import pytest

from ebird.api.data.loaders import APILoader
from ebird.api.data.models import Observer

pytestmark = pytest.mark.django_db


@pytest.fixture()
def loader():
    return APILoader("key", {"en": "en"}, rate_limit=0)


@pytest.fixture()
def data():
    return {
        "subId": "S400084531",
        "locId": "L59202896",
        "obsDt": "2026-10-07 19:12",
        "userDisplayName": "Test Observer",
    }


def entry(name, identifier):
    return {"userDisplayName": name, "userId": identifier, "numSpecies": 1}


@patch("ebird.api.data.loaders.get_top_100")
def test_identifier_found(mock_top_100, loader, data):
    mock_top_100.return_value = [
        entry("Someone Else", "USER1"),
        entry("Test Observer", "USER2"),
    ]
    assert loader.get_observer_identifier(data) == "USER2"
    mock_top_100.assert_called_once_with("key", "L59202896", dt.date(2026, 10, 7))


@patch("ebird.api.data.loaders.get_top_100")
def test_identifier_not_found(mock_top_100, loader, data):
    mock_top_100.return_value = [entry("Someone Else", "USER1")]
    assert loader.get_observer_identifier(data) == ""


@patch("ebird.api.data.loaders.get_top_100")
def test_identifier_not_unique(mock_top_100, loader, data):
    mock_top_100.return_value = [
        entry("Test Observer", "USER1"),
        entry("Test Observer", "USER2"),
    ]
    assert loader.get_observer_identifier(data) == ""


def test_generated_identifier_fits_field(loader):
    identifier = loader.generate_observer_identifier()
    field = Observer._meta.get_field("identifier")
    assert identifier.startswith("UNKNOWN-")
    assert len(identifier) <= field.max_length


@patch("ebird.api.data.loaders.get_top_100")
def test_new_observer(mock_top_100, loader, data):
    mock_top_100.return_value = [entry("Test Observer", "USER2")]
    observer = loader.get_observer(data)
    assert observer.identifier == "USER2"
    assert observer.name == "Test Observer"


@patch("ebird.api.data.loaders.get_top_100")
def test_new_observer_renamed(mock_top_100, loader, data):
    Observer.objects.create(identifier="USER2", name="Old Name", original="Old Name")
    mock_top_100.return_value = [entry("Test Observer", "USER2")]
    observer = loader.get_observer(data)
    assert observer.identifier == "USER2"
    assert observer.original == "Test Observer"


@patch("ebird.api.data.loaders.get_top_100")
def test_new_observers_without_identifiers_are_not_merged(mock_top_100, loader, data):
    mock_top_100.return_value = []
    first = loader.get_observer(data)
    second = loader.get_observer({**data, "userDisplayName": "Another Observer"})
    assert first.identifier.startswith("UNKNOWN-")
    assert second.identifier.startswith("UNKNOWN-")
    assert first.identifier != second.identifier
    assert first.name == "Test Observer"
    assert second.name == "Another Observer"


@patch("ebird.api.data.loaders.get_top_100")
def test_existing_observer_is_not_looked_up(mock_top_100, loader, data):
    Observer.objects.create(
        identifier="USER2", name="Test Observer", original="Test Observer"
    )
    observer = loader.get_observer(data)
    assert observer.identifier == "USER2"
    mock_top_100.assert_not_called()


@patch("ebird.api.data.loaders.get_top_100")
def test_observers_sharing_name(mock_top_100, loader, data):
    for identifier in ("ANON1", "ANON2"):
        Observer.objects.create(
            identifier=identifier, name="Test Observer", original="Test Observer"
        )
    mock_top_100.return_value = [entry("Test Observer", "USER3")]
    observer = loader.get_observer(data)
    assert observer.identifier == "USER3"


@patch("ebird.api.data.loaders.get_top_100")
def test_observers_sharing_name_not_found(mock_top_100, loader, data):
    for identifier in ("ANON1", "ANON2"):
        Observer.objects.create(
            identifier=identifier, name="Test Observer", original="Test Observer"
        )
    mock_top_100.return_value = []
    observer = loader.get_observer(data)
    assert observer.identifier == "ANON1"
