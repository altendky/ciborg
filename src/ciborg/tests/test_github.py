import pathlib

import importlib_resources
import pytest

import ciborg.github
import ciborg.configuration


@pytest.fixture
def github_yaml():
    opened_text = importlib_resources.open_text(
        ciborg.data,
        'github.yml',
    )

    with opened_text as file:
        content = file.read()

    return content


def test_dump(configuration, github_yaml):
    workflow = ciborg.github.create_workflow(
        configuration=configuration,
        configuration_path=pathlib.Path('ciborg.json'),
        output_path=pathlib.Path('github.yml'),
    )
    dumped_workflow = ciborg.github.dump_workflow(pipeline=workflow)

    assert github_yaml == dumped_workflow
