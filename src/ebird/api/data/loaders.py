import datetime as dt
import json
import logging
import random
import re
import socket
import string
import time

from decimal import Decimal
from functools import cache
from typing import List, Optional
from urllib.error import HTTPError, URLError

from django.db import transaction
from django.utils.timezone import get_default_timezone

import requests

from bs4 import BeautifulSoup
from ebird.api.requests import get_checklist, get_regions, get_taxonomy, get_visits
from ebird.api.requests.constants import API_MAX_RESULTS

from .models import (
    Checklist,
    Country,
    County,
    Filter,
    Location,
    Observation,
    Observer,
    Species,
    State,
)

logger = logging.getLogger(__name__)

# Set timeout, in seconds, for SSL socket connections
socket.setdefaulttimeout(30)
# Total number number of retries to attempt
RETRY_LIMIT: int = 10
# Time, in seconds, to wait after an API call fails
RETRY_WAIT: int = 2
# Multiplier to apply to wait time after each failed attempt
RETRY_MULTIPLIER: float = 2.0


def str2datetime(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value).replace(
        tzinfo=get_default_timezone(), second=0, microsecond=0
    )


def random_word(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


class APILoader:
    """
    The APILoader downloads checklists from the eBird API and saves
    them to the database.

    Arguments:

        api_key: Your key to access the eBird API.
            Your can request a key at https://ebird.org/data/download.
            You will need an eBird account to do so.

        locales: A map of Django language codes to eBird locales so the species
                 common name, family name, etc. is displayed in the language
                 selected by the user.

        limit: The total number of retries that can be attempted when calling
               the API or scraping a web page. Defaults to RETRY_LIMIT if not
               set.

        wait: The initial number of seconds to wait. Defaults to RETRY_WAIT
              if not set.

        multiplier: The multiplier to apply to the wait time after each retry.
                    Defaults to RETRY_MULTIPLIER if not set.

    The eBird API limits the number of records returned to 200. When downloading
    the visits for a given region if 200 hundred records are returned then it is
    assumed there are more and the loader will fetch the sub-regions and download
    the visits for each, repeating the process if necessary. To give an extreme
    example if you download the visits for the United States, "US", then the API
    will always return 200 results and the loader then download the visits to
    each of the 50 states and then each of the 3143 counties. DON'T TRY THIS
    AT HOME. Even if you don't get banned, if you melt the eBird servers, then
    karma will ensure bad things happen to you.

    The loader uses a budget for retry attempts when calling the eBird API or
    fetching a web page. After each failure, a wait is applied, which increases
    after each attempt. Once the total number of retries is reached, no
    further attempts are made. You can set the number of retries, the initial
    wait, and the multiplier when creating an APILoader object, otherwise
    sensible defaults are used.

    The default limit for retries is 10, with an initial wait of 2 seconds and
    a multiplier also of 2. This means the loader will wait, 2, 4, 8, 16, etc.
    seconds after each attempt. Since the loader will be run periodically,
    using a scheduler such as cron, the retry limit is probably too high. Most
    of the errors seen to date are timeout error when creating an SSL socket
    connection. The are relatively rare - only one or two a week - with a
    loader that is scheduled to run every hour. You could easily reduce the
    limit to 3, as then, successive errors will usually mean something serious
    is wrong with the network, or the eBird servers are overloaded, and you
    should stop from making the situation any worse.

    """

    def __init__(
        self,
        api_key: str,
        locales: dict,
        limit: int = None,
        wait: int = None,
        multiplier: float = None,
    ):
        self.api_key: str = api_key
        self.locales: dict = locales
        self.retries: int = 0
        self.retry_limit: int = limit if limit else RETRY_LIMIT
        self.retry_wait: int = wait if wait else RETRY_WAIT
        self.retry_multiplier: float = multiplier if multiplier else RETRY_MULTIPLIER

    def call(self, func, *args, **kwargs):
        wait: float = float(self.retry_wait)
        while True:
            try:
                return func(*args, **kwargs)
            except (URLError, HTTPError) as err:
                logger.exception("Failed call #%d", self.retries)
                self.retries += 1
                if self.retries > self.retry_limit:
                    logger.exception("Retry limit reached")
                    raise err
                time.sleep(wait)
                wait *= self.retry_multiplier

    def call_api(self, func, *args, **kwargs) -> dict | list:
        return self.call(func, self.api_key, *args, **kwargs)

    @staticmethod
    def update(obj, values: dict) -> dict[str, tuple]:
        changed: dict[str, tuple] = {}
        for key, value in values.items():
            current = getattr(obj, key)
            if current != value:
                setattr(obj, key, value)
                changed[key] = (current, value)
        if changed:
            obj.save()
        return changed

    def get_country(self, data: dict) -> Country:
        code: str = data["countryCode"]
        values: dict = {
            "name": data["countryName"],
            "place": data["countryName"],
        }
        country, created = Country.objects.get_or_create(code=code, defaults=values)
        if created:
            logger.info("Country %s: added", code)
        elif changed := self.update(country, values):
            if "name" in changed:
                old, new = changed["name"]
                logger.info("Country %s: renamed, %s -> %s", code, old, new)
        return country

    def get_state(self, data: dict) -> State:
        code: str = data["subnational1Code"]
        values: dict = {
            "name": data["subnational1Name"],
            "place": "%s, %s" % (data["subnational1Name"], data["countryName"]),
        }
        state, created = State.objects.get_or_create(code=code, defaults=values)
        if created:
            logger.info("State: %s:  added", code)
        elif changed := self.update(state, values):
            if "name" in changed:
                old, new = changed["name"]
                logger.info("State %s: renamed, %s -> %s", code, old, new)
        return state

    def get_county(self, data) -> County:
        code: str = data["subnational2Code"]
        values: dict = {
            "name": data["subnational2Name"],
            "place": "%s, %s, %s"
            % (data["subnational2Name"], data["subnational1Name"], data["countryName"]),
        }
        county, created = County.objects.get_or_create(code=code, defaults=values)
        if created:
            logger.info("County %s: added", code)
        elif changed := self.update(county, values):
            if "name" in changed:
                old, new = changed["name"]
                logger.info("County %s: renamed, %s -> %s", code, old, new)
        return county

    def add_location(self, data: dict) -> Location:
        identifier: str = data["locId"]
        location: Location

        values: dict = {
            "name": data["name"],
            "original": data["name"],
            "country": self.get_country(data),
            "state": self.get_state(data),
            "county": None,
            "hotspot": data["isHotspot"],
            "latitude": round(Decimal(data["latitude"]), 7),
            "longitude": round(Decimal(data["longitude"]), 7),
            "url": "https://ebird.org/region/%s" % identifier,
        }

        if "subnational2Code" in data:
            values["county"] = self.get_county(data)

        location, created = Location.objects.get_or_create(
            identifier=identifier, defaults=values
        )

        if not created:
            values.pop("name")  # Don't overwrite the name

        if created:
            logger.info("Location %s: added, %s", identifier, values["name"])
        elif changed := self.update(location, values):
            included = ["name", "hotspot", "county", "state", "country"]
            filtered = {key: value for key, value in changed.items() if key in included}
            for key, (old, new) in filtered.items():
                logger.info(
                    "Location %s: changed %s, %s -> %s", identifier, key, old, new
                )
        return location

    def add_species(self, code: str) -> Species:
        """
        Add the species with the eBird code.

        Arguments:
            code: the eBird code for the species, e.g. 'horlar' (Horned Lark).

        """
        values: dict = {
            "common_name": {},
            "family_common_name": {},
        }

        for language, locale in self.locales.items():
            data = self.call_api(get_taxonomy, locale=locale, species=code)[0]
            values["taxon_order"] = int(data["taxonOrder"])
            values["order"] = data.get("order", "")
            values["category"] = data["category"]
            values["family_code"] = data.get("familyCode", "")
            values["common_name"][language] = data["comName"]
            values["scientific_name"] = data["sciName"]
            values["family_common_name"][language] = data.get("familyComName", "")
            values["family_scientific_name"] = data.get("familySciName", "")

        values["common_name"] = json.dumps(values["common_name"])
        values["family_common_name"] = json.dumps(values["family_common_name"])

        species = Species.objects.create(species_code=code, **values)
        logger.info("Species %s: added, %s", code, species.get_common_name())

        return species

    def get_species(self, data: dict) -> Species:
        code: str = data["speciesCode"]
        species = Species.objects.filter(species_code=code).first()
        if species is None:
            species = self.add_species(code)
        return species

    @staticmethod
    def get_urn(project_id, row: dict) -> str:
        return f"URN:CornellLabOfOrnithology:{project_id}:{row['obsId']}"

    def get_observation(self, data: dict, checklist: Checklist) -> Observation:
        identifier: str = data["obsId"]
        observation: Observation
        species: Species = self.get_species(data)

        values: dict = {
            "edited": checklist.edited,
            "published": False,
            "checklist": checklist,
            "country": checklist.country,
            "state": checklist.state,
            "county": checklist.county,
            "location": checklist.location,
            "observer": checklist.observer,
            "species": species,
            "date": checklist.date,
            "time": checklist.time,
            "started": checklist.started,
            "count": 0,
            "audio": False,
            "photo": False,
            "video": False,
            "comments": "",
            "urn": self.get_urn(checklist.project_code, data),
        }

        if re.match(r"\d+", data["howManyStr"]):
            values["count"] = int(data["howManyStr"])

        if "mediaCounts" in data:
            values["audio"] = "A" in data["mediaCounts"]
            values["photo"] = "P" in data["mediaCounts"]
            values["video"] = "V" in data["mediaCounts"]

        if "comments" in data:
            values["comments"] = data["comments"]

        observation, created = Observation.objects.get_or_create(
            identifier=identifier, defaults=values
        )

        # Log observations that were added after the checklist was first loaded.
        if created and checklist.created < checklist.edited:
            logger.info(
                "Checklist %s: added, %s (%d)",
                checklist.identifier,
                species,
                values["count"],
            )

        if not created:
            values.pop("published")

        if changed := self.update(observation, values):
            for field in ["audio", "photo", "video"]:
                if field in changed:
                    old, new = changed[field]
                    logger.info(
                        "Checklist %s: %s, %s %s",
                        checklist.identifier,
                        species,
                        field,
                        "added" if new else "deleted",
                    )
            if "count" in changed:
                old, new = changed["count"]
                logger.info(
                    "Checklist %s: %s, count, %s -> %s",
                    checklist.identifier,
                    species,
                    old,
                    new,
                )
            if "species" in changed:
                old, new = changed["species"]
                logger.info(
                    "Checklist %s: species, %s -> %s",
                    checklist.identifier,
                    old,
                    new,
                )
        return observation

    def get_observer_identifier(self, data) -> str:
        identifier: str = data["subId"]
        logger.info("Scraping checklist: %s", identifier)
        response = self.call(
            requests.get, "https://ebird.org/checklist/%s" % identifier
        )
        content = response.content
        soup = BeautifulSoup(content, "lxml")
        attribute = "data-participant-userid"
        node = soup.find("span", attrs={attribute: True})
        identifier = node[attribute] if node else ""
        if identifier:
            logger.info("Observer Identifier: %s", identifier)
        else:
            logger.info("Observer Identifier: not found")
        return identifier

    def get_observer(self, data: dict) -> Observer:
        name: str = data.get("userDisplayName", "Anonymous eBirder")
        is_multiple = Observer.objects.filter(original=name, multiple=True).exists()
        if is_multiple:
            identifier = self.get_observer_identifier(data)
            observer, created = Observer.objects.get_or_create(
                identifier=identifier,
                defaults={"name": name, "original": random_word(8)},
            )
        else:
            if observer := Observer.objects.filter(original=name).first():
                created = False
            else:
                identifier = self.get_observer_identifier(data)
                observer, created = Observer.objects.get_or_create(
                    identifier=identifier,
                    defaults={"name": name, "original": name},
                )

        if created:
            logger.info("Observer %s: added, %s", identifier, name)
            if Observer.objects.filter(original=name).count() > 1:
                logger.error("Multiple observers exist with same name: %s", name)

        return observer

    def add_checklist(self, identifier: str) -> Checklist | None:
        """
        Add or update the checklist with the given identifier.

        Arguments:
            identifier: the eBird identifier for the checklist, e.g. "S318722167"

        """
        # Make sure loading a checklist is an all or nothing proposition.
        # All the data is available from the eBird API call but there can
        # still be further calls to scrape the checklist web page to get
        # identifier of the observer, or the eBird API when a new species
        # is added.

        with transaction.atomic():
            data: dict = self.call_api(get_checklist, identifier)
            identifier: str = data["subId"]
            added: dt.datetime = str2datetime(data["creationDt"])
            edited: dt.datetime = str2datetime(data["lastEditedDt"])
            started: dt.datetime = str2datetime(data["obsDt"])
            location: Location = Location.objects.get(identifier=data["locId"])
            checklist: Checklist
            observer: Observer = self.get_observer(data)
            observations: list = data.pop("obs", [])

            if not observer.enabled:
                return None

            values: dict = {
                "added": added,
                "edited": edited,
                "published": False,
                "country": location.country,
                "state": location.state,
                "county": location.county,
                "location": location,
                "observer": observer,
                "observer_count": None,
                "species_count": data["numSpecies"],
                "date": started.date(),
                "time": None,
                "started": started,
                "protocol_code": data["protocolId"],
                "project_code": data["projId"],
                "duration": None,
                "complete": data["allObsReported"],
                "comments": "",
                "url": "https://ebird.org/checklist/%s" % identifier,
            }

            if data["obsTimeValid"]:
                values["time"] = started.time()
            else:
                values["time"] = None

            if "numObservers" in data:
                values["observer_count"] = int(data["numObservers"])
            else:
                values["observer_count"] = None

            if duration := data.get("durationHrs"):
                values["duration"] = int(duration * 60.0)
            else:
                values["duration"] = None

            if dist := data.get("effortDistanceKm"):
                values["distance"] = round(Decimal(dist), 3)
            else:
                values["distance"] = None

            if area := data.get("effortAreaHa"):
                values["area"] = round(Decimal(area), 3)
            else:
                values["area"] = None

            if "comments" in data:
                values["comments"] = data["comments"]
            else:
                values["comments"] = ""

            checklist, created = Checklist.objects.get_or_create(
                identifier=identifier, defaults=values
            )

            if not created:
                values.pop("published")

            if created:
                logger.info("Checklist %s: added", identifier)
            elif changed := self.update(checklist, values):
                ignored = ["added", "edited", "published", "url", "comments"]
                filtered = {
                    key: value for key, value in changed.items() if key not in ignored
                }
                for key, (old, new) in filtered.items():
                    logger.info(
                        "Checklist %s: changed %s, %s -> %s",
                        identifier,
                        key.replace("_", " "),
                        old,
                        new,
                    )
            else:
                logger.debug("Checklist %s: unchanged", identifier)

            for observation_data in observations:
                self.get_observation(observation_data, checklist)

            for obs in checklist.observations.all():
                if obs.edited != checklist.edited:
                    obs.delete()
                    logger.info(
                        "Checklist %s: deleted, %s (%s)",
                        identifier,
                        obs.species,
                        obs.count,
                    )

        return checklist

    @cache
    def fetch_subregions(self, region: str) -> List[str]:
        region_types: list = ["subnational1", "subnational2", None]
        levels: int = len(region.split("-", 2))
        region_type: Optional[str] = region_types[levels - 1]

        if region_type:
            items: list = self.call_api(get_regions, region_type, region)
            sub_regions = [item["code"] for item in items]
        else:
            sub_regions = []

        return sub_regions

    def fetch_visits(self, region: str, date: dt.date):
        visits = []

        results: list = get_visits(
            self.api_key, region, date=date, max_results=API_MAX_RESULTS
        )

        if len(results) == API_MAX_RESULTS:
            logger.info("Region %s: API limit reached - fetching subregions", region)
            if sub_regions := self.fetch_subregions(region):
                for sub_region in sub_regions:
                    sub_region_visits = self.fetch_visits(sub_region, date)
                    visits.extend(sub_region_visits)
                    logger.info(
                        "Region %s: %d visits", sub_region, len(sub_region_visits)
                    )
            else:
                # No more sub-regions, issue a warning and return the results
                visits.extend(results)
                logger.warning(
                    "Region %s: API limit reached - no subregions available", region
                )
        else:
            visits.extend(results)

        return visits

    def add_checklists(self, region: str, date: dt.date, update=True) -> None:
        """
        Add or update all the checklists submitted for a region for a given date.

        Arguments:
            region: The code for a national, subnational1, subnational2
                 area or hotspot identifier. For example, US, US-NY,
                 US-NY-109, or L1379126, respectively.

            date: The date the observations were made.

            update: Update existing checklists. Default is True.

        """

        logger.info("Adding checklists: %s, %s", region, date.strftime("%Y-%m-%d"))

        visits: list[dict] = self.fetch_visits(region, date)

        logger.info("Region %s: %s visits", region, len(visits))

        for visit in visits:
            data = visit["loc"]
            self.add_location(data)

        for visit in visits:
            identifier = visit["subId"]
            if not update and Checklist.objects.filter(identifier=identifier).exists():
                continue
            self.add_checklist(identifier)

        self.run_filters()
        self.publish()

        logger.info("Added checklists: %s, %s", region, date.strftime("%Y-%m-%d"))

    @staticmethod
    def run_filters():
        for filter in Filter.objects.filter(enabled=True):
            logger.info("Applying filter: %s", filter.name)
            count = filter.apply()
            logger.info("Observations updated: %d", count)

    @staticmethod
    def publish():
        Checklist.objects.filter(published=False).update(published=True)
        Observation.objects.filter(published=False).update(published=True)
