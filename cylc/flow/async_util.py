import asyncio
from functools import partial
from pathlib import Path

import pyuv


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
        _left (_AsyncPipe):
            The previous item in the pipe or None.
        _right (_AsyncPipe):
            The next item in the pipe or None.

    """

    def __init__(self, func, args=None, kwargs=None, filter_stop=True):
        self.func = func
        self.args = args or tuple()
        self.kwargs = kwargs or {}
        self.filter_stop = filter_stop
        self._left = None
        self._right = None

    async def __aiter__(self):
        # aiter = async iter
        coros = self.__iter__()
        gen = next(coros)
        coros = list(coros)
        async for item in gen.func(*gen.args, **gen.kwargs):
            for coro in coros:
                ret = await coro.func(item, *coro.args, **coro.kwargs)
                if ret is True:
                    # filter passed -> continue
                    pass
                elif ret is False and coro.filter_stop:
                    # filter failed -> stop
                    break
                elif ret is False:
                    # filter failed but pipe configured to yield -> stop
                    yield item
                    break
                else:
                    # returned an object -> continue
                    item = ret
            else:
                yield item

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

    Args:
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

    Functions And Transforms:
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
        for directory in request.result
    ])


async def scandir(path):
    """Asynchronous directory listing using pyuv."""
    ret = asyncio.Future()

    loop = pyuv.Loop.default_loop()
    pyuv.fs.scandir(loop, str(path), callback=partial(_scandir, ret, path))
    loop.run()

    return await ret


async def asyncqgen(queue):
    """Turn a queue into an async generator."""
    while not queue.empty():
        yield await queue.get()
