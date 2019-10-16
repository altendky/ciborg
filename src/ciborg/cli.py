import json

import click

import ciborg.configuration
import ciborg.azure


@click.group()
def cli():
    pass


@cli.command()
def fiddle():
    # template = ciborg.azure.load_template()
    # print(yaml.dump(template))
    # import json
    # print(json.dumps(template, indent=4))

    pipeline = ciborg.azure.create_pipeline(name='Testing Pipeline')
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)
    with open('azure-pipelines.yml', 'w') as f:
        f.write(dumped_pipeline)


@cli.command()
@click.option(
    '--configuration',
    'configuration_file',
    type=click.File(mode='w', atomic=True),
)
def faddle(configuration_file):
    configuration = ciborg.configuration.Configuration(
        build_sdist=True,
        build_universal_wheel=True,
        test_environments=[
            ciborg.configuration.Environment(
                platform='linux',
                interpreter='cpython',
                version='3.7',
            ),
        ]
    )

    marshalled = ciborg.configuration.marshall(configuration=configuration)

    json.dump(marshalled, configuration_file, indent=4)


@cli.command()
@click.option(
    '--configuration',
    'configuration_file',
    type=click.File(mode='r'),
)
def fuddle(configuration_file):
    marshalled = json.load(configuration_file)

    configuration = ciborg.configuration.ConfigurationSchema().load(
        marshalled,
    )

    pipeline = ciborg.azure.create_pipeline(configuration=configuration)
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)
    with open('azure-pipelines.yml', 'w') as f:
        f.write(dumped_pipeline)
