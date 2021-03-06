from collections import OrderedDict
import inspect
import itertools

from decorator import decorator


class ValidationFailure(object):
    def __init__(self, func, args):
        self.func = func
        self.__dict__.update(args)

    def __repr__(self):
        return 'ValidationFailure(func={func}, args={args})'.format(
            func=self.func.__name__,
            args=dict(
                [(k, v) for (k, v) in list(self.__dict__.items()) if k != 'func']
            )
        )

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return False

    def __bool__(self):
        return False


def func_args_as_dict(func, args, kwargs):
    """
    Return given function's positional and key value arguments as an ordered
    dictionary.
    """
    arg_names = list(
        OrderedDict.fromkeys(
            itertools.chain(
                inspect.getargspec(func)[0],
                list(kwargs.keys())
            )
        )
    )
    return OrderedDict(
        list(zip(arg_names, args)) +
        list(kwargs.items())
    )


def validator(func, *args, **kwargs):
    """
    A decorator that makes given function validator.

    Whenever the given function is called and returns ``False`` value
    this decorator returns :class:`ValidationFailure` object.

    Example::

        >>> @validator
        ... def even(value):
        ...     return not (value % 2)

        >>> even(4)
        True

        >>> even(5)
        ValidationFailure(func=even, args={'value': 5})

    :param func: function to decorate
    :param args: positional function arguments
    :param kwargs: key value function arguments
    """
    def wrapper(func, *args, **kwargs):
        value = func(*args, **kwargs)
        if not value:
            return ValidationFailure(
                func, func_args_as_dict(func, args, kwargs)
            )
        return True
    return decorator(wrapper, func)
