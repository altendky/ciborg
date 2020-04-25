import json

import click

import ciborg.configuration
import ciborg.azure


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

    pipeline = ciborg.azure.create_pipeline(configuration=configuration)
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)
    output_file.write(dumped_pipeline)
