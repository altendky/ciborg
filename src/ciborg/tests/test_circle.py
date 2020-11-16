import pathlib

import importlib_resources
import pytest

import ciborg.circle
import ciborg.configuration


@pytest.fixture
def circle_yaml():
    opened_text = importlib_resources.open_text(
        ciborg.data,
        'circle.yml',
    )

    with opened_text as file:
        content = file.read()

    return content


def test_dump_to_circle(configuration, circle_yaml):
    pipeline = ciborg.circle.create_pipeline(
        configuration=configuration,
        configuration_path=pathlib.Path('ciborg.json'),
        output_path=pathlib.Path('circle.yml'),
    )
    dumped_pipeline = ciborg.circle.dump_pipeline(pipeline=pipeline)

    assert circle_yaml == dumped_pipeline
