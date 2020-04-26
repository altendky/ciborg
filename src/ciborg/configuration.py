import json

import attr
import marshmallow
import marshmallow.fields
import marshmallow.validate

import ciborg


def create_one_of_string(choices):
    return marshmallow.fields.String(
        validator=marshmallow.validate.OneOf(choices=choices),
    )


class EnvironmentSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    platform = create_one_of_string([
        'linux',
        'macos',
        'windows',
    ])
    interpreter = create_one_of_string([
        'cpython',
    ])
    version = create_one_of_string([
        '3.7',
    ])
    install_source = create_one_of_string([
        'sdist',
        'bdist',
    ])

    @marshmallow.decorators.post_load
    def post_load(self, data, partial, many):
        return Environment(**data)


@attr.s
class Environment:
    platform = attr.ib()
    interpreter = attr.ib()
    version = attr.ib()
    install_source = attr.ib()


class ConfigurationSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()

    build_sdist = marshmallow.fields.Boolean()
    build_wheel = create_one_of_string([
        'universal',
        'specific',
    ])
    test_environments = marshmallow.fields.List(
        marshmallow.fields.Nested(EnvironmentSchema()),
    )
    ciborg_requirement = marshmallow.fields.String(allow_none=True)

    @marshmallow.decorators.post_load
    def post_load(self, data, partial, many):
        return Configuration(**data)


@attr.s
class Configuration:
    name = attr.ib()
    build_sdist = attr.ib()
    build_wheel = attr.ib()
    test_environments = attr.ib()
    ciborg_requirement = attr.ib(default=ciborg.__version__)


def marshall(configuration):
    marshalled = ConfigurationSchema().dump(configuration)

    return marshalled


def load(file):
    marshalled = json.load(file)

    configuration = ConfigurationSchema().load(marshalled)

    return configuration

    pipeline = ciborg.azure.create_pipeline(configuration=configuration)
    dumped_pipeline = ciborg.azure.dump_pipeline(pipeline=pipeline)
    with open('azure-pipelines.yml', 'w') as f:
        f.write(dumped_pipeline)
