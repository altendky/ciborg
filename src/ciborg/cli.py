import json
import os
import pathlib

import click

import ciborg.azure
import ciborg.configuration
import ciborg.circle
import ciborg.github


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    '--configuration',
    'configuration_file',
    type=click.File(mode='r'),
    default='ciborg.json',
    show_default=True,
)
@click.option(
    '--output',
    'output_file',
    type=click.File(mode='w', atomic=True),
    default='azure-pipelines.yml',
    show_default=True,
)
def azure(configuration_file, output_file):
    marshalled = json.load(configuration_file)

    configuration = ciborg.configuration.ConfigurationSchema().load(
        marshalled,
    )

    configuration_path = pathlib.Path(configuration_file.name)
    output_path = pathlib.Path(
        os.path.relpath(output_file.name, configuration_path.parent),
    )

    pipeline = ciborg.azure.create_pipeline(
        configuration=configuration,
        configuration_path=configuration_path,
        output_path=output_path,
    )
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)
    output_file.write(dumped_pipeline)


@cli.command()
@click.option(
    '--configuration',
    'configuration_file',
    type=click.File(mode='r'),
    default='ciborg.json',
    show_default=True,
)
@click.option(
    '--output',
    'output_file',
    type=click.File(mode='w', atomic=True),
    default='.github/workflows/ci.yml',
    show_default=True,
)
def github(configuration_file, output_file):
    marshalled = json.load(configuration_file)

    configuration = ciborg.configuration.ConfigurationSchema().load(
        marshalled,
    )

    configuration_path = pathlib.Path(configuration_file.name)
    output_path = pathlib.Path(
        os.path.relpath(output_file.name, configuration_path.parent),
    )

    workflow = ciborg.github.create_workflow(
        configuration=configuration,
        configuration_path=configuration_path,
        output_path=output_path,
    )
    dumped_pipeline = ciborg.github.dump_workflow(pipeline=workflow)
    output_file.write(dumped_pipeline)


@cli.command()
@click.option(
    '--configuration',
    'configuration_file',
    type=click.File(mode='r'),
    default='ciborg.json',
    show_default=True,
)
@click.option(
    '--output',
    'output_file',
    type=click.File(mode='w', atomic=True),
    default='.circleci/config.yml',
    show_default=True,
)
def circle(configuration_file, output_file):
    marshalled = json.load(configuration_file)

    configuration = ciborg.configuration.ConfigurationSchema().load(
        marshalled,
    )

    configuration_path = pathlib.Path(configuration_file.name)
    output_path = pathlib.Path(
        os.path.relpath(output_file.name, configuration_path.parent),
    )

    workflow = ciborg.circle.create_pipeline(
        configuration=configuration,
        configuration_path=configuration_path,
        output_path=output_path,
    )
    dumped_pipeline = ciborg.circle.dump_pipeline(pipeline=workflow)
    output_file.write(dumped_pipeline)
