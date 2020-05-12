import asyncio
from functools import partial
from pathlib import Path

import pyuv


class Pipe:
    """An asynchronous pipe implementation in pure Python.

    Example:
        A generator to begin our pipe with:
        >>> @Pipe
        ... async def arange():
        ...    for i in range(10):
        ...        yield i

        A filter which returns a boolean:
        >>> @Pipe
        ... async def even(x):
        ...    return x % 2 == 0

        A transformation returns anything other than a boolean:
        >>> @Pipe
        ... async def mult(x, y):
        ...    return x * y

        Assemble them into a pipe
        >>> mypipe = arange | even | mult(2)
        >>> print(mypipe)
        arange()
        >>> repr(mypipe)
        'arange() | even() | mult(2)'

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

    """

    def __init__(self, func):
        self.func = func
        self.args = tuple()
        self.kwargs = {}
        self._left = None
        self._right = None

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self

    async def __aiter__(self):
        coros = self.__iter__()
        gen = next(coros)
        coros = list(coros)
        async for item in gen.func(*gen.args, **gen.kwargs):
            for coro in coros:
                ret = await coro.func(item, *coro.args, **coro.kwargs)
                if ret is False:
                    break
                if ret is True:
                    pass
                else:
                    item = ret
            else:
                yield item

    def __or__(self, other):
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
