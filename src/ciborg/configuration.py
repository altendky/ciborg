import json

import attr
import marshmallow
import marshmallow.fields
import marshmallow.validate

import ciborg


# TODO: fancier sentinels give nicer errors or something
_NOTHING = object()


def create_one_of_string(choices, missing=_NOTHING):
    extras = {}

    if missing is not _NOTHING:
        extras['missing'] = missing

    return marshmallow.fields.String(
        validator=marshmallow.validate.OneOf(choices=choices),
        **extras,
    )


@attr.s(frozen=True)
class Platform:
    configuration_string = attr.ib()
    identifier_string = attr.ib()
    display_string = attr.ib()


linux_platform = Platform(
    configuration_string='linux',
    identifier_string='linux',
    display_string='Linux',
)


macos_platform = Platform(
    configuration_string='macos',
    identifier_string='macos',
    display_string='macOS',
)


windows_platform = Platform(
    configuration_string='windows',
    identifier_string='windows',
    display_string='Windows',
)


platforms = [linux_platform, macos_platform, windows_platform]


platforms_by_identifier_string = {
    platform.configuration_string: platform
    for platform in platforms
}


@attr.s(frozen=True)
class Interpreter:
    configuration_string = attr.ib()
    identifier_string = attr.ib()
    display_string = attr.ib()


cpython_interpreter = Interpreter(
    configuration_string='cpython',
    identifier_string='cpython',
    display_string='CPython',
)


interpreters = [cpython_interpreter]


interpreter_by_identifier_string = {
    interpreter.identifier_string: interpreter
    for interpreter in interpreters
}


@attr.s(frozen=True)
class PythonVersion:
    configuration_string = attr.ib()
    identifier_string = attr.ib()
    display_string = attr.ib()
    numeric = attr.ib()

    def joined_by(self, separator):
        return separator.join(str(x) for x in self.numeric)


python_versions = [
    PythonVersion(
        configuration_string='.'.join(str(x) for x in version_tuple),
        identifier_string='_'.join(str(x) for x in version_tuple),
        display_string='.'.join(str(x) for x in version_tuple),
        numeric=version_tuple,
    )
    for version_tuple in [
        (major, minor)
        for major in [3]
        for minor in [5, 6, 7, 8]
    ]
]

python_version_by_identifier_string = {
    python_version.configuration_string: python_version
    for python_version in python_versions
}


@attr.s(frozen=True)
class InstallSource:
    configuration_string = attr.ib()
    identifier_string = attr.ib()
    display_string = attr.ib()


sdist_install_source = InstallSource(
    configuration_string='sdist',
    identifier_string='sdist',
    display_string='sdist',
)


bdist_install_source = InstallSource(
    configuration_string='bdist',
    identifier_string='bdist',
    display_string='bdist',
)


install_sources = [sdist_install_source, bdist_install_source]


install_source_by_identifier_string = {
    install_source.identifier_string: install_source
    for install_source in install_sources
}


class EnvironmentSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    platform = create_one_of_string([
        platform.configuration_string
        for platform in platforms
    ])
    interpreter = create_one_of_string([
        interpreter.configuration_string
        for interpreter in interpreters
    ])
    version = create_one_of_string([
        python_version.configuration_string
        for python_version in python_versions
    ])
    install_source = create_one_of_string(
        [
            install_source.configuration_string
            for install_source in install_sources
        ],
        missing=None,
    )

    @marshmallow.decorators.post_load
    def post_load(self, data, partial, many):
        d = {
            'platform': platforms_by_identifier_string.get,
            'interpreter': interpreter_by_identifier_string.get,
            'version': python_version_by_identifier_string.get,
            'install_source': install_source_by_identifier_string.get,
        }

        for key, value in data.items():
            mapper = d.get(key)
            if mapper is not None:
                data[key] = mapper(value)

        return Environment(**data)


@attr.s
class Environment:
    platform = attr.ib()
    interpreter = attr.ib()
    version = attr.ib()
    install_source = attr.ib()

    def identifier(self):
        elements = [
            self.platform,
            self.interpreter,
            self.version,
        ]

        if self.install_source is not None:
            elements.append(self.install_source)

        return '_'.join(element.identifier_string for element in elements)

    def display_name(self):
        elements = [
            self.platform,
            self.interpreter,
            self.version,
        ]

        if self.install_source is not None:
            elements.append(self.install_source)

        return ' '.join(element.display_string for element in elements)


class ConfigurationSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()

    build_sdist = marshmallow.fields.Boolean()
    build_wheel = create_one_of_string([
        'universal',
        'specific',
    ])
    tooling_environment = marshmallow.fields.Nested(EnvironmentSchema())
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
    tooling_environment = attr.ib()
    test_environments = attr.ib()
    ciborg_requirement = attr.ib(
        default='ciborg=={version}'.format(version=ciborg.__version__),
    )


def marshal(configuration):
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
