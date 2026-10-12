from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from django.core.management import CommandError, call_command

from ebird.api.data.models import Checklist, Observer

import pytest

pytestmark = pytest.mark.django_db

MERGED = "MERGED-TEST"

NAMES = {
    "Repair Test One": "USERTEST1",
    "Repair Test Two": "USERTEST2",
}


@pytest.fixture()
def checklists():
    checklists = list(Checklist.objects.order_by("-date")[:2])
    if len(checklists) < 2:
        pytest.skip("Load some checklists first, using add_checklists.")
    return checklists


@pytest.fixture()
def merged(checklists):
    observer = Observer.objects.create(
        identifier=MERGED, name="Repair Test Two", original="Repair Test Two"
    )
    for checklist in checklists:
        checklist.observer = observer
        checklist.save()
        checklist.observations.update(observer=observer)
    return observer


@pytest.fixture()
def visits(checklists):
    return [
        {"subId": checklist.identifier, "userDisplayName": name}
        for checklist, name in zip(checklists, NAMES)
    ]


def top_100(key, location, date, **kwargs):
    return [{"userDisplayName": name, "userId": id} for name, id in NAMES.items()]


def repair(*args):
    call_command("repair_observers", "--identifier", MERGED, *args)


@patch("ebird.api.data.loaders.get_top_100", side_effect=top_100)
@patch("ebird.api.data.loaders.APILoader.fetch_visits")
def test_checklists_are_reassigned(
    mock_fetch_visits, mock_top_100, merged, checklists, visits
):
    mock_fetch_visits.return_value = visits
    repair()
    for checklist, identifier in zip(checklists, NAMES.values()):
        checklist.refresh_from_db()
        assert checklist.observer_id == identifier
        observers = checklist.observations.values_list("observer", flat=True)
        assert set(observers) <= {identifier}
    assert not Observer.objects.filter(identifier=MERGED).exists()


@patch("ebird.api.data.loaders.get_top_100", side_effect=top_100)
@patch("ebird.api.data.loaders.APILoader.fetch_visits")
def test_merged_name_is_not_matched(
    mock_fetch_visits, mock_top_100, merged, checklists, visits
):
    # The merged observer has the same name as the second observer. The
    # checklist must not be assigned back to it.
    mock_fetch_visits.return_value = visits
    repair()
    checklists[1].refresh_from_db()
    assert checklists[1].observer_id == "USERTEST2"


@patch("ebird.api.data.loaders.get_top_100", side_effect=top_100)
@patch("ebird.api.data.loaders.APILoader.fetch_visits")
def test_dry_run(mock_fetch_visits, mock_top_100, merged, checklists, visits):
    mock_fetch_visits.return_value = visits
    repair("--dry-run")
    for checklist in checklists:
        checklist.refresh_from_db()
        assert checklist.observer_id == MERGED
    merged.refresh_from_db()
    assert merged.name == "Repair Test Two"
    assert not Observer.objects.filter(identifier__in=NAMES.values()).exists()


@patch("ebird.api.data.management.commands.repair_observers.get_checklist")
@patch("ebird.api.data.loaders.get_top_100", side_effect=top_100)
@patch("ebird.api.data.loaders.APILoader.fetch_visits")
def test_missing_visit_fetches_checklist(
    mock_fetch_visits, mock_top_100, mock_get_checklist, merged, checklists, visits
):
    mock_fetch_visits.return_value = visits[:1]
    mock_get_checklist.return_value = {"userDisplayName": "Repair Test Two"}
    repair()
    checklists[1].refresh_from_db()
    assert checklists[1].observer_id == "USERTEST2"


@patch("ebird.api.data.management.commands.repair_observers.get_checklist")
@patch("ebird.api.data.loaders.get_top_100", side_effect=top_100)
@patch("ebird.api.data.loaders.APILoader.fetch_visits")
def test_deleted_checklist_is_skipped(
    mock_fetch_visits, mock_top_100, mock_get_checklist, merged, checklists, visits
):
    mock_fetch_visits.return_value = visits[:1]
    mock_get_checklist.side_effect = HTTPError(
        "http://example.com", 404, "Not Found", None, BytesIO(b"")
    )
    repair()
    checklists[0].refresh_from_db()
    checklists[1].refresh_from_db()
    assert checklists[0].observer_id == "USERTEST1"
    assert checklists[1].observer_id == MERGED
    assert Observer.objects.filter(identifier=MERGED).exists()


def test_unknown_observer():
    with pytest.raises(CommandError):
        call_command("repair_observers", "--identifier", "DOES-NOT-EXIST")
