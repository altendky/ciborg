import collections
import pathlib
import typing

import attr
import marshmallow
import marshmallow_polyfield
import pyrsistent.typing
import yaml

from pyrsistent import pvector, pmap, pset

import ciborg.configuration
import ciborg.data
import ciborg.utils


# class UsePythonVersionTaskStepSchema(marshmallow.Schema):
#     class Meta:
#         ordered = True
#
#     architecture = marshmallow.fields.String()
#     version_spec = marshmallow.fields.String(data_key='versionSpec')
#
#
# @attr.s(frozen=True)
# class UsePythonVersionTaskStepInputs:
#     architecture = attr.ib()
#     version_spec = attr.ib()
#
#
# class PublishBuildArtifactsTaskStepSchema(marshmallow.Schema):
#     class Meta:
#         ordered = True
#
#     path_to_publish = marshmallow.fields.String(data_key='pathToPublish')
#     artifact_name = marshmallow.fields.String(data_key='artifactName')
#
#
# @attr.s(frozen=True)
# class PublishBuildArtifactsTaskStep:
#     path_to_publish = attr.ib()
#     artifact_name = attr.ib()
#
#
# class DownloadBuildArtifactsTaskStepSchema(marshmallow.Schema):
#     class Meta:
#         ordered = True
#
#     download_path = marshmallow.fields.String(data_key='downloadPath')
#     artifact_name = marshmallow.fields.String(data_key='artifactName')
#
#
# @attr.s(frozen=True)
# class DownloadBuildArtifactsTaskStep:
#     download_path = attr.ib()
#     artifact_name = attr.ib()
#
#
# task_step_inputs_type_schema_map = pmap({
#     UsePythonVersionTaskStepInputs: UsePythonVersionTaskStepSchema,
#     PublishBuildArtifactsTaskStep: PublishBuildArtifactsTaskStepSchema,
#     DownloadBuildArtifactsTaskStep: DownloadBuildArtifactsTaskStepSchema,
# })
#
#
# def task_step_inputs_serialization_schema_selector(base_object, parent_object):
#     return task_step_inputs_type_schema_map[type(base_object)]()


def remove_skip_values(the_dict, skip_values=pset({None, pvector(), pmap()})):
    return type(the_dict)([
        [key, value]
        for key, value in the_dict.items()
        if value not in tuple(skip_values)
    ])


@marshmallow.decorators.post_dump
def post_dump_remove_skip_values(self, data, many):
    return remove_skip_values(data)


# class TaskStepSchema(marshmallow.Schema):
#     class Meta:
#         ordered = True
#
#     task = marshmallow.fields.String()
#     id_name = marshmallow.fields.String(data_key='name')
#     display_name = marshmallow.fields.String(data_key='displayName')
#     inputs = marshmallow_polyfield.PolyField(
#         serialization_schema_selector=(
#             task_step_inputs_serialization_schema_selector
#         ),
#     )
#     condition = marshmallow.fields.String(allow_none=True)
#
#     post_dump = post_dump_remove_skip_values
#
#
# @attr.s(frozen=True)
# class TaskStep:
#     task = attr.ib()
#     inputs = attr.ib()
#     id_name = attr.ib(default=None)
#     display_name = attr.ib(default=None)
#     condition = attr.ib(default=None)
#
#
# def create_publish_build_artifacts_task_step(path_to_publish, artifact_name):
#     return TaskStep(
#         task='PublishBuildArtifacts@1',
#         display_name='Publish',
#         id_name='publish',
#         inputs=PublishBuildArtifactsTaskStep(
#             path_to_publish=path_to_publish,
#             artifact_name=artifact_name,
#         ),
#     )
#
#
# def create_download_build_artifacts_task_step(download_path, artifact_name):
#     return TaskStep(
#         task='DownloadBuildArtifacts@0',
#         display_name='Download',
#         id_name='download',
#         inputs=DownloadBuildArtifactsTaskStep(
#             download_path=download_path,
#             artifact_name=artifact_name,
#         ),
#     )
#
#
# def create_set_dist_file_path_task(distribution_name, distribution_type):
#     if distribution_type == ciborg.configuration.sdist_install_source:
#         # only_or_no_binary = '--no-binary :all:'
#         extension = '.tar.gz'
#     elif distribution_type == ciborg.configuration.bdist_install_source:
#         # only_or_no_binary = '--only-binary :all:'
#         extension = '.whl'
#     else:
#         raise Exception(
#             'Unexpected distribution type: {!r}'.format(distribution_type),
#         )
#
#     # download_command_format = (
#     #     'python -m pip download --no-deps {only_or_no_binary}'
#     #     + ' --find-links dist/ --dest dist-selected/ {package}'
#     # )
#     # download_command = download_command_format.format(
#     #     only_or_no_binary=only_or_no_binary,
#     #     package=distribution_name,
#     # )
#
#     set_variable_command = (
#         'echo "##vso[task.setvariable variable=DIST_FILE_PATH]'
#         # + '$(ls ${PWD}/dist-selected/*)"'
#         + '$(ls ${{PWD}}/dist/*{})"'.format(extension)
#     )
#
#     return BashStep(
#         display_name='Select distribution file',
#         script='\n'.join([
#             'ls ${PWD}/dist/*',
#             # download_command,
#             set_variable_command,
#         ]),
#         fail_on_stderr=True,
#     )


def create_verify_up_to_date_job(
        environment,
        configuration_path,
        output_path,
        ciborg_requirement,
):
    use_python_version_step = create_use_python_version_task_step(
        version_spec=environment.version,
        architecture='x64',
    )

    installation_step = BashStep(
        display_name='Install ciborg',
        script='\n'.join([
            'python -m pip install --upgrade pip setuptools',
            'python -m pip install "{}"'.format(ciborg_requirement),
        ]),
    )

    generation_command_format = (
        'python -m ciborg azure --configuration {configuration}'
        + ' --output {output}'
    )
    generation_command = generation_command_format.format(
        configuration=configuration_path,
        output=configuration_path.parent / output_path,
    )

    generation_step = BashStep(
        display_name='Generate',
        script='\n'.join([
            generation_command,
        ]),
    )

    verification_step = BashStep(
        display_name='Verify',
        script='\n'.join([
            '[ -z "$(git status --porcelain)" ]',
        ]),
    )

    job = Job(
        id_name='verify_up_to_date',
        display_name='Verify up to date',
        steps=[
            use_python_version_step,
            installation_step,
            generation_step,
            verification_step,
        ],
        pool=Pool(vm_image=environment.vm_image),
    )

    return job


def create_sdist_job(environment):
    checkout_step = CheckoutStep()

    build_step = RunStep(
        name='Build',
        command='\n'.join([
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --source --out-dir dist/ .',
        ]),
    )

    store_artifacts_step = StoreArtifactsStep(path=pathlib.Path('dist'))

    persist_to_workspace_step = PersistToWorkspaceStep(
        root=pathlib.Path('.'),
        paths=[pathlib.Path('dist')],
    )

    sdist_job = Job(
        id_name='sdist',
        docker=[DockerImage(image='python:3.8')],
        macos=None,
        executor=None,
        environment=pmap(),
        steps=[
            checkout_step,
            build_step,
            store_artifacts_step,
            persist_to_workspace_step,
        ],
    )

    return sdist_job


def create_bdist_wheel_pure_job(environment):
    checkout_step = CheckoutStep()

    build_step = RunStep(
        name='Build',
        command='\n'.join([
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --binary --out-dir dist/ .',
        ]),
    )

    store_artifacts_step = StoreArtifactsStep(path=pathlib.Path('dist'))

    persist_to_workspace_step = PersistToWorkspaceStep(
        root=pathlib.Path('.'),
        paths=[pathlib.Path('dist')],
    )

    bdist_job = Job(
        id_name='bdist',
        docker=[DockerImage(image='python:3.8')],
        macos=None,
        executor=None,
        environment=pmap(),
        steps=[
            checkout_step,
            build_step,
            store_artifacts_step,
            persist_to_workspace_step,
        ],
    )

    return bdist_job


# def create_all_job(environment, other_jobs):
#     use_python_version_step = create_use_python_version_task_step(
#         version_spec=environment.version,
#         architecture='x64',
#     )
#
#     this_step = BashStep(
#         display_name='This',
#         script='\n'.join([
#             'python -m this',
#         ]),
#     )
#
#     job = Job(
#         id_name='all',
#         display_name='All',
#         steps=[
#             use_python_version_step,
#             this_step,
#         ],
#         depends_on=other_jobs,
#         pool=Pool(vm_image=environment.vm_image),
#     )
#
#     return job


# class PlatformSchema(marshmallow.Schema):
#     class Meta:
#         ordered = True
#
#     display_name = marshmallow.fields.String()
#
#
# @attr.s(frozen=True)
# class Platform:
#     display_name = attr.ib()
#
#     def identifier(self):
#         return self.display_name.casefold()
#
#
# platforms = {
#     'linux': Platform(display_name='Linux'),
#     'macos': Platform(display_name='macOS'),
#     'windows': Platform(display_name='Windows'),
# }
#

def create_tox_test_job(
        build_job,
        environment,
        distribution_name,
        distribution_type,
):
    steps = pvector()

    steps = steps.append(CheckoutStep())

    select_distribution_file_step = None
    if distribution_type is not None:
        steps = steps.append(AttachWorkspaceStep(at=pathlib.Path()))

        if distribution_type == ciborg.configuration.sdist_install_source:
            # only_or_no_binary = '--no-binary :all:'
            extension = '.tar.gz'
        elif distribution_type == ciborg.configuration.bdist_install_source:
            # only_or_no_binary = '--only-binary :all:'
            extension = '.whl'
        else:
            raise Exception(
                'Unexpected distribution type: {!r}'.format(distribution_type),
            )

        steps = steps.append(RunStep(
            name='Select distribution file',
            command='\n'.join([
                'ls ${PWD}/dist/*',
                'echo "export DIST_FILE_PATH=$(ls ${{PWD}}/dist/*{extension})" >> $BASH_ENV'.format(extension=extension),
            ]),
        ))

    id_pieces = [
        'tox',
        *(
            []
            if environment.tox_environment is None
            else [environment.tox_environment]
        ),
        environment.identifier_string,
    ]

    docker = None
    macos = None
    executor = None

    if environment.platform == ciborg.configuration.linux_platform:
        docker = [
            DockerImage(
                image='python:{version}'.format(
                    version=environment.version.joined_by('.'),
                ),
            ),
        ]
    elif environment.platform == ciborg.configuration.macos_platform:
        macos = MacosExecutor(xcode='10.0.0')

        steps = steps.append(RunStep(
            name='Install pyenv support libraries',
            command='\n'.join([
                '# brew update',
                'brew list readline &>/dev/null || brew install readline',
                'brew list xz &>/dev/null || brew install xz',
            ]),
        ))
        steps = steps.append(RunStep(
            name='Configure pyenv',
            command='\n'.join([
                "echo 'export PYENV_ROOT=${PWD}/.ciborg/pyenv' >> $BASH_ENV",
            ]),
        ))

        cache_key = 'pyenv_macos_{interpreter}_{version}-v2'.format(
            interpreter=environment.interpreter.identifier_string,
            version=environment.version.joined_by('_'),
        )

        steps = steps.append(RestoreCacheStep(
            key=cache_key,
        ))
        steps = steps.append(RunStep(
            name='Install pyenv',
            command='\n'.join([
                "if [ ! -e .ciborg/pyenv ]; then curl https://pyenv.run | bash; fi",
                "echo 'export PATH=${PYENV_ROOT}/bin:${PATH}' >> $BASH_ENV",
                "echo 'export PATH=${PYENV_ROOT}/shims:${PATH}' >> $BASH_ENV",
                '''# echo 'eval '$(pyenv init -)"' >> $BASH_ENV''',
                "# echo 'export CFLAGS=-I$(brew --prefix openssl)/include' >> $BASH_ENV",
                "# echo 'export LDFLAGS=-L$(brew --prefix openssl)/lib' >> $BASH_ENV",
                "echo ----",
                "cat $BASH_ENV",
                "echo ----",
            ]),
        ))
        dotted_version = environment.version.joined_by('.')
        most_recent_matching_version = ' | '.join([
            'pyenv install --list',
            "grep '^  {version}'",
            "grep -v 'dev'",
            "tail -n 1",
        ])

        steps = steps.append(RunStep(
            name='Install {name} {version}'.format(
                name=environment.interpreter.display_string,
                version=dotted_version,
            ),
            command='\n'.join([
                'pyenv --help',
                'set -vx',
                '''pyenv install --skip-existing $({})'''.format(
                    most_recent_matching_version,
                ),
                'pyenv global {version}'.format(
                    version=dotted_version,
                ),
            ]),
        ))
        steps = steps.append(SaveCacheStep(
            key=cache_key,
            paths=[pathlib.Path('.ciborg') / 'pyenv'],
        ))
    elif environment.platform == ciborg.configuration.windows_platform:
        executor = RawExecutor(name='windows/default', shell='bash')

    tox_command = 'python -m tox'

    if distribution_type is not None:
        tox_command += ''' --installpkg="${DIST_FILE_PATH}"'''

    steps = steps.append(RunStep(
        name='Tox',
        command='\n'.join([
            'python -m pip install --quiet --upgrade pip setuptools wheel',
            'python -m pip install tox',
            tox_command,
        ]),
    ))

    job = Job(
        id_name='_'.join(id_pieces),
        docker=docker,
        macos=macos,
        executor=executor,
        environment={
            'TOXENV': environment.tox_env(),
        },
        steps=steps,
        requires=pvector([build_job] if build_job is not None else []),
    )

    return job


@attr.s(frozen=True)
class Environment:
    platform = attr.ib()
    interpreter = attr.ib()
    version = attr.ib()
    architecture = attr.ib()
    display_string = attr.ib()
    identifier_string = attr.ib()
    tox_environment = attr.ib()

    @classmethod
    def build(
            cls,
            platform,
            interpreter,
            version,
            architecture,
            display_string,
            identifier_string,
            tox_environment=None,
    ):
        return cls(
            platform=platform,
            interpreter=interpreter,
            version=version,
            architecture=architecture,
            display_string=display_string,
            identifier_string=identifier_string,
            tox_environment=tox_environment,
        )

    def tox_env(self):
        if self.tox_environment is not None:
            return self.tox_environment

        env = 'py'
        if self.interpreter == 'PyPy':
            env += 'py'
            if self.version[0] == '3':
                env += '3'
        else:
            env += self.version.joined_by('')

        return env


def create_pipeline(configuration, configuration_path, output_path):
    jobs = pvector()

    tooling_environment = Environment.build(
        platform=configuration.tooling_environment.platform,
        interpreter=configuration.tooling_environment.interpreter,
        version=configuration.tooling_environment.version,
        architecture='x64',
        display_string=configuration.tooling_environment.display_name(),
        identifier_string=configuration.tooling_environment.identifier(),
    )

    # verify_job = create_verify_up_to_date_job(
    #     environment=tooling_environment,
    #     configuration_path=configuration_path,
    #     output_path=output_path,
    #     ciborg_requirement=configuration.ciborg_requirement,
    # )
    # jobs = jobs.append(verify_job)

    if configuration.build_sdist:
        sdist_job = create_sdist_job(environment=tooling_environment)
        jobs = jobs.append(sdist_job)

    if configuration.build_wheel == 'universal':
        bdist_job = create_bdist_wheel_pure_job(
            environment=tooling_environment,
        )
        jobs = jobs.append(bdist_job)
    # elif configuration.build_wheel == 'specific':

    build_jobs = {
        ciborg.configuration.sdist_install_source: sdist_job,
        ciborg.configuration.bdist_install_source: bdist_job,
    }

    for environment in configuration.test_environments:
        test_job_environment = Environment.build(
            platform=environment.platform,
            interpreter=environment.interpreter,
            version=environment.version,
            architecture=None,
            display_string=environment.display_name(),
            identifier_string=environment.identifier(),
            tox_environment=environment.tox_environment,
        )

        build_job = build_jobs.get(environment.install_source)

        jobs = jobs.append(
            create_tox_test_job(
                build_job=build_job,
                environment=test_job_environment,
                distribution_name=configuration.name,
                distribution_type=environment.install_source,
            ),
        )

    # all_job = create_all_job(
    #     environment=tooling_environment,
    #     other_jobs=jobs,
    # )
    # jobs = jobs.append(all_job)

    windows_orb = Orb(name='windows', reference='circleci/windows@2.4.0')

    pipeline = Pipeline(
        version=2.1,
        orbs=[windows_orb],
        jobs=jobs,
        workflows=Workflows(
            version=2,
            all=Workflow(jobs=jobs),
        ),
    )

    return pipeline


def ordered_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())


def str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="")


class TidyOrderedDictDumper(yaml.Dumper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.add_representer(
            collections.OrderedDict,
            ordered_dict_representer,
        )

        self.add_representer(
            str,
            str_representer,
        )


def dump_pipeline(pipeline):
    basic_types = PipelineSchema().dump(pipeline)
    dumped = yaml.dump(
        basic_types,
        sort_keys=False,
        Dumper=TidyOrderedDictDumper,
    )

    return dumped


@attr.s(frozen=True)
class IncludeExcludePVectors:
    include = attr.ib(factory=pvector)
    exclude = attr.ib(factory=pvector)


class CheckoutStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class CheckoutStep:
    type: str = 'checkout'


class StoreArtifactsStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    path = marshmallow.fields.String()
    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class StoreArtifactsStep:
    # TODO: should be path
    path: pathlib.Path
    type: str = 'store_artifacts'


class PersistToWorkspaceStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    # TODO: should be path
    root = marshmallow.fields.String()
    # TODO: should be paths
    paths = marshmallow.fields.List(
        marshmallow.fields.String(),
    )
    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class PersistToWorkspaceStep:
    root: pathlib.Path
    paths: typing.List[pathlib.Path]
    type: str = 'persist_to_workspace'


class AttachWorkspaceStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    # TODO: really a path
    at = marshmallow.fields.String()
    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class AttachWorkspaceStep:
    at: pathlib.Path = attr.ib(converter=lambda x: pathlib.Path(x))
    type: str = 'attach_workspace'


class RunStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    command = marshmallow.fields.String()
    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class RunStep:
    name: str
    command: str
    type: str = 'run'


class RestoreCacheStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    key = marshmallow.fields.String()
    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class RestoreCacheStep:
    key: str
    type: str = 'restore_cache'


class SaveCacheStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    key = marshmallow.fields.String()
    # TODO: really paths but...
    paths = marshmallow.fields.List(
        marshmallow.fields.String(),
    )
    type = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class SaveCacheStep:
    key: str
    paths: typing.List[pathlib.Path] = attr.ib(
        converter=lambda x: pvector(pathlib.Path(v) for v in x),
    )
    type: str = 'save_cache'


StepTypesUnion = typing.Union[
    CheckoutStepSchema,
    AttachWorkspaceStepSchema,
    StoreArtifactsStepSchema,
    PersistToWorkspaceStepSchema,
    RunStep,
    RestoreCacheStep,
    SaveCacheStep,
]


step_type_schema_map = pmap({
    CheckoutStep: CheckoutStepSchema,
    AttachWorkspaceStep: AttachWorkspaceStepSchema,
    StoreArtifactsStep: StoreArtifactsStepSchema,
    PersistToWorkspaceStep: PersistToWorkspaceStepSchema,
    RunStep: RunStepSchema,
    RestoreCacheStep: RestoreCacheStepSchema,
    SaveCacheStep: SaveCacheStepSchema,
})


def job_steps_serialization_schema_selector(base_object, parent_object):
    return step_type_schema_map[type(base_object)]()


class DockerImageSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    image = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class DockerImage:
    image: str


class MacosExecutorSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    xcode = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class MacosExecutor:
    xcode: str


class RawExecutorSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    shell = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class RawExecutor:
    name: str
    shell: str


class JobSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    id_name = marshmallow.fields.String()

    # TODO: only want to allow one of these really
    docker = marshmallow.fields.List(
        marshmallow.fields.Nested(DockerImageSchema(), allow_none=True),
    )
    macos = marshmallow.fields.Nested(MacosExecutorSchema(), allow_none=True)
    executor = marshmallow.fields.Nested(RawExecutorSchema(), allow_none=True)

    environment = marshmallow.fields.Dict(
        keys=marshmallow.fields.String(),
        values=marshmallow.fields.String(),
    )
    steps = ciborg.utils.ListAsListOfKeyDictOrString(
        nested=marshmallow_polyfield.PolyField(
            serialization_schema_selector=(
                job_steps_serialization_schema_selector
            ),
        ),
        key='type',
    )

    requires = marshmallow.fields.List(
        marshmallow.fields.Pluck(
            nested='ciborg.circle.JobSchema',
            field_name='id_name',
        ),
    )
    # condition = marshmallow.fields.String(allow_none=True)
    # continue_on_error = marshmallow.fields.Boolean(data_key='continueOnError')
    # steps = marshmallow.fields.List(
    #     marshmallow_polyfield.PolyField(
    #         serialization_schema_selector=(
    #             job_steps_serialization_schema_selector
    #         ),
    #     ),
    # )

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class Job:
    id_name: str

    # TODO: only want to allow one of these really
    docker: typing.Optional[typing.List[DockerImageSchema]]
    macos: typing.Optional[MacosExecutor]
    executor: typing.Optional[RawExecutor]

    environment: typing.Mapping[str, str]
    steps: typing.Sequence[StepTypesUnion]

    requires: pyrsistent.typing.PVector['Job'] = attr.ib(factory=pvector)


class WorkflowSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    jobs = ciborg.utils.ListAsListOfKeyDictOrString(
        nested=marshmallow.fields.Nested(JobSchema()),
        key='id_name',
        only_these=['requires'],
    )

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class Workflow:
    jobs: typing.Sequence[Job]


class WorkflowsSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    version = marshmallow.fields.Integer()
    all = marshmallow.fields.Nested(WorkflowSchema())

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class Workflows:
    version: int
    all: Workflow


class OrbSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    reference = marshmallow.fields.String()

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class Orb:
    name: str
    reference: str


class PipelineSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    version = marshmallow.fields.Float()
    orbs = ciborg.utils.NestedListAsKeyValue(
        nested=OrbSchema(),
        key='name',
        value='reference',
    )
    jobs = ciborg.utils.NestedDict(
        nested=JobSchema(exclude=['requires']),
        key='id_name',
        remove_key=True,
    )
    workflows = marshmallow.fields.Nested(WorkflowsSchema())

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class Pipeline:
    # TODO: float?  auauuahghghhgh
    version: float
    orbs: typing.Sequence[Orb]
    jobs: typing.Sequence[Job]
    workflows: Workflows
