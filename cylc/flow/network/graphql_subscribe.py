# MIT License
#
# Copyright (c) GraphQL Contributors (GraphQL.js)
# Copyright (c) Syrus Akbary (GraphQL-core 2)
# Copyright (c) Christoph Zwerschke (GraphQL-core 3)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# ----------------------------------------------------------------------------
#
# The code in this file originates from graphql-core
# https://github.com/graphql-python/graphql-core/blob/v3.2.6/src/graphql/execution/subscribe.py
#
# It was modified to include `execution_context_class` and `middleware` in
# the execution of GraphQL subscriptions.
# This should not be necessary with some unspecified future releases as
# the head of graphql-core has these included.
#
# BACK COMPAT: graphql_subscribe.py
# FROM: graphql-core 3.2
# TO: graphql-core 3.3
# URL: https://github.com/cylc/cylc-flow/issues/6688


from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterable,
    AsyncIterator,
    Dict,
    Optional,
    Type,
    Union,
)

from graphql.error import GraphQLError, located_error
from graphql.execution.collect_fields import collect_fields
from graphql.execution.execute import (
    assert_valid_execution_arguments,
    execute,
    get_field_def,
    ExecutionContext,
    ExecutionResult,
    Middleware,
)
from graphql.execution.values import get_argument_values
from graphql.pyutils import Path, inspect
from graphql.execution.map_async_iterator import MapAsyncIterator


if TYPE_CHECKING:
    from graphql.language import DocumentNode
    from graphql.type import GraphQLFieldResolver, GraphQLSchema


__all__ = ["subscribe", "create_source_event_stream"]


async def subscribe(
    schema: 'GraphQLSchema',
    document: 'DocumentNode',
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: 'Optional[GraphQLFieldResolver]' = None,
    subscribe_field_resolver: 'Optional[GraphQLFieldResolver]' = None,
    middleware: Optional[Middleware] = None,
    execution_context_class: Optional[Type["ExecutionContext"]] = None,
    subscribe_resolver_map: 'Optional[Dict[str, GraphQLFieldResolver]]' = None,
) -> Union[AsyncIterator[ExecutionResult], ExecutionResult]:
    """Create a GraphQL subscription.

    Implements the "Subscribe" algorithm described in the GraphQL spec.

    Returns a coroutine object which yields either an AsyncIterator
    (if successful) or an ExecutionResult (client error). The coroutine will
    raise an exception if a server error occurs.

    If the client-provided arguments to this function do not result in a
    compliant subscription, a GraphQL Response (ExecutionResult) with
    descriptive errors and no data will be returned.

    If the source stream could not be created due to faulty subscription
    resolver logic or underlying systems, the coroutine object will yield a
    single ExecutionResult containing ``errors`` and no ``data``.

    If the operation succeeded, the coroutine will yield an AsyncIterator,
    which yields a stream of ExecutionResults representing the response stream.
    """
    result_or_stream = await create_source_event_stream(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        subscribe_field_resolver,
        middleware,
        execution_context_class,
        subscribe_resolver_map
    )
    if isinstance(result_or_stream, ExecutionResult):
        return result_or_stream

    async def map_source_to_response(payload: Any) -> ExecutionResult:
        """Map source to response.

        For each payload yielded from a subscription, map it over the normal
        GraphQL :func:`~graphql.execute` function, with ``payload`` as the
        ``root_value``. This implements the "MapSourceToResponseEvent"
        algorithm described in the GraphQL specification. The
        :func:`~graphql.execute` function provides the
        "ExecuteSubscriptionEvent" algorithm, as it is nearly identical to the
        "ExecuteQuery" algorithm, for which :func:`~graphql.execute` is also
        used.
        """
        result = execute(
            schema,
            document,
            payload,
            context_value,
            variable_values,
            operation_name,
            field_resolver,
            middleware=middleware,
            execution_context_class=execution_context_class,
        )
        return await result if isawaitable(result) else result

    # Map every source value to a ExecutionResult value as described above.
    return MapAsyncIterator(result_or_stream, map_source_to_response)


async def create_source_event_stream(
    schema: 'GraphQLSchema',
    document: 'DocumentNode',
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    subscribe_field_resolver: 'Optional[GraphQLFieldResolver]' = None,
    middleware: Optional[Middleware] = None,
    execution_context_class: Optional[Type["ExecutionContext"]] = None,
    subscribe_resolver_map: 'Optional[Dict[str, GraphQLFieldResolver]]' = None,
) -> Union[AsyncIterable[Any], ExecutionResult]:
    """Create source event stream

    Implements the "CreateSourceEventStream" algorithm described in the GraphQL
    specification, resolving the subscription source event stream.

    Returns a coroutine that yields an AsyncIterable.

    If the client-provided arguments to this function do not result in a
    compliant subscription, a GraphQL Response (ExecutionResult) with
    descriptive errors and no data will be returned.

    If the source stream could not be created due to faulty subscription
    resolver logic or underlying systems, the coroutine object will yield a
    single ExecutionResult containing ``errors`` and no ``data``.

    A source event stream represents a sequence of events, each of which
    triggers a GraphQL execution for that event.

    This may be useful when hosting the stateful subscription service in a
    different process or machine than the stateless GraphQL execution engine,
    or otherwise separating these two steps. For more on this, see the
    "Supporting Subscriptions at Scale" information in the GraphQL spec.
    """
    # If arguments are missing or incorrectly typed, this is an internal
    # developer mistake which should throw an early error.
    assert_valid_execution_arguments(schema, document, variable_values)

    if execution_context_class is None:
        execution_context_class = ExecutionContext

    # If a valid context cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    context = execution_context_class.build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        subscribe_field_resolver=subscribe_field_resolver,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(data=None, errors=context)

    try:
        event_stream = await execute_subscription(
            context,
            subscribe_resolver_map
        )

        # Assert field returned an event stream, otherwise yield an error.
        if not isinstance(event_stream, AsyncIterable):
            raise TypeError(
                "Subscription field must return AsyncIterable."
                f" Received: {inspect(event_stream)}."
            )
        return event_stream

    except GraphQLError as error:
        # Report it as an ExecutionResult, containing only errors and no data.
        return ExecutionResult(data=None, errors=[error])


async def execute_subscription(
    context: ExecutionContext,
    subscribe_resolver_map: 'Optional[Dict[str, GraphQLFieldResolver]]' = None,
) -> AsyncIterable[Any]:
    schema = context.schema

    root_type = schema.subscription_type
    if root_type is None:
        raise GraphQLError(
            "Schema is not configured to execute subscription operation.",
            context.operation,
        )

    root_fields = collect_fields(
        schema,
        context.fragments,
        context.variable_values,
        root_type,
        context.operation.selection_set,
    )
    response_name, field_nodes = next(iter(root_fields.items()))
    field_def = get_field_def(schema, root_type, field_nodes[0])

    if not field_def:
        field_name = field_nodes[0].name.value
        raise GraphQLError(
            f"The subscription field '{field_name}' is not defined.",
            field_nodes
        )

    path = Path(None, response_name, root_type.name)
    info = context.build_resolve_info(field_def, field_nodes, root_type, path)

    # Call the `subscribe()` resolver or the default resolver to produce an
    # AsyncIterable yielding raw payloads.
    if subscribe_resolver_map is not None:
        resolve_fn = subscribe_resolver_map.get(
            info.field_name,
            field_def.subscribe or context.subscribe_field_resolver
        )
    else:
        resolve_fn = field_def.subscribe or context.subscribe_field_resolver

    # Implements the "ResolveFieldEventStream" algorithm from GraphQL
    # specification. It differs from "ResolveFieldValue" due to providing a
    # different `resolveFn`.

    try:
        # Build a dictionary of arguments from the field.arguments AST, using
        # the variables scope to fulfill any variable references.
        args = get_argument_values(
            field_def, field_nodes[0], context.variable_values)

        event_stream = resolve_fn(context.root_value, info, **args)
        if context.is_awaitable(event_stream):
            event_stream = await event_stream
        if isinstance(event_stream, Exception):
            raise event_stream

        return event_stream
    except Exception as error:
        raise located_error(error, field_nodes, path.as_list()) from error
