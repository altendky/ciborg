import attr
import importlib_resources
import pytest

import ciborg.configuration


@pytest.fixture
def raw_configuration():
    with importlib_resources.open_text(ciborg.data, 'ciborg.json') as file:
        configuration = ciborg.configuration.load(file)

    return configuration


@pytest.fixture
def configuration(raw_configuration):
    configuration = attr.evolve(
        raw_configuration,
        ciborg_requirement='ciborg==v1+test',
    )

    return configuration


