import click

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

    pipeline = ciborg.azure.create_pipeline(name='testing pipeline')
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)
    print(dumped_pipeline)
