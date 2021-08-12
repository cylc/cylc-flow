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
"""Utilities for use with asynchronous code."""

import asyncio
from functools import partial
from pathlib import Path
from typing import List, Union

import pyuv

from cylc.flow import LOG


class _AsyncPipe:
    """Implement the @pipe interface.

    Represents and implements an asynchronous pipe.

    Note:
        _AsyncPipe objects are created when you construct a pipe (using __or__)
        or attempt to iterate over an @pipe function.

    Attrs:
        func (callable):
            The function that this stage of the pipe represents.
        args (tuple):
            Args to call the function with.
        kwargs (dict):
            Kwargs to call the function with.
        filter_stop (bool):
            If True then items which fail a filter will not get yielded.
            If False then they will get yielded immediately.
        preserve_order (bool):
            If True then this will behave like a "conventional" pipe i.e.
            first-in first-out.

            If False then results will be yielded as soon as they arrive.

            Concurrency is the same for both options as results get cached
            in the first case.
        _left (_AsyncPipe):
            The previous item in the pipe or None.
        _right (_AsyncPipe):
            The next item in the pipe or None.

    """

    def __init__(
            self,
            func,
            args=None,
            kwargs=None,
            filter_stop=True,
            preserve_order=True
    ):
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.filter_stop = filter_stop
        self.preserve_order = preserve_order
        self._left = None
        self._right = None

    async def __aiter__(self):
        # aiter = async iter
        coros = self.__iter__()
        gen = next(coros)  # the generator we start the pipe with
        coros = list(coros)  # the coros to push data through
        running = []  # list of running asyncio tasks
        completed = asyncio.Queue()  # queue of processed items to yield
        try:
            # run the generator
            running.append(
                asyncio.create_task(
                    self._generate(gen, coros, running, completed)
                )
            )
            # push the data through the pipe and yield results
            if self.preserve_order:
                meth = self._ordered
            else:
                meth = self._unordered
            async for item in meth(running, completed):
                yield item
        finally:
            # tidy up after ourselves
            for task in running:
                task.cancel()

    async def _ordered(self, running, completed):
        """The classic first-in first-out pipe behaviour."""
        cache = {}  # cache of results {index: result}
        skip_cache = []  # list of results which have been filtered out
        yield_ind = 0  # the result index used when preserve_order == True

        while cache or running or not completed.empty():
            # cache any completed items
            if not completed.empty():
                ind, item = await completed.get()
                # add the item to the cache so we can yield in order
                cache[ind] = item
            # skip over any results which have been filtered out
            while yield_ind in skip_cache:
                skip_cache.remove(yield_ind)
                yield_ind += 1
            # yield any cached results
            while yield_ind in cache:
                yield cache.pop(yield_ind)
                yield_ind += 1
            # process completed tasks
            for task in running:
                if task.done():
                    running.remove(task)
                    ind = task.result()
                    if ind is not None:
                        # this item has been filtered out
                        skip_cache.append(ind)

            await asyncio.sleep(0)  # don't allow this loop to block

    async def _unordered(self, running, completed):
        """The optimal yield items as they are processed behaviour."""
        while running or not completed.empty():
            # return any completed items
            if not completed.empty():
                _, item = await completed.get()
                yield item
            # process completed tasks
            for task in running:
                if task.done():
                    running.remove(task)

            await asyncio.sleep(0)  # don't allow this loop to block

    async def _generate(self, gen, coros, running, completed):
        """Pull data out of the generator."""
        ind = 0
        async for item in gen.func(*gen.args, **gen.kwargs):
            running.append(
                asyncio.create_task(
                    self._chain((ind, item), coros, completed)
                )
            )
            ind += 1

    async def _chain(self, item, coros, completed):
        """Push data through the coroutine pipe."""
        ind, item = item
        for coro in coros:
            try:
                ret = await coro.func(item, *coro.args, **coro.kwargs)
            except Exception as exc:
                # if something goes wrong log the error and skip the item
                LOG.warning(exc)
                ret = False
            if ret is True:
                # filter passed -> continue
                continue
            elif ret is False and coro.filter_stop:
                # filter failed -> stop
                return ind
            elif ret is False:
                # filter failed but pipe configured to yield -> stop + yield
                break
            else:
                # returned an object -> continue
                item = ret
        await completed.put((ind, item))

    def __or__(self, other):
        if isinstance(other, _PipeFunction):
            other = _AsyncPipe(other.func)
        other._left = self
        self.fastforward()._right = other
        # because we return self we only need __or__ not __ror__
        return self

    def rewind(self):
        """Return the head of the pipe."""
        ptr = self
        while ptr._left:
            ptr = ptr._left
        return ptr

    def fastforward(self):
        """Return the tail of the pipe."""
        ptr = self
        while ptr._right:
            ptr = ptr._right
        return ptr

    def __iter__(self):
        ptr = self.rewind()
        while ptr._right:
            yield ptr
            ptr = ptr._right
        yield ptr

    def __repr__(self):
        return ' | '.join((str(ptr) for ptr in self))

    def __str__(self):
        args = ''
        if self.args:
            args = ', '.join(map(repr, self.args))
        if self.kwargs:
            if args:
                args += ', '
            args += ', '.join(f'{k}={repr(v)}' for k, v in self.kwargs.items())
        return f'{self.func.__name__}({args})'


class _PipeFunction:
    """Represent a function for use in an async pipe.

    This class is just for syntactic sugar, it enables us to assign arguments
    via the __call__ interface and enables us to add an interface for
    preprocessing args.

    """

    def __init__(self, func, preproc=None):
        self.func = func
        self.preproc = preproc

    def __call__(self, *args, filter_stop=True, **kwargs):
        # assign args/kwargs to a function in a pipe
        if self.preproc:
            args, kwargs = self.preproc(*args, **kwargs)
        return _AsyncPipe(
            self.func,
            args,
            kwargs,
            filter_stop
        )

    def __or__(self, other):
        this = _AsyncPipe(self.func)
        return this | other

    async def __aiter__(self):
        # this permits pipes with only one step
        async for item in _AsyncPipe(self.func):
            yield item

    def __str__(self):
        return _AsyncPipe(self.func).__str__()

    def __repr__(self):
        return _AsyncPipe(self.func).__repr__()

    @property
    def __doc__(self):
        return self.func.__doc__


def pipe(func=None, preproc=None):
    """An asynchronous pipe implementation in pure Python.

    Use this to decorate async functions in order to arrange them into
    asynchronous pipes. These pipes can process multiple items through multiple
    stages of the pipe simultaneously by doing what processing it can whilst
    waiting on IO to take place in the background.

    Async pipes perform maximum concurrency running as far ahead as they can.
    Don't use for cases where you only want the first N items as the pipe may
    process items outside of this window.

    Args:
        func (callable):
            The function this decorator decorates.
        preproc (callable):
            An optional function for pre-processing any args or kwargs
            provided to a function when the pipe is created.

            preproc(args: tuple, kwargs: dict) -> (args: tuple, kwargs: dict)

    Example:
        A generator to begin our pipe with:
        >>> @pipe
        ... async def arange():
        ...    for i in range(10):
        ...        yield i

        A filter which returns a boolean:
        >>> @pipe
        ... async def even(x):
        ...    # note the first argument (x) is the value passed down the pipe
        ...    return x % 2 == 0

        A transformation returns anything other than a boolean:
        >>> @pipe
        ... async def mult(x, y):
        ...    # note subsequent args must be provided when you build the pipe
        ...    return x * y

        Assemble them into a pipe
        >>> mypipe = arange | even | mult(2)
        >>> mypipe
        arange() | even() | mult(2)

        Write a function to "consume items":
        >>> async def consumer(pipe):
        ...     async for item in pipe:
        ...         print(item)

        Run pipe run:
        >>> import asyncio
        >>> asyncio.run(consumer(mypipe))
        0
        4
        8
        12
        16

        Real world examples will involve a bit of awaiting.

    Result Order
        By default this behaves like a "conventional" pipe where results
        are yielded in the order which the generator at the start of the pipe
        created them.

        By setting the ``preserve_order`` attribute on a pipe to ``False``
        you can make it yield items as soon as they are processed irrespective
        or order for more immediate results e.g::

            pipe = arange | even
            pipe.preserve_order = False

    Providing Arguments To Functions:
        The first function in the pipe will receive no data. All subsequent
        functions will receive the result of the previous function
        as its first argument (unless the previous function was a filter).

        To provide extra args/kwargs call the function when the pipe is
        being constructed e.g::

            pipe = my_function(arg1, kwarg1='x')

        If you want to transform args/kwargs before running the pipe use the
        ``preproc`` argument e.g::

            def my_preproc(*args, **kwargs):
                # do some transformation
                return args, kwargs

            @pipe(preproc=my_preproc)
            def my_pipe_step(x, *args, *kwargs): pass

    Filters And Transforms:
        If a function in the pipe returns a bool then it will be interpreted
        as a filter. If it returns any other object then it is a transform.

        Transforms mutate data as it passes through the pipe.

        Filters stop data from travelling further through the pipe.
        True means the filter passed, False means it failed.
        By default if a value fails a filter then it will not get yielded,
        you can change this using the filter_stop argument e.g::

            # if the filter fails yield the item straight away
            # if it passes run the item through function and yield the result
            pipe = generator | filter(filter_stop=False) | function

    """
    if preproc and not func:
        # @pipe(preproc=x)
        def _pipe(func):
            nonlocal preproc
            return _PipeFunction(func, preproc)
        return _pipe
    elif func:
        # @pipe
        return _PipeFunction(func)
    else:
        # @pipe()
        def _pipe(func):
            return _PipeFunction(func)
        return _pipe


def _scandir(future, path, request):
    """Callback helper for scandir()."""
    future.set_result([
        Path(path, directory.name)
        # request.result is None for empty dirs
        for directory in request.result or []
    ])


async def scandir(path: Union[Path, str]) -> List[Path]:
    """Asynchronous directory listing using pyuv."""
    ret: asyncio.Future[List[Path]] = asyncio.Future()

    loop = pyuv.Loop.default_loop()
    pyuv.fs.scandir(loop, str(path), callback=partial(_scandir, ret, path))
    loop.run()

    return await ret


async def asyncqgen(queue):
    """Turn a queue into an async generator."""
    while not queue.empty():
        yield await queue.get()
