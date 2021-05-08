#!/usr/bin/env python

"""
This is an API I proposed to upstream recently but which wasn't judged about
yet. However, I want to use it here because handling of concurrent exceptions with
plain trio feels pretty weird and unergonomic.

This will become obsolete once trio's ExceptionGroup is implemented with a new API.
"""

import sys

import trio


# When switching from MultiError to ExceptionGroup which don't collapse even when
# just a single exception is contained, all these functions could become methods
# of ExceptionGroup (without the _exc suffix of course) and the support for plain
# exceptions could then be dropped.


def find_exc(exc, predicate):
    """Return the first exception that fulfills some predicate or ``None``.

    :param exc: see :func:`findall_excs`
    :type  exc: BaseException
    :param predicate: see :func:`findall_excs`
    :type  predicate: callable, type, (type)
    :rtype: BaseException, None
    """
    for _exc in findall_excs(exc, predicate):
        return _exc


def findall_excs(exc, predicate):
    """Yield only exceptions that fulfill some predicate.

    :param exc:
        Exception to check the predicate for.
        If this is a :exc:`trio.MultiError`, all contained exceptions are checked
        and those that fulfill the predicate are yielded. If It's none, nothing
        is yielded.
    :type  exc: BaseException, None
    :param predicate:
        Callable that takes a :class:`BaseException` object and returns whether it
        fulfills some criteria (``True``) or not (``False``).
        If a type or tuple of types is given instead of a callable, :func:`isinstance`
        is automatically used as the predicate function.
    :type  predicate: callable, type, (type)
    :return: iterator over :exc:`BaseException` objects
    """
    if exc is None:
        return

    if isinstance(predicate, (type, tuple)):
        exc_type = predicate
        predicate = lambda _exc: isinstance(_exc, exc_type)

    if isinstance(exc, trio.MultiError):
        yield from filter(predicate, exc.exceptions)
    elif predicate(exc):
        yield exc


# Functions for modifying MultiError.


def add_exc(exc, to_add):
    if exc is None:
        existing = ()
    elif isinstance(exc, trio.MultiError):
        existing = e.exceptions
    else:
        existing = (exc,)
    return trio.MultiError([*existing, to_add])


def maybe_reraise(exc, from_exc=0):
    if exc is None:
        return
    if from_exc == 0:
        from_exc = sys.exc_info()[1]
    raise exc from from_exc


def remove_exc(exc, to_remove):
    if exc is None:
        existing = ()
    elif isinstance(exc, trio.MultiError):
        existing = exc.exceptions
    else:
        existing = (exc,)
    if to_remove not in existing:
        raise ValueError("{!r} not contained in {!r}".format(to_remove, exc))
    new = [e for e in existing if e is not to_remove]
    if new:
        return trio.MultiError(new)


def monkey_patch():
    """Make functions available as static methods on :class:`trio.MultiError`."""
    trio.MultiError.find = staticmethod(find_exc)
    trio.MultiError.findall = staticmethod(findall_excs)
    trio.MultiError.add = staticmethod(add_exc)
    trio.MultiError.maybe_reraise = staticmethod(maybe_reraise)
    trio.MultiError.remove = staticmethod(remove_exc)


# Just an example of how to use this
if __name__ == "__main__":

    async def main():
        async def task():
            raise TypeError("This propagates out")

        with trio.CancelScope() as cscope:
            try:
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(task)
                    # Cancel the whole nursery from outside
                    cscope.cancel()
                    # This raises the ValueError, a TypeError from task() and a
                    # trio.Cancelled from the nursery's main task)
                    raise ValueError("This will be handled and swallowed")
            except BaseException as exc:
                for _exc in trio.MultiError.findall(exc, ValueError):
                    print("handling", repr(_exc))
                    exc = trio.MultiError.remove(exc, _exc)
                if trio.MultiError.find(exc, trio.Cancelled):
                    print("delaying cancellation")
                    with trio.CancelScope(shield=True):
                        await trio.sleep(1)
                print("reraising", repr(exc))
                trio.MultiError.maybe_reraise(exc)

    monkey_patch()
    trio.run(main)
