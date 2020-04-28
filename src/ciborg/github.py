import collections

import attr
import marshmallow
import marshmallow_polyfield
from pyrsistent import pvector, pmap, pset
import yaml

import ciborg.azure


def create_tox_test_job(
        build_job,
        environment,
        distribution_name,
        distribution_type,
):
    use_python_version_step = create_setup_python_action_step(
        python_version=environment.version,
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    download_task_step = create_download_build_artifacts_action_step(
        download_path='dist',
        artifact_name='dist',
    )

    select_dist_step = create_set_dist_file_path_task(
        distribution_name=distribution_name,
        distribution_type=distribution_type,
    )

    bash_step = BashStep(
        name='Tox',
        run='\n'.join([
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
        id_name='tox_{platform}_{tox_env}_{dist_type}'.format(
            platform=environment.platform.identifier(),
            tox_env=environment.tox_env(),
            dist_type=build_job.id_name,
        ),
        display_name='Tox - {}'.format(environment.display_name()),
        steps=[
            use_python_version_step,
            checkout_step,
            download_task_step,
            select_dist_step,
            bash_step,
        ],
        needs=[build_job],
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


class BashStepSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String()
    run = marshmallow.fields.String()
    environment = marshmallow.fields.Dict(
        keys=marshmallow.fields.String(),
        values=marshmallow.fields.String(),
        data_key='env',
    )

    post_dump = ciborg.azure.post_dump_remove_skip_values


@attr.s(frozen=True)
class BashStep:
    name = attr.ib()
    run = attr.ib()
    environment = attr.ib(
        default=pmap(),
        converter=lambda x: collections.OrderedDict(sorted(x.items())),
    )


step_type_schema_map = pmap({
    ActionStep: ActionStepSchema,
    BashStep: BashStepSchema,
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
    steps = attr.ib(default=(), converter=pvector)


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
        name='Set up CPython {}'.format(python_version),
        uses='actions/setup-python@v1',
        with_=SetupPythonActionWith(
            python_version=python_version,
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
    if distribution_type == 'sdist':
        # only_or_no_binary = '--no-binary :all:'
        extension = '.tar.gz'
    elif distribution_type == 'bdist':
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

    return BashStep(
        name='Select distribution file',
        run='\n'.join([
            'ls ${PWD}/dist/*',
            set_variable_command,
        ]),
    )


def create_verify_up_to_date_job(
        vm_image,
        configuration_path,
        output_path,
        ciborg_requirement,
):
    setup_python_step = create_setup_python_action_step(
        python_version='3.7',
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    installation_step = BashStep(
        name='Install ciborg',
        run='\n'.join([
            'python -m pip install --upgrade pip setuptools',
            'python -m pip install "{}"'.format(ciborg_requirement),
        ]),
    )

    generation_command_format = (
        'python -m ciborg github --configuration {configuration}'
        + ' --output {output}'
    )
    generation_command = generation_command_format.format(
        configuration=configuration_path,
        output=configuration_path.parent / output_path,
    )

    generation_step = BashStep(
        name='Generate',
        run='\n'.join([
            generation_command,
        ]),
    )

    verification_step = BashStep(
        name='Verify',
        run='\n'.join([
            '[ -z "$(git status --porcelain)" ]',
        ]),
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
        runs_on=vm_image,
    )

    return job


def create_sdist_job(vm_image):
    use_python_version_step = create_setup_python_action_step(
        python_version='3.7',
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    bash_step = BashStep(
        name='Build',
        run='\n'.join([
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --source --out-dir dist/ .',
        ]),
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
        runs_on=vm_image,
    )

    return sdist_job


def create_bdist_wheel_pure_job(vm_image):
    use_python_version_step = create_setup_python_action_step(
        python_version='3.7',
        architecture='x64',
    )

    checkout_step = create_checkout_action_step()

    bash_step = BashStep(
        name='Build',
        run='\n'.join([
            'python -m pip install --quiet --upgrade pip',
            'python -m pip install --quiet --upgrade pep517',
            'python -m pep517.build --binary --out-dir dist/ .',
        ]),
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
        runs_on=vm_image,
    )

    return job


def create_all_job(vm_image, other_jobs):
    use_python_version_step = create_setup_python_action_step(
        python_version='3.7',
        architecture='x64',
    )

    this_step = BashStep(
        name='This',
        run='\n'.join([
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
        needs=other_jobs,
        runs_on=vm_image,
    )

    return job


def create_workflow(configuration, configuration_path, output_path):
    jobs = pvector()

    verify_job = create_verify_up_to_date_job(
        vm_image=ciborg.azure.vm_images['linux'],
        configuration_path=configuration_path,
        output_path=output_path,
        ciborg_requirement=configuration.ciborg_requirement,
    )
    jobs = jobs.append(verify_job)

    if configuration.build_sdist:
        sdist_job = create_sdist_job(vm_image=ciborg.azure.vm_images['linux'])
        jobs = jobs.append(sdist_job)

    if configuration.build_wheel == 'universal':
        bdist_job = create_bdist_wheel_pure_job(
            vm_image=ciborg.azure.vm_images['linux'],
        )
        jobs = jobs.append(bdist_job)
    # elif configuration.build_wheel == 'specific':

    for environment in configuration.test_environments:
        vm_image = ciborg.azure.vm_images[environment.platform]

        test_job_environment = ciborg.azure.Environment(
            platform=vm_image.platform,
            vm_image=vm_image,
            interpreter=environment.interpreter,
            version=environment.version,
            architecture=None,
        )

        build_job = {
            'sdist': sdist_job,
            'bdist': bdist_job,
        }[environment.install_source]

        jobs = jobs.append(
            create_tox_test_job(
                build_job=build_job,
                environment=test_job_environment,
                distribution_name=configuration.name,
                distribution_type=environment.install_source,
            ),
        )

    all_job = create_all_job(vm_image=ciborg.azure.vm_images['linux'], other_jobs=jobs)
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


def dump_workflow(pipeline):
    basic_types = WorkflowSchema().dump(pipeline)
    dumped = yaml.dump(
        basic_types,
        sort_keys=False,
        Dumper=ciborg.azure.TidyOrderedDictDumper,
    )

    return dumped
