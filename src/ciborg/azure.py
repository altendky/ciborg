import typing

import attr
import importlib_resources
import marshmallow
import yaml

from pyrsistent import pvector, pmap

import ciborg.data


def load_template():
    with importlib_resources.open_text(ciborg.data, 'azure.yml') as file:
        template = yaml.safe_load(file)

    return template


@attr.s(frozen=True)
class IncludeExcludePVectors:
    include = attr.ib(factory=pvector)
    exclude = attr.ib(factory=pvector)


@attr.s(frozen=True)
class Trigger:
    batch: bool = attr.ib(default=False)
    branches = attr.ib(factory=IncludeExcludePVectors)
    tags = attr.ib(factory=IncludeExcludePVectors)
    paths = attr.ib(factory=IncludeExcludePVectors)


@attr.s(frozen=True)
class BashStep:
    id_name: str
    display_name: str
    script = attr.ib(default=(), converter=pvector)
    fail_on_stderr: bool = attr.ib(default=True)
    environment = attr.ib(factory=pmap)


@attr.s(frozen=True)
class Job:
    name = attr.ib()
    display_name = attr.ib()
    depends_on = attr.ib(factory=pvector)
    condition = attr.ib(default='')
    continue_on_error = attr.ib(default=True)
    steps = attr.ib(factory=pvector)


@attr.s(frozen=True)
class Stage:
    id_name = attr.ib()
    display_name = attr.ib()
    depends_on = attr.ib(factory=pvector)
    condition = attr.ib(default='')
    jobs = attr.ib(factory=pvector)


class PipelineSchema(marshmallow.Schema):
    name = marshmallow.fields.Str()
    trigger = marshmallow.fields.Nested(StageSchema())


@attr.s(frozen=True)
class Pipeline:
    name = attr.ib()
    trigger = attr.ib(factory=Trigger)
    stages = attr.ib(factory=list)


print(Pipeline(name='ciborg'))
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
