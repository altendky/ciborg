import collections

import marshmallow.fields


# class OrderedDictField(marshmallow.fields.Mapping):
#     # https://github.com/marshmallow-code/marshmallow/pull/1098
#     mapping_type = collections.OrderedDict


# https://github.com/marshmallow-code/marshmallow/issues/483#issuecomment-229557880
class NestedDict(marshmallow.fields.Nested):
    def __init__(
            self,
            nested,
            key,
            *args,
            remove_key=False,
            only_these=None,
            **kwargs,
    ):
        super(NestedDict, self).__init__(nested, many=True, *args, **kwargs)
        self.key = key
        self.remove_key = remove_key
        self.only_these = only_these

    def _serialize(self, nested_obj, attr, obj):
        nested_list = super()._serialize(nested_obj, attr, obj)
        # nested_dict = {item[self.key]: item for item in nested_list}

        nested_dict = {}
        for item in nested_list:
            nested_dict[item[self.key]] = {
                key: value
                for key, value in item.items()
                if (
                    not (key == self.key and self.remove_key)
                    and (self.only_these is None or key in self.only_these)
                )
            }

        return nested_dict

    def _deserialize(self, value, attr, data):
        raw_list = [item for key, item in value.items()]
        nested_list = super()._deserialize(raw_list, attr, data)
        return nested_list


class NestedListAsKeyValue(marshmallow.fields.Nested):
    def __init__(
            self,
            nested,
            *args,
            key,
            value,
            **kwargs,
    ):
        super().__init__(nested, many=True, *args, **kwargs)
        self.key = key
        self.value = value

    def _serialize(self, nested_obj, attr, obj):
        nested_list = super()._serialize(nested_obj, attr, obj)

        return {
            entry[self.key]: entry[self.value]
            for entry in nested_list
        }


class ListAsListOfKeyDictOrString(marshmallow.fields.List):
    def __init__(
            self,
            nested,
            *args,
            key,
            only_these=None,
            **kwargs,
    ):
        super().__init__(nested, many=True, *args, **kwargs)
        self.key = key
        self.only_these = only_these

    def _serialize(self, nested_obj, attr, obj):
        serialized = super()._serialize(nested_obj, attr, obj)

        result = [
            {
                entry[self.key]: {
                    key: value
                    for key, value in entry.items()
                    if key != self.key
                    if self.only_these is None or key in self.only_these
                },
            }
            for entry in serialized
        ]

        result = [
            (
                entry
                if len(next(iter(entry.values()))) > 0
                else next(iter(entry.keys()))
            )
            for entry in result
        ]

        return result
