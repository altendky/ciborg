import collections
import typing

import attr
import importlib_resources
import marshmallow
import marshmallow_polyfield
import yaml

from pyrsistent import pvector, pmap, pset

import ciborg.configuration
import ciborg.data


tooling_python_version = (
    ciborg.configuration.python_version_by_identifier_string['3.7']
)


def load_template():
    with importlib_resources.open_text(ciborg.data, 'azure.yml') as file:
        template = yaml.safe_load(file)

    return template


def create_use_python_version_task_step(version_spec, architecture):
    return TaskStep(
        task='UsePythonVersion@0',
        inputs=UsePythonVersionTaskStepInputs(
            version_spec=version_spec.joined_by('.'),
            architecture=architecture,
        ),
    )


def create_publish_build_artifacts_task_step(path_to_publish, artifact_name):
    return TaskStep(
        task='PublishBuildArtifacts@1',
        display_name='Publish',
        id_name='publish',
        inputs=PublishBuildArtifactsTaskStep(
            path_to_publish=path_to_publish,
            artifact_name=artifact_name,
        ),
    )


def create_download_build_artifacts_task_step(download_path, artifact_name):
    return TaskStep(
        task='DownloadBuildArtifacts@0',
        display_name='Download',
        id_name='download',
        inputs=DownloadBuildArtifactsTaskStep(
            download_path=download_path,
            artifact_name=artifact_name,
        ),
    )


def create_set_dist_file_path_task(distribution_name, distribution_type):
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

    # download_command_format = (
    #     'python -m pip download --no-deps {only_or_no_binary}'
    #     + ' --find-links dist/ --dest dist-selected/ {package}'
    # )
    # download_command = download_command_format.format(
    #     only_or_no_binary=only_or_no_binary,
    #     package=distribution_name,
    # )

    set_variable_command = (
        'echo "##vso[task.setvariable variable=DIST_FILE_PATH]'
        # + '$(ls ${PWD}/dist-selected/*)"'
        + '$(ls ${{PWD}}/dist/*{})"'.format(extension)
    )

    return BashStep(
        display_name='Select distribution file',
        script='\n'.join([
            'ls ${PWD}/dist/*',
            # download_command,
            set_variable_command,
        ]),
        fail_on_stderr=True,
    )


def create_verify_up_to_date_job(
        vm_image,
        configuration_path,
        output_path,
        ciborg_requirement,
):
    use_python_version_step = create_use_python_version_task_step(
        version_spec=tooling_python_version,
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
        pool=Pool(vm_image=vm_image),
    )

    return job


def create_sdist_job(vm_image):
    use_python_version_step = create_use_python_version_task_step(
        version_spec=tooling_python_version,
        architecture='x64',
    )

    bash_step = BashStep(
        display_name='Build',
        script='\n'.join([
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --source --out-dir dist/ .',
        ]),
    )

    publish_task_step = create_publish_build_artifacts_task_step(
        path_to_publish='$(System.DefaultWorkingDirectory)/dist/',
        artifact_name='dist',
    )

    sdist_job = Job(
        id_name='sdist',
        display_name='Build sdist',
        steps=[
            use_python_version_step,
            bash_step,
            publish_task_step,
        ],
        pool=Pool(vm_image=vm_image),
    )

    return sdist_job


def create_bdist_wheel_pure_job(vm_image):
    use_python_version_step = create_use_python_version_task_step(
        version_spec=tooling_python_version,
        architecture='x64',
    )

    bash_step = BashStep(
        display_name='Build',
        script='\n'.join([
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --binary --out-dir dist/ .',
        ]),
    )

    publish_task_step = create_publish_build_artifacts_task_step(
        path_to_publish='$(System.DefaultWorkingDirectory)/dist/',
        artifact_name='dist',
    )

    job = Job(
        id_name='bdist',
        display_name='Build pure wheel',
        steps=[
            use_python_version_step,
            bash_step,
            publish_task_step,
        ],
        pool=Pool(vm_image=vm_image),
    )

    return job


def create_all_job(vm_image, other_jobs):
    use_python_version_step = create_use_python_version_task_step(
        version_spec=tooling_python_version,
        architecture='x64',
    )

    this_step = BashStep(
        display_name='This',
        script='\n'.join([
            'python -m this',
        ]),
    )

    job = Job(
        id_name='all',
        display_name='All',
        steps=[
            use_python_version_step,
            this_step,
        ],
        depends_on=other_jobs,
        pool=Pool(vm_image=vm_image),
    )

    return job


class PlatformSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    display_name = marshmallow.fields.String()


@attr.s(frozen=True)
class Platform:
    display_name = attr.ib()

    def identifier(self):
        return self.display_name.casefold()


platforms = {
    'linux': Platform(display_name='Linux'),
    'macos': Platform(display_name='macOS'),
    'windows': Platform(display_name='Windows'),
}


class VmImageSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    id_name = marshmallow.fields.String()
    display_name = marshmallow.fields.String()
    platform = marshmallow.fields.Nested(PlatformSchema)


@attr.s(frozen=True)
class VmImage:
    id_name = attr.ib()
    display_name = attr.ib()
    platform = attr.ib()


vm_images = {
    ciborg.configuration.linux_platform: VmImage(
        platform=platforms['linux'],
        display_name=platforms['linux'].display_name,
        id_name='ubuntu-latest',
    ),
    ciborg.configuration.macos_platform: VmImage(
        platform=platforms['macos'],
        display_name=platforms['macos'].display_name,
        id_name='macOS-latest',
    ),
    ciborg.configuration.windows_platform: VmImage(
        platform=platforms['windows'],
        display_name=platforms['windows'].display_name,
        id_name='windows-latest',
    ),
}

# @attr.s(frozen=True)
# class Platform:
#     display_name = attr.ib()
#
#
# class Platforms(enum.Enum):
#     linux = Platform(display_name='Linux')
#     macos = Platform(display_name='macOS')
#     windows = Platform(display_name='Windows')
#
#
# @attr.s(frozen=True)
# class VmImage:
#     id_name = attr.ib()
#     display_name = attr.ib()
#     platform = attr.ib()
#
#
# class VmImages(enum.Enum):
#     linux = VmImage(
#         platform=Platforms.linux,
#         display_name=Platforms.linux.value.display_name,
#         id_name='ubuntu-16.04',
#     )
#     macos = VmImage(
#         platform=Platforms.macos,
#         display_name=Platforms.macos.value.display_name,
#         id_name='macOS-10.13',
#     )
#     windows = VmImage(
#         platform=Platforms.windows,
#         display_name=Platforms.windows.value.display_name,
#         id_name='vs2017-win2016',
#     )


# vm_images_per_platform = pmap({
#     Platforms.linux: [VmImages.linux],
#     Platforms.macos: [VmImages.macos],
#     Platforms.windows: [VmImages.windows],
# })


# default_vm_images_per_platform = pmap({
#     linux: VmImages.linux,
#     macos: VmImages.macos,
#     windows: VmImages.windows,
# })


@attr.s(frozen=True)
class Environment:
    platform = attr.ib()
    vm_image = attr.ib()
    interpreter = attr.ib()
    version = attr.ib()
    architecture = attr.ib()
    display_string = attr.ib()
    identifier_string = attr.ib()

    @classmethod
    def build(cls, platform, interpreter, version, architecture):
        return cls(
            platform=platform,
            vm_image=vm_images[platform],
            interpreter=interpreter,
            version=version,
            architecture=architecture,
        )

    def tox_env(self):
        env = 'py'
        if self.interpreter == 'PyPy':
            env += 'py'
            if self.version[0] == '3':
                env += '3'
        else:
            env += self.version.joined_by('')

        return env

    def matrix_version(self):
        if self.interpreter == 'CPython':
            return self.version

        return 'pypy{}'.format(self.version[0])


def create_tox_test_job(
        build_job,
        environment,
        distribution_name,
        distribution_type,
):
    use_python_version_step = create_use_python_version_task_step(
        version_spec=environment.version,
        architecture='x64',
    )

    download_task_step = create_download_build_artifacts_task_step(
        download_path='$(System.DefaultWorkingDirectory)/',
        artifact_name='dist',
    )

    select_dist_step = create_set_dist_file_path_task(
        distribution_name=distribution_name,
        distribution_type=distribution_type,
    )

    bash_step = BashStep(
        display_name='Tox',
        script='\n'.join([
            'python -m pip install --quiet --upgrade pip setuptools wheel',
            'python -m pip install tox',
            'python -m tox --installpkg="${DIST_FILE_PATH}"',
        ]),
        environment={
            'DIST_FILE_PATH': '$(DIST_FILE_PATH)',
            'TOXENV': environment.tox_env(),
        },
    )

    job = Job(
        id_name='tox_{}'.format(environment.identifier_string),
        display_name='Tox - {}'.format(environment.display_string),
        steps=[
            use_python_version_step,
            download_task_step,
            select_dist_step,
            bash_step,
        ],
        depends_on=[build_job],
        pool=Pool(vm_image=environment.vm_image),
    )

    return job


def create_pipeline(configuration, configuration_path, output_path):
    jobs = pvector()

    verify_job = create_verify_up_to_date_job(
        vm_image=vm_images[ciborg.configuration.linux_platform],
        configuration_path=configuration_path,
        output_path=output_path,
        ciborg_requirement=configuration.ciborg_requirement,
    )
    jobs = jobs.append(verify_job)

    if configuration.build_sdist:
        sdist_job = create_sdist_job(
            vm_image=vm_images[ciborg.configuration.linux_platform],
        )
        jobs = jobs.append(sdist_job)

    if configuration.build_wheel == 'universal':
        bdist_job = create_bdist_wheel_pure_job(
            vm_image=vm_images[ciborg.configuration.linux_platform],
        )
        jobs = jobs.append(bdist_job)
    # elif configuration.build_wheel == 'specific':

    for environment in configuration.test_environments:
        vm_image = vm_images[environment.platform]

        test_job_environment = Environment(
            platform=vm_image.platform,
            vm_image=vm_image,
            interpreter=environment.interpreter,
            version=environment.version,
            architecture=None,
            display_string=environment.display_name(),
            identifier_string=environment.identifier(),
        )

        build_job = {
            ciborg.configuration.sdist_install_source: sdist_job,
            ciborg.configuration.bdist_install_source: bdist_job,
        }[environment.install_source]

        jobs = jobs.append(
            create_tox_test_job(
                build_job=build_job,
                environment=test_job_environment,
                distribution_name=configuration.name,
                distribution_type=environment.install_source,
            ),
        )

    all_job = create_all_job(
        vm_image=vm_images[ciborg.configuration.linux_platform],
        other_jobs=jobs,
    )
    jobs = jobs.append(all_job)

    stage = Stage(
        id_name='main',
        display_name='Main',
        jobs=jobs,
    )

    pipeline = Pipeline(
        name=configuration.name,
        stages=pvector([stage]),
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
    dumped = yaml.dump(basic_types, sort_keys=False, Dumper=TidyOrderedDictDumper)

    return dumped


def remove_skip_values(the_dict, skip_values=pset({None, pvector(), pmap()})):
    return type(the_dict)([
        [key, value]
        for key, value in the_dict.items()
        if value not in tuple(skip_values)
    ])


@marshmallow.decorators.post_dump
def post_dump_remove_skip_values(self, data, many):
    return remove_skip_values(data)


class IncludeExcludePVectorsSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    include = marshmallow.fields.List(marshmallow.fields.String())
    exclude = marshmallow.fields.List(marshmallow.fields.String())

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class IncludeExcludePVectors:
    include = attr.ib(factory=pvector)
    exclude = attr.ib(factory=pvector)


class TriggerSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    batch = marshmallow.fields.Boolean()
    branches = marshmallow.fields.Nested(IncludeExcludePVectorsSchema())
    tags = marshmallow.fields.Nested(IncludeExcludePVectorsSchema())
    paths = marshmallow.fields.Nested(IncludeExcludePVectorsSchema())

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class Trigger:
    batch = attr.ib(default=False)
    branches = attr.ib(factory=IncludeExcludePVectors)
    tags = attr.ib(factory=IncludeExcludePVectors)
    paths = attr.ib(factory=IncludeExcludePVectors)


class OrderedDictField(marshmallow.fields.Mapping):
    # https://github.com/marshmallow-code/marshmallow/pull/1098
    mapping_type = collections.OrderedDict


class UsePythonVersionTaskStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    architecture = marshmallow.fields.String()
    version_spec = marshmallow.fields.String(data_key='versionSpec')


@attr.s(frozen=True)
class UsePythonVersionTaskStepInputs:
    architecture = attr.ib()
    version_spec = attr.ib()


class PublishBuildArtifactsTaskStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    path_to_publish = marshmallow.fields.String(data_key='pathToPublish')
    artifact_name = marshmallow.fields.String(data_key='artifactName')


@attr.s(frozen=True)
class PublishBuildArtifactsTaskStep:
    path_to_publish = attr.ib()
    artifact_name = attr.ib()


class DownloadBuildArtifactsTaskStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    download_path = marshmallow.fields.String(data_key='downloadPath')
    artifact_name = marshmallow.fields.String(data_key='artifactName')


@attr.s(frozen=True)
class DownloadBuildArtifactsTaskStep:
    download_path = attr.ib()
    artifact_name = attr.ib()


task_step_inputs_type_schema_map = pmap({
    UsePythonVersionTaskStepInputs: UsePythonVersionTaskStepSchema,
    PublishBuildArtifactsTaskStep: PublishBuildArtifactsTaskStepSchema,
    DownloadBuildArtifactsTaskStep: DownloadBuildArtifactsTaskStepSchema,
})


def task_step_inputs_serialization_schema_selector(base_object, parent_object):
    return task_step_inputs_type_schema_map[type(base_object)]()


class TaskStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    task = marshmallow.fields.String()
    id_name = marshmallow.fields.String(data_key='name')
    display_name = marshmallow.fields.String(data_key='displayName')
    inputs = marshmallow_polyfield.PolyField(
        serialization_schema_selector=(
            task_step_inputs_serialization_schema_selector
        ),
    )
    condition = marshmallow.fields.String(allow_none=True)

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class TaskStep:
    task = attr.ib()
    inputs = attr.ib()
    id_name = attr.ib(default=None)
    display_name = attr.ib(default=None)
    condition = attr.ib(default=None)


class BashStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    script = marshmallow.fields.String(data_key='bash')
    display_name = marshmallow.fields.String(data_key='displayName')
    fail_on_stderr = marshmallow.fields.Boolean(data_key='failOnStderr')
    environment = marshmallow.fields.Dict(
        keys=marshmallow.fields.String(),
        values=marshmallow.fields.String(),
        data_key='env',
    )

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class BashStep:
    script = attr.ib()
    display_name = attr.ib()
    fail_on_stderr = attr.ib(default=True)
    environment = attr.ib(
        default=pmap(),
        converter=lambda x: collections.OrderedDict(sorted(x.items())),
    )


class PoolSchema(marshmallow.Schema):
    vm_image = marshmallow.fields.Pluck(
        nested=VmImageSchema,
        field_name='id_name',
        data_key='vmImage',
    )


@attr.s(frozen=True)
class Pool:
    vm_image = attr.ib()


step_type_schema_map = pmap({
    BashStep: BashStepSchema,
    TaskStep: TaskStepSchema,
})


def job_steps_serialization_schema_selector(base_object, parent_object):
    return step_type_schema_map[type(base_object)]()


class JobSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    id_name = marshmallow.fields.String(data_key='job')
    display_name = marshmallow.fields.String(data_key='displayName')
    pool = marshmallow.fields.Nested(PoolSchema())
    depends_on = marshmallow.fields.List(
        marshmallow.fields.Pluck(
            nested='ciborg.azure.JobSchema',
            field_name='id_name',
        ),
        data_key='dependsOn',
    )
    condition = marshmallow.fields.String(allow_none=True)
    continue_on_error = marshmallow.fields.Boolean(data_key='continueOnError')
    steps = marshmallow.fields.List(
        marshmallow_polyfield.PolyField(
            serialization_schema_selector=(
                job_steps_serialization_schema_selector
            ),
        ),
    )

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class Job:
    id_name = attr.ib()
    display_name = attr.ib()
    pool = attr.ib()
    depends_on = attr.ib(factory=pvector)
    condition = attr.ib(default=None)
    continue_on_error = attr.ib(default=True)
    steps = attr.ib(default=(), converter=pvector)


class StageSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    id_name = marshmallow.fields.String(data_key='stage')
    display_name = marshmallow.fields.String(data_key='displayName')
    depends_on = marshmallow.fields.List(
        marshmallow.fields.String(),
        data_key='dependsOn',
    )
    condition = marshmallow.fields.String(allow_none=True)
    jobs = marshmallow.fields.List(marshmallow.fields.Nested(JobSchema()))

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class Stage:
    id_name = attr.ib()
    display_name = attr.ib()
    depends_on = attr.ib(factory=pvector)
    condition = attr.ib(default=None)
    jobs = attr.ib(factory=pvector)


class PipelineSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    trigger = marshmallow.fields.Nested(TriggerSchema())
    stages = marshmallow.fields.List(marshmallow.fields.Nested(StageSchema()))

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class Pipeline:
    name = attr.ib()
    trigger = attr.ib(factory=Trigger)
    stages = attr.ib(factory=list)


# @attr.s(frozen=True)
# class IncludeExcludeStringTuples:
#     include = attr.ib(factory=tuple, type=typing.Tuple[str])
#     exclude = attr.ib(factory=tuple, type=typing.Tuple[str])
#
#
# @attr.s(frozen=True)
# class Trigger:
#     batch = attr.ib(default=False, type=bool)
#     branches = attr.ib(
#         factory=IncludeExcludeStringTuples,
#         type=IncludeExcludeStringTuples,
#     )
#     tags = attr.ib(
#         factory=IncludeExcludeStringTuples,
#         type=IncludeExcludeStringTuples,
#     )
#     paths = attr.ib(
#         factory=IncludeExcludeStringTuples,
#         type=IncludeExcludeStringTuples,
#     )
#
# factory_hints = pyrsistent.pmap({
#     pyrsistent.pvector: pyrsistent.typing.PVector,
#     pyrsistent.pmap: pyrsistent.typing.PMap,
#     tuple: typing.Tuple,
# })
#
# def collection_attribute(type, hint, *args, **kwargs):
#     return attr.ib(
#         factory=type,
#         type=factory_hints
#     )
#
# # factory_hints = pyrsistent.PMap((
# #     ('')
# # ))
#
# @attr.s(frozen=True)
# class BashStep:
#     id_name = attr.ib(type=str)
#     display_name = attr.ib(type=str)
#     script = attr.ib(
#         factory=pyrsistent.PVector,
#         type=pyrsistent.typing.PVector[str],
#     )
#     fail_on_stderr = attr.ib(default=True, type=bool)
#     environment = attr.ib(factory=dict)
#
#
# @attr.s(frozen=True)
# class Job:
#     name = attr.ib(type=str)
#     display_name = attr.ib(type=str)
#     depends_on = attr.ib(factory=tuple, type=typing.Tuple['Job'])
#     condition = attr.ib(default=None, type=typing.Optional[str])
#     continue_on_error = attr.ib(default=True, type=bool)
#     steps = attr.ib(factory=tuple, type=typing.Tuple[Step])
#
#
# @attr.s(frozen=True)
# class Stage:
#     id_name = attr.ib(type=str)
#     display_name = attr.ib(type=str)
#     depends_on = attr.ib(factory=tuple, type=typing.Tuple['Stage'])
#     condition = attr.ib(default=None, type=typing.Optional[str])
#     jobs = attr.ib(factory=tuple, type=typing.List[Job])
#
#
# @attr.s(frozen=True)
# class Pipeline:
#     name = attr.ib(type=str)
#     trigger = attr.ib(factory=Trigger, type=Trigger)
#     stages = attr.ib(factory=list, type=typing.List[Stage])



# @attr.s(frozen=True)
# class ContainerResource:
#     pass
#
#
# @attr.s(frozen=True)
# class RepositoryResource:
#     pass
#
#
# @attr.s(frozen=True)
# class PipelineResources:
#     containers = attr.ib(factory=list, type=typing.List[ContainerResource])
#     repositories = attr.ib(factory=list, type=typing.List[RepositoryResource])
#
#
# @attr.s(frozen=True)
# class Pipeline:
#     name = attr.ib(type=str)
#     resources = attr.ib(factory=PipelineResources, type=PipelineResources)
#     variables = attr.ib()
#
#
# @attr.s(frozen=True)
# class Stage:
#     name = attr.ib(type=str)
#     display_name = attr.ib(type=str)
#     depends_on = attr.ib(factory=list, type=typing.List['Stage']
#
#
# @attr.s(frozen=True)
# class Job:
#     pass
