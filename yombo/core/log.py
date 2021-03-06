# This file was created by Yombo for use with Yombo Python gateway automation
# software.  Details can be found at https://yombo.net
"""

.. note::

  For more information see: `Log Core @ Module Development <https://docs.yombo.net/Core/Log>`_


Handles logging functions.

.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>

:copyright: Copyright 2012-2015 by Yombo.
:license: LICENSE for details.
:view-source: `View Source Code <https://docs.yombo.net/gateway/html/current/_modules/yombo/core/module.html>`_
"""
# Import python libraries
import configparser
from zope.interface import provider
import io
import os
import gzip

# Import twisted libraries
from twisted.logger import globalLogPublisher, FilteringLogObserver, InvalidLogLevelError, \
    Logger, LogLevel, LogLevelFilterPredicate, ILogObserver, formatEvent, formatTime, \
    textFileLogObserver, jsonFileLogObserver
from twisted.internet.task import LoopingCall
from twisted.internet import reactor

def static_var(varname, value):
    """
    Sets a static variable within a function. This is an easy way to set a default.

    **Usage**:

    .. code-block:: python

        from yombo.utils.decorators import static_var

        @static_var("my_variable", 0)
        def some_function(x):
            some_function.my_variable += 1
            print "I've been called %s times." % some_function.my_variable

    :param varname: variable name to create
    :param value: initial value to set.
    :return:
    """
    def decorate(func):
        setattr(func, varname, value)
        return func
    return decorate

loggers = {}
open_files = {}
observers = {}
configCache = {}
logFirstRun = True

logLevels = (
    "debug",
    "info",
    "warn",
    "error",
)

bcolor = {'debug':'\033[94m',
        'info':'\033[92m',
        'warn':'\033[93m',
        'error':'\033[91m',
        'default':'\033[33m',
        }

@provider(ILogObserver)
def simpleObserver(event):
#    event['log_system'] = "asdf"
    print(event)
    print((formatEvent(event)))

logFormat = lambda event: "{0} [{1}]: {2}".format(formatTime(event["log_time"]), event["log_level"].name.upper(),
                                                   formatEvent(event))

@provider(ILogObserver)
def consoleLogObserver(event):
    print("[{0}{1}\033[39m-{2}]: {3}".format(bcolor[event["log_level"].name.lower()], event["log_level"].name.upper(), event["log_namespace"], formatEvent(event)))

@static_var('rotate_loop', None)
def get_logger(logname='yombolog', **kwargs):
    """
    Returns a logger object that allows logging of error messages.

    **Usage**:

    .. code-block:: python

       from yombo.core.log import get_logger

       logger = get_logger("module.ModuleName")
       logger.debug("Some status line, debug level items.")
       logger.info("ModuleName has finished starting is ready.")
       logger.warn("A warning!!")
       logger.error("Something really bad happened! I should quit.")

    :param logname: Name of the module or library.
    :type logname: string
    :return: logger object
    """
    global loggers
    global observers
    global configCache
    global open_files

    # A simple cache or existing loggers...
    if logname in loggers:
        return loggers[logname]


    loglevel = None
    source = kwargs.get('source', logname)
    json = kwargs.get('source', False)

    # Determine the logging level
    if len(loggers) == 0:
        config_parser = configparser.SafeConfigParser()
        try:
            fp = open('yombo.ini')
            config_parser.readfp(fp)
            ini = config_parser
            for option in ini.options('logging'):
                value =  ini.get('logging', option)
                configCache[option] = value
            fp.close()
        except IOError:
            pass
        except configparser.NoSectionError:
            pass

    logFilter = LogLevelFilterPredicate()
    try:
        if logname in configCache:
          iniLogLevel = configCache[logname].lower()
          logFilter.setLogLevelForNamespace(logname, LogLevel.levelWithName(iniLogLevel))
#        else:
#          iniLogLevel = 'info'
#          iniLogLevel = False
#        print "iniLogLevel: %s, logname: %s" % (iniLogLevel, logname)
        invalidLogLevel = False
    except InvalidLogLevelError:
        logFilter.setLogLevelForNamespace(logname, LogLevel.info)
        invalidLogLevel = True

    # Yell at the user if they specified an invalid log level
    if invalidLogLevel:
        loggers[logname].warn("yombo.ini file contained invalid log level {invalidLevel}, level has been set to INFO instead.",
                           invalidLevel=configCache[logname].lower())

    # Set up logging
    consoleFilterObserver = FilteringLogObserver(consoleLogObserver, (logFilter,))

    logger = Logger(namespace=logname, source=source, observer=consoleFilterObserver)
    loggers[logname] = logger

    # global logFirstRun
    # if logFirstRun is True:
    #   logFirstRun = False
      # This doesn't appear to be working yet...
    #   observers['json'] = jsonFileLogObserver(io.open("usr/log/yombo.json", "a"))
    #   globalLogPublisher.addObserver(observers['json'])
    #   observers['text'] = textFileLogObserver(io.open("usr/log/yombo.text", "a"))
    #   globalLogPublisher.addObserver(observers['text'])
    #
    #   # globalLogPublisher.addObserver(jsonFileLogObserver(io.open("usr/log/yombo.json", "a")))
    #   # globalLogPublisher.addObserver(textFileLogObserver(io.open("usr/log/yombo.text", "a")))
    #
    #
    # if get_logger.rotate_loop is None:
    #     get_logger.rotate_loop = LoopingCall(rotate_logs)
    #     get_logger.rotate_loop.start(5, False)  # about every 10 minutes
    #     # get_logger.rotate_loop.start(615, False)  # about every 10 minutes

    return loggers[logname]

def rotate_logs():
    reactor.callInThread(do_rotate_logs, 'usr/log/yombo.json', 'json')
    reactor.callInThread(do_rotate_logs, 'usr/log/yombo.text', 'text')

def do_rotate_logs(basefile, type):
    global observers

    if os.path.exists(basefile):
        if os.path.getsize(basefile) > 1000:
            for c in range(19, 0, -1):
                filename_cur = "%s.1" % basefile
                if c == 1 and os.path.exists(filename_cur):
                    with open(filename_cur) as src, gzip.open('%s.gz' % filename_cur, 'wb') as dst:
                        dst.writelines(src)
                    os.remove(filename_cur)

                filename_cur = "%s.%s.gz" % (basefile, c)
                filename_next = "%s.%s.gz" % (basefile, c+1)
                if os.path.exists(filename_cur):
                    os.rename(filename_cur, filename_next)
            os.rename(basefile, "%s.1" % basefile)


        if type == 'json':
            globalLogPublisher.removeObserver(observers['json'])
            observers['json'] = jsonFileLogObserver(io.open("usr/log/yombo.json", "a"))
            globalLogPublisher.addObserver(observers['json'])


            globalLogPublisher.addObserver(jsonFileLogObserver(io.open(basefile, "a")))
        elif type == 'text':
            observers['text'] = textFileLogObserver(io.open("usr/log/yombo.text", "a"))
            globalLogPublisher.addObserver(observers['text'])


            globalLogPublisher.removeObserver(textFileLogObserver())
            globalLogPublisher.addObserver(textFileLogObserver(io.open(basefile, "a")))


def reset_log_levels():
    """
    Used to reset the logs to their proper levels after
    configurations are downloaded. Also called when
    recieved a config update.
    """
    #TODO: Test this!
    from yombo.core.helpers import getConfigValue
    global loggers
    global logLevels

    for key, aLog in loggers:
        newLevel = getConfigValue('logging', key, 10)
        aLog.setLevel(newlevel)


