# eBird API Data

eBird API Data is a reusable Django app for loading data from eBird into a database.

## Overview

The Cornell Laboratory of Ornithology in Ithaca, New York runs the eBird database
which collects observations of birds from all over the world. All the observations
are published on [eBird.org](https://ebird.org), and they also make them available
via an [API](https://documenter.getpostman.com/view/664302/S1ENwy59). This project
contains a loader and models to take data from the API and load it into a database.
From there you can analyse the data with python, jupyter notebooks, or build a web
site.

To get started, you will need to
[sign up](https://secure.birds.cornell.edu/identity/account/create)
for an eBird account, if you don't already have one and
[register](https://ebird.org/data/download)
to get an API key. Make sure you read and understand the
[Terms of use](https://www.birds.cornell.edu/home/ebird-api-terms-of-use/),
and remember bandwidth and servers cost money, so don't abuse the service. If you
need large numbers of observations, then sign up to receive the
[eBird Basic Dataset](https://science.ebird.org/en/use-ebird-data/download-ebird-data-products).

## Install

You can use either [pip](https://pip.pypa.io/en/stable/) or [uv](https://docs.astral.sh/uv/)
to download the [package](https://pypi.org/project/ebird-api-data/) from PyPI and
install it into a virtualenv:

```shell
pip install ebird-api-data
```

or:

```shell
uv add ebird-api-data
```

Update `INSTALLED_APPS` in your Django setting:

```python
INSTALLED_APPS = [
    ...
    ebird.api.data
]
```

Finally, run the migrations to create the tables:

```python
python manage.py migrate
```

## Demo

If you check out the code from the repository there is a fully functioning
Django site. It contains pages for checklists, observations and species,
where you can browse the records or search by location, observer. date. etc. 
The Django Admin lets you browse and edit the records in the database.

```shell
git clone git@github.com:StuartMacKay/ebird-api-data.git
cd ebird-api-data
```

Create the virtual environment:
```shell
uv venv
```

Activate it:
```shell
source .venv/bin/activate
```

Install the requirements:
```shell
uv sync
```

Create a copy of the .env.example file and add your API key:
```shell
cp .env.example .env
```

For example:
```shell
EBIRD_API_KEY=<my api key>
```

Run the database migrations:
```shell
python manage.py migrate
```

Create a user:
```shell
python manage.py createsuperuser
```

Create a copy of the .env.example file and add your API key:
```shell
cp .env.example .env
```

```shell
EBIRD_API_KEY=<my api key>
```

Now, download data from the API:

```shell
python manage.py add_checklists --days -2 US-NY-109
```

This loads all the checklists, submitted in the past two days by birders in
Tompkins County, New York, where the Cornell Lab is based. You can use any
location code used by eBird, whether it's for a country, state/region, or
county. Remember, read the terms of use.

Run the demo:

```shell
python manage.py runserver
```

Now, either visit the site, http:localhost:8000/, or log into the Django Admin, 
http:localhost:8000/admin to browse the tables.

## Project Information

* Documentation: https://ebird-api-data.readthedocs.io/en/latest/
* Issues: https://todo.sr.ht/~smackay/ebird-api-data
* Repository: https://git.sr.ht/~smackay/ebird-api-data
* Announcements: https://lists.sr.ht/~smackay/ebirders-announce
* Discussions: https://lists.sr.ht/~smackay/ebirders-discuss
* Development: https://lists.sr.ht/~smackay/ebirders-develop

The repository is also mirrored on Github:

* Repository: https://github.com/StuartMacKay/ebird-api-data

The app is tested on Python 3.10+, and officially supports Django 4.2, 5.0 and 5.1.

## License

eBird API Data is released under the terms of the [MIT](https://opensource.org/licenses/MIT) license.
