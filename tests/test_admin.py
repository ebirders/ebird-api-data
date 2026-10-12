from django.urls import reverse

from ebird.api.data import models

import pytest

pytestmark = pytest.mark.django_db

models = [
    models.Checklist,
    models.Country,
    models.County,
    models.Location,
    models.Observation,
    models.Observer,
    models.Species,
    models.State,
]

# Don't include tests for the delete view as we're testing against
# a live database and deleting Country, County, Location or State,
# will trigger generating a list of all Checklists and all Observations,
# which is going to take a while.

@pytest.mark.parametrize("model", models)
def test_changelist_view(admin_client, model):
    url = reverse("admin:data_%s_changelist" % model.__name__.lower())
    response = admin_client.get(url)
    assert response.status_code == 200


@pytest.mark.parametrize("model", models)
def test_add_view(admin_client, model):
    url = reverse("admin:data_%s_add" % model.__name__.lower())
    response = admin_client.get(url)
    assert response.status_code == 200


@pytest.mark.parametrize("model", models)
def test_change_view(admin_client, model):
    obj = model._default_manager.last()
    if obj is None:
        pytest.skip(
            "No %s records. Load some checklists first, using the "
            "add_checklists management command." % model.__name__
        )
    url = reverse("admin:data_%s_change" % model.__name__.lower(), args=(obj.pk,))
    response = admin_client.get(url)
    assert response.status_code == 200
