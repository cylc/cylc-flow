# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

GraphQL Middleware defined here also.

"""

from inspect import isclass
import logging
from typing import (
    Any, Awaitable, Callable, TypeVar, Tuple, Dict, Union, cast
)

from graphene.utils.str_converters import to_snake_case
from graphql import (
    ExecutionContext,
    TypeInfo,
    TypeInfoVisitor,
    Visitor,
    visit,
    get_argument_values,
    get_named_type,
    introspection_types,
)
from graphql.pyutils import AwaitableOrValue, is_awaitable

from cylc.flow.network.schema import NODE_MAP


logger = logging.getLogger(__name__)

STRIP_ARG = 'strip_null'
NULL_VALUE = None
EMPTY_VALUES: Tuple[list, dict] = ([], {})
STRIP_OPS = {'query', 'subscription'}
INTROSPECTS = {
    k.lower()
    for k in introspection_types
}

U = TypeVar("U")


def grow_tree(tree, path, leaves=None):
    """Additively grows tree with leaves at terminal of new branch.

    Given existing dictionary, it follows the new path from root through
    existing trunk and without clobbering existing leaves when encountered.

    Args:
        tree (dict): Existing or new dictionary/tree.
        path (list): List of keys from root to branch end.
        leaves (dict, optional):
            Dictionary of information to put at path end.

    Returns:
        None
    """
    tree_loc = [tree, {}]
    for loc, key in enumerate(path):
        if key in tree_loc[loc % 2]:  # noqa: SIM401
            tree_loc[(loc + 1) % 2] = tree_loc[loc % 2][key]
        else:
            tree_loc[loc % 2][key] = tree_loc[(loc + 1) % 2]
        tree_loc[loc % 2] = {}
    if leaves:
        tree_loc[len(path) % 2].update({'leaves': leaves})


def instantiate_middleware(middlewares):
    """Take iterable of middlewares and instantiate.

    Middleware instantiated here will not be shared amongst
    subscriptions/queries.

    """
    for middleware in middlewares:
        if isclass(middleware):
            yield middleware()
            continue
        yield middleware


async def async_callback(
    callback: Callable[[U], AwaitableOrValue[U]],
    result: AwaitableOrValue[U],
) -> U:
    """Await result and apply callback."""
    result = callback(await cast('Awaitable[Any]', result))
    return await result if is_awaitable(result) else result  # type: ignore


def async_next(
    callback: Callable[[U], AwaitableOrValue[U]],
    result: AwaitableOrValue[U],
) -> AwaitableOrValue[U]:
    """Reduce the given potentially awaitable values using a callback function.

    If the callback does not return an awaitable, then this function will also
    not return an awaitable.
    """
    if is_awaitable(result):
        return async_callback(callback, result)
    else:
        return callback(cast('U', result))


def null_setter(result):
    """Set type to null if result is empty/null-like."""
    # Only set empty parents to null.
    try:
        if result in EMPTY_VALUES:
            return NULL_VALUE
    except TypeError:
        # If field is a repeated composite field convert to list.
        if not result:
            return NULL_VALUE
    return result


# Is possible to not use middleware and do all the filtering here.
# However, middleware allows for argument of the request doc to set.
def strip_null(data):
    """Recursively strip data structure of nulls."""
    if isinstance(data, dict):
        return {
            key: strip_null(val)
            for key, val in data.items()
            if val is not NULL_VALUE
        }
    if isinstance(data, list):
        return [
            strip_null(val)
            for val in data
            if val is not NULL_VALUE
        ]
    return data


class CylcVisitor(Visitor):
    """Traverse graphql document/query to find an argument in a given state.

    Find whether an argument is set to a specific value anywhere in the
    document (i.e. 'strip_null' set to 'True'), and stop on the first
    occurrence.
    """
    def __init__(self, type_info, variable_values, doc_arg) -> None:
        super().__init__()
        self.type_info = type_info
        self.variable_values = variable_values
        self.doc_arg = doc_arg
        self.arg_flag = False

    def enter(self, node, key, parent, path, ancestors):
        if hasattr(node, 'arguments'):
            field_def = self.type_info.get_field_def()
            arg_vals = get_argument_values(
                field_def,
                node,
                self.variable_values
            )
            if arg_vals.get(self.doc_arg['arg']) == self.doc_arg['val']:
                self.arg_flag = True
                return self.BREAK
        return self.IDLE

    def leave(self, node, key, parent, path, ancestors):
        return self.IDLE


class CylcExecutionContext(ExecutionContext):

    def execute_operation(
        self, operation, root_value
    ) -> AwaitableOrValue[Union[Dict[str, Any], Any, None]]:
        """Execute the GraphQL document, and apply requested stipping.

        Search request document to determine if 'stripNull: true' is set
        as and argument. It can not be done in the middleware, as they
        can have awaitables and is prior to validation.
        """
        result = super().execute_operation(operation, root_value)

        # Traverse the document stop if found
        type_info = TypeInfo(self.schema)
        cylc_visitor = CylcVisitor(
            type_info,
            self.variable_values,
            {
                'arg': 'strip_null',
                'val': True,
            }
        )
        visit(
            self.operation,
            TypeInfoVisitor(
                type_info,
                cylc_visitor
            ),
            None
        )
        if not cylc_visitor.arg_flag:
            for fragment in self.fragments.values():
                visit(
                    fragment,
                    TypeInfoVisitor(
                        type_info,
                        cylc_visitor
                    ),
                    None
                )
        if cylc_visitor.arg_flag:
            return async_next(strip_null, result)  # type: ignore
        return result


# -- Middleware --

class IgnoreFieldMiddleware:
    """Set to null/None type undesired field values for stripping."""

    def __init__(self):
        self.args_tree = {}
        self.tree_paths = set()
        self.field_sets = {}

    def resolve(self, next_, root, info, **args):
        """Middleware resolver; handles field according to operation."""
        # GraphiQL introspection is 'query' but not async
        if INTROSPECTS.intersection({f'{p}' for p in info.path.as_list()}):
            return next_(root, info, **args)

        if info.operation.operation.value in STRIP_OPS:
            path_list = info.path.as_list()
            path_string = f'{path_list}'
            # Needed for child fields that resolve without args.
            # Store arguments of parents as leaves of schema tree from path
            # to respective field.
            # no need to regrow the tree on every subscription push/delta
            if args and path_string not in self.tree_paths:
                grow_tree(self.args_tree, path_list, args)
                self.tree_paths.add(path_string)
            if STRIP_ARG not in args:
                branch = self.args_tree
                for section in path_list:
                    if section not in branch:
                        break
                    branch = branch[section]
                    # Only set if present on branch section
                    if 'leaves' in branch and STRIP_ARG in branch['leaves']:
                        args[STRIP_ARG] = branch['leaves'][STRIP_ARG]

            # Now flag empty fields as null for stripping
            if args.get(STRIP_ARG, False):
                field_name = to_snake_case(info.field_name)

                # Clear field set so recreated via first child field,
                # as path may be a parent.
                # Done here as parent may be in NODE_MAP
                if path_string in self.field_sets:
                    del self.field_sets[path_string]

                # Avoid using the protobuf default if field isn't set.
                if (
                    hasattr(root, 'ListFields')
                    and hasattr(root, field_name)
                    and get_named_type(info.return_type).name not in NODE_MAP
                ):

                    # Gather fields set in root
                    parent_path_string = f'{path_list[:-1:]}'
                    stamp = getattr(root, 'stamp', '')
                    if (
                        parent_path_string not in self.field_sets
                        or self.field_sets[
                            parent_path_string]['stamp'] != stamp
                    ):
                        self.field_sets[parent_path_string] = {
                            'stamp': stamp,
                            'fields': {
                                field.name
                                for field, _ in root.ListFields()
                            }
                        }

                    if (
                        parent_path_string in self.field_sets
                        and field_name not in self.field_sets[
                            parent_path_string]['fields']
                    ):
                        return None
                # Do not resolve subfields of an empty type
                # by setting as null in parent/root.
                elif isinstance(root, dict) and field_name in root:
                    field_value = root[field_name]
                    if (
                        field_value in EMPTY_VALUES
                        or (
                            hasattr(field_value, 'ListFields')
                            and not field_value.ListFields()
                        )
                    ):
                        return None
                return async_next(null_setter, next_(root, info, **args))

        return next_(root, info, **args)
