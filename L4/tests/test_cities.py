import pytest

from assistente.cities import find_city


@pytest.mark.parametrize("name, expected", [
    ("Miami", ("Miami", "US", "America/New_York")),
    ("Nuova York", ("New York City", "US", "America/New_York")),
    ("pechino", ("Beijing", "CN", "Asia/Shanghai")),
    ("Città del Messico", ("Mexico City", "MX", "America/Mexico_City")),
    ("Citta del Messico", ("Mexico City", "MX", "America/Mexico_City")),
    ("  KYOTO ", ("Kyoto", "JP", "Asia/Tokyo")),
])
def test_find_city(name, expected):
    assert tuple(find_city(name)) == expected


def test_homonyms_pick_most_populous():
    assert find_city("Paris").country == "FR"


@pytest.mark.parametrize("name", ["Miami, Florida", "Miami, USA"])
def test_country_after_comma_is_ignored(name):
    assert find_city(name).timezone == "America/New_York"


@pytest.mark.parametrize("name", ["Xyzville", "", "   ", ","])
def test_unknown_or_empty_city(name):
    assert find_city(name) is None


@pytest.mark.parametrize("name, expected", [
    ("Zaragoza", ("Zaragoza", "ES", "Europe/Madrid")),
    ("Islamabad", ("Islamabad", "PK", "Asia/Karachi")),
    ("Cancun", ("Cancún", "MX", "America/Cancun")),
])
def test_main_name_beats_alternate_name_of_bigger_city(name, expected):
    assert tuple(find_city(name)) == expected


@pytest.mark.parametrize("name, expected", [
    ("Roma", ("Rome", "IT", "Europe/Rome")),
    ("Mexico", ("Mexico City", "MX", "America/Mexico_City")),
])
def test_much_bigger_city_wins_with_alternate_name(name, expected):
    assert tuple(find_city(name)) == expected
