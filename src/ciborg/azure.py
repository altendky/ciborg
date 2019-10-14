import collections
import typing

import attr
import importlib_resources
import marshmallow
import marshmallow_polyfield
import yaml

from pyrsistent import pvector, pmap, pset

import ciborg.data


def load_template():
    with importlib_resources.open_text(ciborg.data, 'azure.yml') as file:
        template = yaml.safe_load(file)

    return template


def create_use_python_version_task_step(version_spec, architecture):
    return TaskStep(
        task='UsePythonVersion@0',
        inputs=UsePythonVersionTaskStep(
            version_spec=version_spec,
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


def create_sdist_job():
    use_python_version_step = create_use_python_version_task_step(
        version_spec='3.7',
        architecture='x64',
    )

    bash_step = BashStep(
        display_name='Build',
        script='\n'.join([
            'python setup.py sdist --format=zip',
        ]),
    )

    publish_task_step = create_publish_build_artifacts_task_step(
        path_to_publish='$(System.DefaultWorkingDirectory)/dist/',
        artifact_name='dist',
    )

    sdist_job = Job(
        name='sdist',
        display_name='Build sdist',
        steps=[
            use_python_version_step,
            bash_step,
            publish_task_step,
        ],
    )

    return sdist_job


def create_bdist_wheel_pure_job():
    use_python_version_step = create_use_python_version_task_step(
        version_spec='3.7',
        architecture='x64',
    )

    bash_step = BashStep(
        display_name='Build',
        script='\n'.join([
            'python -m pip install wheel',
            'python setup.py bdist_wheel',
        ]),
    )

    publish_task_step = create_publish_build_artifacts_task_step(
        path_to_publish='$(System.DefaultWorkingDirectory)/dist/',
        artifact_name='dist',
    )

    job = Job(
        name='bdist_wheel',
        display_name='Build pure wheel',
        steps=[
            use_python_version_step,
            bash_step,
            publish_task_step,
        ],
    )

    return job


def create_pipeline(name):
    stage = Stage(
        id_name='main',
        display_name='Main',
        jobs=pvector([
            create_sdist_job(),
            create_bdist_wheel_pure_job(),
        ]),
    )

    pipeline = Pipeline(
        name=name,
        stages=pvector([stage]),
    )

    return pipeline


def ordered_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())


def str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")


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
class UsePythonVersionTaskStep:
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


task_step_inputs_type_schema_map = pmap({
    UsePythonVersionTaskStep: UsePythonVersionTaskStepSchema,
    PublishBuildArtifactsTaskStep: PublishBuildArtifactsTaskStepSchema,
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
    )

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class BashStep:
    script = attr.ib()
    display_name = attr.ib()
    fail_on_stderr = attr.ib(default=True)
    environment = attr.ib(default=pmap(), converter=pmap)


step_type_schema_map = pmap({
    BashStep: BashStepSchema,
    TaskStep: TaskStepSchema,
})


def job_steps_serialization_schema_selector(base_object, parent_object):
    return step_type_schema_map[type(base_object)]()


class JobSchema(marshmallow.Schema):
    class Meta:
        ordered = True

    name = marshmallow.fields.String(data_key='job')
    display_name = marshmallow.fields.String(data_key='displayName')
    depends_on = marshmallow.fields.List(
        marshmallow.fields.Pluck('JobSchema', 'name'),
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
    name = attr.ib()
    display_name = attr.ib()
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
