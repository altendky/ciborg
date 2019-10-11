import click
import yaml

import ciborg.azure


@click.group()
def cli():
    pass


@cli.command()
def fiddle():
    template = ciborg.azure.load_template()
    # print(yaml.dump(template))
    import json
    print(json.dumps(template, indent=4))
