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


def remove_skip_values(the_dict, skip_values=pset({None, pvector(), pmap()})):
    return type(the_dict)([
        [key, value]
        for key, value in the_dict.items()
        if value not in tuple(skip_values)
    ])


@marshmallow.decorators.post_dump
def post_dump_remove_skip_values(self, data, many):
    return remove_skip_values(data)


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


def create_tox_test_job(
        build_job,
        environment,
        distribution_name,
        distribution_type,
        pyenv_job,
):
    steps: pyrsistent.typing.PVector[StepTypesUnion] = pvector()

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

        # steps = steps.append(create_brew_prepare_for_pyenv_step())
        steps = steps.append(RunStep(
            name='Configure pyenv',
            command='\n'.join([
                "echo 'export PYENV_ROOT=${PWD}/.ciborg/pyenv' >> $BASH_ENV",
                "echo 'export PATH=${PYENV_ROOT}/bin:${PATH}' >> $BASH_ENV",
                "echo 'export PATH=${PYENV_ROOT}/shims:${PATH}' >> $BASH_ENV",
            ]),
        ))

        cache_key = 'pyenv_macos_{interpreter}_{version}-v3'.format(
            interpreter=environment.interpreter.identifier_string,
            version=environment.version.joined_by('_'),
        )

        steps = steps.append(RestoreCacheStep(key=cache_key))
        # steps = steps.append(create_install_pyenv_step())
        # steps = steps.append(create_pyenv_install_python_step(environment))
        # steps = steps.append(SaveCacheStep(
        #     key=cache_key,
        #     paths=[pathlib.Path('.ciborg') / 'pyenv'],
        # ))
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

    requires = pvector()
    if pyenv_job is not None:
        requires = requires.append(pyenv_job)
    if build_job is not None:
        requires = requires.append(build_job)

    if len(requires) == 0:
        requires = None

    job = Job(
        id_name='_'.join(id_pieces),
        docker=docker,
        macos=macos,
        executor=executor,
        environment={
            'TOXENV': environment.tox_env(),
        },
        steps=steps,
        requires=requires,
    )

    return job


def create_pyenv_install_job(environment):
    steps: pyrsistent.typing.PVector[StepTypesUnion] = pvector()

    id_pieces = [
        'pyenv',
        environment.identifier(),
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

        steps = steps.append(create_brew_prepare_for_pyenv_step())
        steps = steps.append(RunStep(
            name='Configure pyenv',
            command='\n'.join([
                "echo 'export PYENV_ROOT=${PWD}/.ciborg/pyenv' >> $BASH_ENV",
            ]),
        ))

        cache_key = 'pyenv_{platform}_{interpreter}_{version}-v3'.format(
            platform=environment.platform.identifier_string,
            interpreter=environment.interpreter.identifier_string,
            version=environment.version.joined_by('_'),
        )

        steps = steps.append(RestoreCacheStep(key=cache_key))
        steps = steps.append(create_install_pyenv_step())
        steps = steps.append(create_pyenv_install_python_step(environment))
        steps = steps.append(SaveCacheStep(
            key=cache_key,
            paths=[pathlib.Path('.ciborg') / 'pyenv'],
        ))
    elif environment.platform == ciborg.configuration.windows_platform:
        executor = RawExecutor(name='windows/default', shell='bash')

        steps = steps.append(RunStep(
            name='Configure pyenv',
            command='\n'.join([
                "echo 'export PYENV_ROOT=${PWD}/.ciborg/pyenv' >> $BASH_ENV",
            ]),
        ))

        cache_key = 'pyenv_{platform}_{interpreter}_{version}-v5'.format(
            platform=environment.platform.identifier_string,
            interpreter=environment.interpreter.identifier_string,
            version=environment.version.joined_by('_'),
        )

        steps = steps.append(RestoreCacheStep(key=cache_key))
        steps = steps.append(create_install_pyenv_win_step())
        steps = steps.append(create_pyenv_install_python_step(environment))
        steps = steps.append(SaveCacheStep(
            key=cache_key,
            paths=[pathlib.Path('.ciborg') / 'pyenv'],
        ))

    job = Job(
        id_name='_'.join(id_pieces),
        docker=docker,
        macos=macos,
        executor=executor,
        steps=steps,
    )

    return job


def create_brew_prepare_for_pyenv_step():
    return RunStep(
        name='Install pyenv support libraries',
        command='\n'.join([
            '# brew update',
            'brew list readline &>/dev/null || brew install readline',
            'brew list xz &>/dev/null || brew install xz',
        ]),
    )


def create_install_pyenv_step():
    create_install_pyenv_step = RunStep(
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
    )
    return create_install_pyenv_step


def create_install_pyenv_win_step():
    step = RunStep(
        name='Install pyenv',
        command='\n'.join([
            "if [ ! -e ${PYENV_ROOT} ]; then git clone https://github.com/pyenv-win/pyenv-win pyenv-win; mkdir -p $(dirname ${PYENV_ROOT}); mv pyenv-win/pyenv-win ${PYENV_ROOT}; fi",
            "echo 'export PATH=${PYENV_ROOT}/bin:${PATH}' >> $BASH_ENV",
            "echo 'export PATH=${PYENV_ROOT}/shims:${PATH}' >> $BASH_ENV",
            "echo ----",
            "cat $BASH_ENV",
            "echo ----",
        ]),
    )
    return step


def create_pyenv_install_python_step(environment):
    dotted_version = environment.version.joined_by('.')
    most_recent_matching_version = ' | '.join([
        'pyenv install --list',
        r"sed -n 's/^\s\+\({version}[^\s]*\)/\1/p'".format(version=dotted_version),
        "grep -v 'dev'",
        "tail -n 1",
    ])
    pyenv_install_python_step = RunStep(
        name='Install {name} {version}'.format(
            name=environment.interpreter.display_string,
            version=dotted_version,
        ),
        command='\n'.join([
            'echo $PATH',
            "ls ${PYENV_ROOT} || true",
            "ls ${PYENV_ROOT}/bin || true",
            "ls ${PYENV_ROOT}/shims || true",
            'pyenv --help',
            'set -vx',
            'export CIBORG_PYTHON_VERSION=$({})'''.format(
                most_recent_matching_version,
            ),
            'echo ${CIBORG_PYTHON_VERSION}',
            'pyenv install --skip-existing ${CIBORG_PYTHON_VERSION}',
            'pyenv global ${CIBORG_PYTHON_VERSION}',
        ]),
    )
    return pyenv_install_python_step


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


def pyenv_environment_from_configuration_environment(environment):
    return attr.evolve(environment, install_source=None, tox_environment=None)


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
    else:
        sdist_job = None

    if configuration.build_wheel == 'universal':
        bdist_job = create_bdist_wheel_pure_job(
            environment=tooling_environment,
        )
        jobs = jobs.append(bdist_job)
    else:
        bdist_job = None
    # elif configuration.build_wheel == 'specific':

    build_jobs = {
        ciborg.configuration.sdist_install_source: sdist_job,
        ciborg.configuration.bdist_install_source: bdist_job,
    }

    pyenv_environments = {
        pyenv_environment_from_configuration_environment(environment)
        for environment in configuration.test_environments
    }

    pyenv_jobs = {
        environment: create_pyenv_install_job(environment)
        for environment in pyenv_environments
        if environment.platform != ciborg.configuration.linux_platform
    }

    jobs = jobs.extend(sorted(pyenv_jobs.values()))

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
                pyenv_job=pyenv_jobs.get(
                    pyenv_environment_from_configuration_environment(
                        environment,
                    )
                ),
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
    at: pathlib.Path = attr.ib(converter=pathlib.Path)
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


def to_pvector_of_paths(x) -> pyrsistent.typing.PVector[pathlib.Path]:
    return pvector(pathlib.Path(v) for v in x)


@attr.dataclass(frozen=True)
class SaveCacheStep:
    key: str
    paths: typing.List[pathlib.Path] = attr.ib(converter=to_pvector_of_paths)
    type: str = 'save_cache'


StepTypesUnion = typing.Union[
    CheckoutStep,
    AttachWorkspaceStep,
    StoreArtifactsStep,
    PersistToWorkspaceStep,
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

    post_dump = post_dump_remove_skip_values


@attr.dataclass(frozen=True)
class Job:
    id_name: str

    # TODO: only want to allow one of these really
    docker: typing.Optional[typing.List[DockerImage]]
    macos: typing.Optional[MacosExecutor]
    executor: typing.Optional[RawExecutor]

    steps: typing.Sequence[StepTypesUnion]

    environment: typing.Mapping[str, str] = attr.ib(factory=pmap)

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
