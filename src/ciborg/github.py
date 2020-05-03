import collections
import typing

import attr
import marshmallow
import marshmallow_polyfield
import pyrsistent.typing
import yaml

from pyrsistent import pvector, pmap

import ciborg.azure
import ciborg.configuration


def create_tox_test_job(
        build_job,
        environment,
        distribution_name,
        distribution_type,
):
    steps = pvector()

    use_python_version_step = create_setup_python_action_step(
        python_version=environment.version,
        architecture='x64',
    )
    steps = steps.append(use_python_version_step)

    checkout_step = create_checkout_action_step()
    steps = steps.append(checkout_step)

    if distribution_type is not None:
        download_task_step = create_download_build_artifacts_action_step(
            download_path='dist',
            artifact_name='dist',
        )
        steps = steps.append(download_task_step)

        select_dist_step = create_set_dist_file_path_task(
            distribution_name=distribution_name,
            distribution_type=distribution_type,
        )
        steps = steps.append(select_dist_step)

    tox_command = 'python -m tox'

    if distribution_type is not None:
        tox_command += ''' --installpkg="${{ env['DIST_FILE_PATH'] }}"'''

    bash_step = create_bash_step(
        name='Tox',
        commands=[
            'python -m pip install --quiet --upgrade pip setuptools wheel',
            'python -m pip install tox',
            tox_command,
        ],
        environment={
            'TOXENV': environment.tox_env(),
        },
    )
    steps = steps.append(bash_step)

    id_pieces = [
        'tox',
        *(
            []
            if environment.tox_environment is None
            else [environment.tox_environment]
        ),
        environment.identifier_string,
    ]

    display_pieces = [
        'Tox',
        *(
            []
            if environment.tox_environment is None
            else [environment.tox_environment]
        ),
    ]

    job = Job(
        id_name='_'.join(id_pieces),
        display_name='{} - {}'.format(
            ' '.join(display_pieces),
            environment.display_string,
        ),
        steps=steps,
        needs=[] if build_job is None else [build_job],
        runs_on=environment.vm_image,
    )

    return job


def dump_workflow(pipeline):
    basic_types = WorkflowSchema().dump(pipeline)
    dumped = yaml.dump(
        basic_types,
        sort_keys=False,
        Dumper=ciborg.azure.TidyOrderedDictDumper,
    )

    return dumped


class PushSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    branches = marshmallow.fields.List(marshmallow.fields.String)
    tags = marshmallow.fields.List(marshmallow.fields.String)

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class Push:
    branches = attr.ib()
    tags = attr.ib()


class PullRequestSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    branches = marshmallow.fields.List(marshmallow.fields.String)

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class PullRequest:
    branches = attr.ib()


class OnSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    push = marshmallow.fields.Nested(PushSchema())
    pull_request = marshmallow.fields.Nested(PullRequestSchema())

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class On:
    push = attr.ib()
    pull_request = attr.ib()


class SetupPythonActionWithSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    python_version = marshmallow.fields.String(data_key='python-version')
    architecture = marshmallow.fields.String()

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class SetupPythonActionWith:
    python_version = attr.ib()
    architecture = attr.ib()


class UploadArtifactsActionStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    path = marshmallow.fields.String()

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class UploadArtifactsActionStep:
    name = attr.ib()
    path = attr.ib()


class DownloadArtifactActionStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    path = marshmallow.fields.String()

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class DownloadArtifactActionStep:
    name = attr.ib()
    path = attr.ib()


class CheckoutActionStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class CheckoutActionStep:
    pass


task_step_inputs_type_schema_map = pmap({
    SetupPythonActionWith: SetupPythonActionWithSchema,
    UploadArtifactsActionStep: UploadArtifactsActionStepSchema,
    DownloadArtifactActionStep: DownloadArtifactActionStepSchema,
    CheckoutActionStep: CheckoutActionStepSchema,
})


def task_step_inputs_serialization_schema_selector(base_object, parent_object):
    return task_step_inputs_type_schema_map[type(base_object)]()


class ActionStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    uses = marshmallow.fields.String()
    with_ = marshmallow_polyfield.PolyField(
        serialization_schema_selector=(
            task_step_inputs_serialization_schema_selector
        ),
        data_key='with',
    )

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class ActionStep:
    name = attr.ib()
    uses = attr.ib()
    with_ = attr.ib()


def create_bash_step(name, commands, environment=pmap()):
    return RunStep(
        name=name,
        shell='bash',
        run='\n'.join(commands),
        environment=environment,
    )


class RunStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    shell = marshmallow.fields.String()
    run = marshmallow.fields.String()
    environment = marshmallow.fields.Dict(
        keys=marshmallow.fields.String(),
        values=marshmallow.fields.String(),
        data_key='env',
    )

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class RunStep:
    name = attr.ib()
    shell = attr.ib()
    run = attr.ib()
    environment: typing.Mapping[str, str] = attr.ib(
        default=pmap(),
        converter=ciborg.azure.sorted_ordered_dict,
    )


step_type_schema_map = pmap({
    ActionStep: ActionStepSchema,
    RunStep: RunStepSchema,
})


def job_steps_serialization_schema_selector(base_object, parent_object):
    return step_type_schema_map[type(base_object)]()


class JobSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    id_name = marshmallow.fields.String()
    display_name = marshmallow.fields.String(data_key='name')
    runs_on = marshmallow.fields.Pluck(
        nested=ciborg.azure.VmImageSchema,
        field_name='id_name',
        data_key='runs-on',
    )
    needs = marshmallow.fields.List(
        marshmallow.fields.Pluck(
            nested='ciborg.github.JobSchema',
            field_name='id_name',
        ),
    )
    steps = marshmallow.fields.List(
        marshmallow_polyfield.PolyField(
            serialization_schema_selector=(
                job_steps_serialization_schema_selector
            ),
        ),
    )

    # @marshmallow.decorators.post_dump
    # def post_dump(self, data, many):
    #     processed = ciborg.azure.remove_skip_values(data)
    #     processed.pop('id_name')
    #     return processed

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class Job:
    id_name = attr.ib()
    display_name = attr.ib()
    runs_on = attr.ib()
    needs = attr.ib(factory=pvector)
    steps: pyrsistent.typing.PVector[
        typing.Union[ActionStep, RunStep],
    ] = attr.ib(default=pvector(), converter=pvector)


# https://github.com/marshmallow-code/marshmallow/issues/483#issuecomment-229557880
class NestedDict(marshmallow.fields.Nested):
    def __init__(self, nested, key, remove_key=False, *args, **kwargs):
        super(NestedDict, self).__init__(nested, many=True, *args, **kwargs)
        self.key = key
        self.remove_key = remove_key

    def _serialize(self, nested_obj, attr, obj):
        nested_list = super(NestedDict, self)._serialize(nested_obj, attr, obj)
        nested_dict = {item[self.key]: item for item in nested_list}
        for value in nested_dict.values():
            value.pop(self.key)
        return nested_dict

    def _deserialize(self, value, attr, data):
        raw_list = [item for key, item in value.items()]
        nested_list = super(NestedDict, self)._deserialize(raw_list, attr, data)
        return nested_list


class WorkflowSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    on = marshmallow.fields.Nested(OnSchema())
    jobs = NestedDict(
        nested=JobSchema(),
        key='id_name',
        remove_key=True,
    )

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class Workflow:
    name = attr.ib()
    on = attr.ib()
    jobs = attr.ib()


def create_setup_python_action_step(python_version, architecture):
    return ActionStep(
        name='Set up CPython {}'.format(python_version.display_string),
        uses='actions/setup-python@v1',
        with_=SetupPythonActionWith(
            python_version=python_version.display_string,
            architecture=architecture,
        ),
    )


def create_checkout_action_step():
    return ActionStep(
        name='Checkout',
        uses='actions/checkout@v2',
        with_=CheckoutActionStep(),
    )


def create_publish_build_artifacts_task_step(path_to_publish, artifact_name):
    return ActionStep(
        uses='actions/upload-artifact@v2',
        name='Publish',
        with_=DownloadArtifactActionStep(
            path=path_to_publish,
            name=artifact_name,
        ),
    )


def create_download_build_artifacts_action_step(download_path, artifact_name):
    return ActionStep(
        uses='actions/download-artifact@v2',
        name='Download',
        with_=DownloadArtifactActionStep(
            path=download_path,
            name=artifact_name,
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
        'echo ::set-env name=DIST_FILE_PATH::'
        + '$(ls ${{PWD}}/dist/*{extension})'.format(extension=extension)
    )

    return create_bash_step(
        name='Select distribution file',
        commands=[
            'ls ${PWD}/dist/*',
            set_variable_command,
        ],
    )


def create_verify_up_to_date_job(
        environment,
        configuration_path,
        output_path,
        ciborg_requirement,
):
    setup_python_step = create_setup_python_action_step(
        python_version=environment.version,
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    installation_step = create_bash_step(
        name='Install ciborg',
        commands=[
            'python -m pip install --upgrade pip setuptools',
            'python -m pip install "{}"'.format(ciborg_requirement),
        ],
    )

    generation_command_format = (
        'python -m ciborg github --configuration {configuration}'
        + ' --output {output}'
    )
    generation_command = generation_command_format.format(
        configuration=configuration_path,
        output=configuration_path.parent / output_path,
    )

    generation_step = create_bash_step(
        name='Generate',
        commands=[
            generation_command,
        ],
    )

    verification_step = create_bash_step(
        name='Verify',
        commands=[
            '[ -z "$(git status --porcelain)" ]',
        ],
    )

    job = Job(
        id_name='verify_up_to_date',
        display_name='Verify up to date',
        steps=[
            setup_python_step,
            checkout_step,
            installation_step,
            generation_step,
            verification_step,
        ],
        runs_on=environment.vm_image,
    )

    return job


def create_sdist_job(environment):
    use_python_version_step = create_setup_python_action_step(
        python_version=environment.version,
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    bash_step = create_bash_step(
        name='Build',
        commands=[
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --source --out-dir dist/ .',
        ],
    )

    publish_task_step = create_publish_build_artifacts_task_step(
        path_to_publish='dist/',
        artifact_name='dist',
    )

    sdist_job = Job(
        id_name='sdist',
        display_name='Build sdist',
        steps=[
            use_python_version_step,
            checkout_step,
            bash_step,
            publish_task_step,
        ],
        runs_on=environment.vm_image,
    )

    return sdist_job


def create_bdist_wheel_pure_job(environment):
    use_python_version_step = create_setup_python_action_step(
        python_version=environment.version,
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    bash_step = create_bash_step(
        name='Build',
        commands=[
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --binary --out-dir dist/ .',
        ],
    )

    publish_task_step = create_publish_build_artifacts_task_step(
        path_to_publish='dist/',
        artifact_name='dist',
    )

    job = Job(
        id_name='bdist',
        display_name='Build pure wheel',
        steps=[
            use_python_version_step,
            checkout_step,
            bash_step,
            publish_task_step,
        ],
        runs_on=environment.vm_image,
    )

    return job


def create_all_job(environment, other_jobs):
    use_python_version_step = create_setup_python_action_step(
        python_version=environment.version,
        architecture='x64',
    )

    this_step = create_bash_step(
        name='This',
        commands=[
            'python -m this',
        ],
    )

    job = Job(
        id_name='all',
        display_name='All',
        steps=[
            use_python_version_step,
            this_step,
        ],
        needs=other_jobs,
        runs_on=environment.vm_image,
    )

    return job


def create_workflow(configuration, configuration_path, output_path):
    jobs = pvector()

    tooling_environment = ciborg.azure.Environment.build(
        platform=configuration.tooling_environment.platform,
        interpreter=configuration.tooling_environment.interpreter,
        version=configuration.tooling_environment.version,
        architecture='x64',
        display_string=configuration.tooling_environment.display_name(),
        identifier_string=configuration.tooling_environment.identifier(),
    )

    verify_job = create_verify_up_to_date_job(
        environment=tooling_environment,
        configuration_path=configuration_path,
        output_path=output_path,
        ciborg_requirement=configuration.ciborg_requirement,
    )

    jobs = jobs.append(verify_job)

    if configuration.build_sdist:
        sdist_job = create_sdist_job(
            environment=tooling_environment,
        )
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
        vm_image = ciborg.azure.vm_images[environment.platform]

        test_job_environment = ciborg.azure.Environment(
            platform=vm_image.platform,
            vm_image=vm_image,
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

    all_job = create_all_job(environment=tooling_environment, other_jobs=jobs)
    jobs = jobs.append(all_job)

    pipeline = Workflow(
        name='CI',
        on=On(
            push=Push(branches=['master'], tags=['v*']),
            pull_request=PullRequest(branches=['*']),
        ),
        jobs=jobs,
    )

    return pipeline
