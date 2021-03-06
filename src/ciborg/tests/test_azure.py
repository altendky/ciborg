import pathlib

import importlib_resources
import pytest

import ciborg.azure
import ciborg.configuration


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
