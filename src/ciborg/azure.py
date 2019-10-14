import typing

import attr
import importlib_resources
import marshmallow
import yaml

from pyrsistent import pvector, pmap, pset

import ciborg.data


def load_template():
    with importlib_resources.open_text(ciborg.data, 'azure.yml') as file:
        template = yaml.safe_load(file)

    return template


def create_sdist_job():
    bash_step = BashStep(
        display_name='Build',
        script=[
            'python setup.py sdist --format=zip',
        ],
    )

    publish_task_step = TaskStep(
        task='PublishBuildArtifacts@1',
        display_name='Publish',
        id_name='publish',
        inputs={
            'pathToPublish': '$(System.DefaultWorkingDirectory)/dist/',
            'artifactName': 'dist',
        },
    )

    sdist_job = Job(
        name='sdist',
        display_name='Build sdist',
        steps=[
            bash_step,
            publish_task_step,
        ],
    )

    return sdist_job


def create_bdist_pure_job():
    pass


def create_pipeline(name):
    stage = Stage(
        id_name='main',
        display_name='Main',
        jobs=pvector([
            create_sdist_job(),
        ]),
    )

    pipeline = Pipeline(
        name=name,
        stages=pvector([stage]),
    )

    return pipeline


def dump_pipeline(pipeline):
    basic_types = PipelineSchema().dump(pipeline)
    dumped = yaml.dump(basic_types)

    return dumped


def remove_skip_values(the_dict, skip_values=pset({None, pvector(), pmap()})):
    return {
        key: value
        for key, value in the_dict.items()
        if value not in tuple(skip_values)
    }


@marshmallow.decorators.post_dump
def post_dump_remove_skip_values(self, data, many):
    return remove_skip_values(data)


class IncludeExcludePVectorsSchema(marshmallow.Schema):
    include = marshmallow.fields.List(marshmallow.fields.String())
    exclude = marshmallow.fields.List(marshmallow.fields.String())

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class IncludeExcludePVectors:
    include = attr.ib(factory=pvector)
    exclude = attr.ib(factory=pvector)


class TriggerSchema(marshmallow.Schema):
    batch = marshmallow.fields.Boolean()
    branches = marshmallow.fields.Nested(IncludeExcludePVectorsSchema())
    tags = marshmallow.fields.Nested(IncludeExcludePVectorsSchema())
    paths = marshmallow.fields.Nested(IncludeExcludePVectorsSchema())

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class Trigger:
    batch: bool = attr.ib(default=False)
    branches = attr.ib(factory=IncludeExcludePVectors)
    tags = attr.ib(factory=IncludeExcludePVectors)
    paths = attr.ib(factory=IncludeExcludePVectors)


class TaskStepSchema(marshmallow.Schema):
    task = marshmallow.fields.String()
    id_name = marshmallow.fields.String(data_key='name')
    display_name = marshmallow.fields.String(data_key='display_name')
    inputs = marshmallow.fields.Dict(
        keys=marshmallow.fields.String(),
        values=marshmallow.fields.String(),
    )
    condition = marshmallow.fields.String(allow_none=True)

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class TaskStep:
    task = attr.ib()
    id_name = attr.ib()
    display_name = attr.ib()
    inputs = attr.ib(converter=pmap)
    condition = attr.ib(default=None)


class BashStepSchema(marshmallow.Schema):
    display_name = marshmallow.fields.String()
    script = marshmallow.fields.List(
        marshmallow.fields.String(),
        data_key='bash',
    )
    fail_on_stderr = marshmallow.fields.Boolean(data_key='failOnStderr')
    environment = marshmallow.fields.Dict(
        keys=marshmallow.fields.String(),
        values=marshmallow.fields.String(),
    )

    post_dump = post_dump_remove_skip_values


@attr.s(frozen=True)
class BashStep:
    display_name: str = attr.ib()
    script = attr.ib(default=(), converter=pvector)
    fail_on_stderr: bool = attr.ib(default=True)
    environment = attr.ib(default=pmap(), converter=pmap)


class JobSchema(marshmallow.Schema):
    name = marshmallow.fields.String(data_key='job')
    display_name = marshmallow.fields.String(data_key='displayName')
    depends_on = marshmallow.fields.List(
        marshmallow.fields.Pluck('JobSchema', 'name'),
    )
    condition = marshmallow.fields.String(allow_none=True)
    continue_on_error = marshmallow.fields.Boolean()
    steps = marshmallow.fields.List(
        marshmallow.fields.Nested(BashStepSchema()),
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
