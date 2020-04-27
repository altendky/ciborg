import pathlib

import attr
import importlib_resources
import pytest
import yaml

import ciborg.azure
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


@pytest.fixture
def azure_yaml():
    opened_text = importlib_resources.open_text(
        ciborg.data,
        'azure-pipelines.yml',
    )

    with opened_text as file:
        content = file.read()

    return content


def test_dump_to_azure(configuration, azure_yaml):
    pipeline = ciborg.azure.create_pipeline(
        configuration=configuration,
        configuration_path=pathlib.Path('ciborg.json'),
        output_path=pathlib.Path('azure-pipelines.yml'),
    )
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)

    assert azure_yaml == dumped_pipeline


def test_configuration_defaults_to_version(raw_configuration):
    expected = 'ciborg=={}'.format(ciborg.__version__)

    assert raw_configuration.ciborg_requirement == expected
