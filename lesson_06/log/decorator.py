import sys
import logging
import inspect


def log(func):
    LOGGER = logging.getLogger('server') if 'server.py' in sys.argv[0] else logging.getLogger('client')

    def decor(*args, **kwargs):
        result = func(*args, **kwargs)
        s = '\\'
        LOGGER.debug(f'"{inspect.getmodule(inspect.stack()[1][0]).__file__.rpartition(s)[-1]}/'
                     f'{inspect.getouterframes(inspect.currentframe())[1][3]}" '
                     f'Вызывает: "{func.__module__}/{func.__name__}("{args}" {kwargs})"; '
                     f'Результат: "{str(result)}"')
        return result

    decor.log = LOGGER
    return decor
