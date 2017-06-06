# This file was created by Yombo for use with Yombo Python Gateway automation
# software.  Details can be found at https://yombo.net
"""
Responsible for importing, starting, and stopping all libraries and modules.

Starts libraries and modules (components) in the following phases.  These
phases are first completed for libraries.  After "start" phase has completed
then modules startup in the same method.

#. Import all components
#. Call "init" for all components

   * Get the component ready, but not do any actual work yet.
   * Components can now see a full list of components there were imported.
  
#. Call "load" for all components
#. Call "start" for all components

Stops components in the following phases. Modules first, then libraries.

#. Call "stop" for all components
#. Call "unload" for all components

.. warning::

  Module developers and users should not access any of these functions
  or variables.  This is listed here for completeness. Use a :ref:`Helpers`
  function to get what is needed.

.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>

:copyright: Copyright 2012-2016 by Yombo.
:license: LICENSE for details.
"""
# Import python libraries
import traceback
from re import search as ReSearch
from collections import OrderedDict
import asyncio
from concurrent.futures import ThreadPoolExecutor
# from signal import signal, SIGINT

# Import twisted libraries
from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue, Deferred
from twisted.internet import reactor
from twisted.web import client
import collections
from functools import reduce
client._HTTP11ClientFactory.noisy = False

# Import Yombo libraries
from yombo.core.exceptions import YomboCritical, YomboWarning, YomboHookStopProcessing
from yombo.utils.fuzzysearch import FuzzySearch
from yombo.core.library import YomboLibrary
from yombo.core.log import get_logger
import yombo.utils

logger = get_logger('library.loader')

HARD_LOAD = OrderedDict()
HARD_LOAD["Queue"] = {'operation_mode':'all'}
HARD_LOAD["Notifications"] = {'operation_mode':'all'}
HARD_LOAD["LocalDB"] = {'operation_mode':'all'}
HARD_LOAD["SQLDict"] = {'operation_mode':'all'}
HARD_LOAD["Atoms"] = {'operation_mode':'all'}
HARD_LOAD["States"] = {'operation_mode':'all'}
HARD_LOAD["Configuration"] = {'operation_mode':'all'}
HARD_LOAD["Statistics"] = {'operation_mode':'all'}
HARD_LOAD["Startup"] = {'operation_mode':'all'}
HARD_LOAD["AMQP"] = {'operation_mode':'run'}
HARD_LOAD["YomboAPI"] = {'operation_mode':'all'}
HARD_LOAD["GPG"] = {'operation_mode':'all'}
HARD_LOAD["Automation"] = {'operation_mode':'all'}
HARD_LOAD["CronTab"] = {'operation_mode':'all'}
HARD_LOAD["DownloadModules"] = {'operation_mode':'run'}
HARD_LOAD["Times"] = {'operation_mode':'all'}
HARD_LOAD["Commands"] = {'operation_mode':'all'}
HARD_LOAD["DeviceTypes"] = {'operation_mode':'all'}
HARD_LOAD["InputTypes"] = {'operation_mode':'all'}
HARD_LOAD["VoiceCmds"] = {'operation_mode':'all'}
HARD_LOAD["Variables"] = {'operation_mode':'all'}
HARD_LOAD["Devices"] = {'operation_mode':'all'}
HARD_LOAD["Modules"] = {'operation_mode':'all'}
HARD_LOAD["Localize"] = {'operation_mode':'all'}
HARD_LOAD["AMQPYombo"] = {'operation_mode':'run'}
HARD_LOAD["Nodes"] = {'operation_mode':'all'}
HARD_LOAD["MQTT"] = {'operation_mode':'run'}
HARD_LOAD["WebInterface"] = {'operation_mode':'all'}
HARD_LOAD["Tasks"] = {'operation_mode':'all'}
HARD_LOAD["SSLCerts"] = {'operation_mode':'all'}

HARD_UNLOAD = OrderedDict()
HARD_UNLOAD["SSLCerts"] = {'operation_mode':'all'}
HARD_UNLOAD["Tasks"] = {'operation_mode':'all'}
HARD_UNLOAD["Localize"] = {'operation_mode':'all'}
HARD_UNLOAD["Startup"] = {'operation_mode':'all'}
HARD_UNLOAD["YomboAPI"] = {'operation_mode':'all'}
HARD_UNLOAD["GPG"] = {'operation_mode':'all'}
HARD_UNLOAD["Automation"] = {'operation_mode':'all'}
HARD_UNLOAD["CronTab"] = {'operation_mode':'all'}
HARD_UNLOAD["Times"] = {'operation_mode':'all'}
HARD_UNLOAD["Commands"] = {'operation_mode':'all'}
HARD_UNLOAD["DeviceTypes"] = {'operation_mode':'all'}
HARD_UNLOAD["InputTypes"] = {'operation_mode':'all'}
HARD_UNLOAD["VoiceCmds"] = {'operation_mode':'all'}
HARD_UNLOAD["Devices"] = {'operation_mode':'all'}
HARD_UNLOAD["Nodes"] = {'operation_mode':'all'}
HARD_UNLOAD["Atoms"] = {'operation_mode':'all'}
HARD_UNLOAD["States"] = {'operation_mode':'all'}
HARD_UNLOAD["WebInterface"] = {'operation_mode':'all'}
HARD_UNLOAD["Devices"] = {'operation_mode':'all'}
HARD_UNLOAD["AMQPYombo"] = {'operation_mode':'run'}
HARD_UNLOAD["Configuration"] = {'operation_mode':'all'}
HARD_UNLOAD["Statistics"] = {'operation_mode':'all'}
HARD_UNLOAD["Modules"] = {'operation_mode':'all'}
HARD_UNLOAD["MQTT"] = {'operation_mode':'run'}
HARD_UNLOAD["SQLDict"] = {'operation_mode':'all'}
HARD_UNLOAD["AMQP"] = {'operation_mode':'run'}
HARD_UNLOAD["Modules"] = {'operation_mode':'all'}
HARD_LOAD["Variables"] = {'operation_mode':'all'}
# HARD_UNLOAD["DownloadModules"] = {'operation_mode':'run'}
HARD_UNLOAD["LocalDB"] = {'operation_mode':'all'}
HARD_UNLOAD["Queue"] = {'operation_mode':'all'}


class Loader(YomboLibrary, object):
    """
    Responsible for loading libraries, and then delegating loading modules to
    the modules library.

    Libraries are never reloaded, however, during a reconfiguration,
    modules are unloaded, and then reloaded after configurations are done
    being downloaded.
    """
    @property
    def operation_mode(self):
        return self._operation_mode

    @operation_mode.setter
    def operation_mode(self, val):
        self.loadedLibraries['atoms']['loader.operation_mode'] = val
        self._operation_mode = val

    def __getitem__(self, component_requested):
        """
        """
        logger.debug("looking for: {component_requested}", component_requested=component_requested)
        if component_requested in self.loadedComponents:
            logger.debug("found by loadedComponents! {component_requested}", component_requested=component_requested)
            return self.loadedComponents[component_requested]
        elif component_requested in self.loadedLibraries:
            logger.debug("found by loadedLibraries! {component_requested}", component_requested=component_requested)
            return self.loadedLibraries[component_requested]
        elif component_requested in self._moduleLibrary:
            logger.debug("found by self._moduleLibrary! {component_requested}", component_requested=self._moduleLibrary)
            return self._moduleLibrary[component_requested]
        else:
            raise YomboWarning("Loader could not find requested component: {%s}"
                               % component_requested, '101', '__getitem__', 'loader')

    def __init__(self, testing=False, loop=None):
        self.unittest = testing
        self._moduleLibrary = None
        YomboLibrary.__init__(self)

        self.loadedComponents = FuzzySearch({self._FullName.lower(): self}, .95)
        self.loadedLibraries = FuzzySearch({self._Name.lower(): self}, .95)
        self.libraryNames = {}
        self.__localModuleVars = {}
        self._moduleLibrary = None
        self._invoke_list_cache = {}  # Store a list of hooks that exist or not. A cache.
        self._operation_mode = None  # One of: firstrun, config, run
        self.sigint = False  # will be set to true if SIGINT is received
        self.hook_counts = OrderedDict()  # keep track of hook names, and how many times it's called.
        self.run_phase = None
        reactor.addSystemEventTrigger("before", "shutdown", self.shutdown)

    def shutdown(self):
        """
        This is called if SIGINT (ctrl-c) was caught. Very useful incase it was called during startup.
        :return:
        """
        self.sigint = True

    # def shutdown2(self, signum, frame):
    #     """
    #     This is called if SIGINT (ctrl-c) was caught. Very useful incase it was called during startup.
    #     :return:
    #     """
    #     print 'Signal handler called with signal %s' % signum
    #     print "WHAT!  I was called - signal"
    #     self.sigint = True
    #     reactor.stop()

    @inlineCallbacks
    def start(self):  #on startup, load libraried, then modules
        """
        This is effectively the main start function.

        This function is called when the gateway is to startup. In turn,
        this function will load all the components and modules of the gateway.
        """
        logger.info("Importing libraries, this can take a few moments.")
        self.run_phase = "libraries_import"

        # Get a reference to the asyncio event loop.
        yield yombo.utils.sleep(0.01)  # kick the asyncio event loop
        self.event_loop = asyncio.get_event_loop()

        yield self.import_libraries() # import and init all libraries

        # if self.sigint:
        #     return
        logger.debug("Calling load functions of libraries.")
        self.run_phase = "libraries_load"
        for name, config in HARD_LOAD.items():
            # print "sigint: %s" % self.sigint
            if self.sigint:
                return
            self._log_loader('debug', name, 'library', 'load', 'About to call _load_.')
            if self.check_operation_mode(config['operation_mode']):
                HARD_LOAD[name]['_load_'] = 'Starting'
                libraryName = name.lower()
                yield self.library_invoke(libraryName, "_load_", called_by=self)
                HARD_LOAD[name]['_load_'] = True
            else:
                HARD_LOAD[name]['_load_'] = False
            self._log_loader('debug', name, 'library', 'load', 'Finished call to _load_.')

        self._moduleLibrary = self.loadedLibraries['modules']
        self.run_phase = "libraries_start"

#        logger.debug("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1Calling start function of libraries.")
        for name, config in HARD_LOAD.items():
            if self.sigint:
                return
            self._log_loader('debug', name, 'library', 'start', 'About to call _start_.')
            if self.check_operation_mode(config['operation_mode']):
                libraryName =  name.lower()
                yield self.library_invoke(libraryName, "_start_", called_by=self)
                HARD_LOAD[name]['_start_'] = True
            else:
                HARD_LOAD[name]['_start_'] = False
            self._log_loader('debug', name, 'library', 'load', 'Finished call to _start_.')


        yield self._moduleLibrary.import_modules()

        for name, config in HARD_LOAD.items():
            if self.sigint:
                return
            self._log_loader('debug', name, 'library', 'started', 'About to call _started_.')
            if self.check_operation_mode(config['operation_mode']):
                libraryName =  name.lower()
                yield self.library_invoke(libraryName, "_started_", called_by=self)
                HARD_LOAD[name]['_started_'] = True
            else:
                HARD_LOAD[name]['_started_'] = False

        yield self._moduleLibrary.load_modules()
        self.loadedLibraries['notifications'].add({'title': 'System started',
            'message': 'System successfully started.', 'timeout': 300, 'source': 'Yombo Gateway System',
            'persist': False,
            'always_show': False,
        })

        for name, config in HARD_LOAD.items():
            if self.sigint:
                return
            self._log_loader('debug', name, 'library', 'started', 'About to call _modules_started_.')
            if self.check_operation_mode(config['operation_mode']):
                libraryName =  name.lower()
                yield self.library_invoke(libraryName, "_modules_started_", called_by=self)
                HARD_LOAD[name]['_started_'] = True
            else:
                HARD_LOAD[name]['_started_'] = False

        logger.info("Yombo Gateway started.")

    @inlineCallbacks
    def unload(self):
        """
        Called when the gateway should stop. This will gracefully stop the gateway.

        First, unload all modules, then unload all components.
        """
        self.sigint = True  # it's 99.999% true - usually only shutdown due to this.
        if self._moduleLibrary is not None:
            yield self._moduleLibrary.unload_modules()
        yield self.unload_libraries()
        # self.loop.close()

    def Times_i18n_atoms(self, **kwargs):
       return [
           {'loader.operation_mode': {
               'en': 'One of: firstrun, run, config',
               },
           },
       ]

    def check_component_status(self, name, function):
        if name in HARD_LOAD:
            if function in HARD_LOAD[name]:
                return HARD_LOAD[name][function]
        return None

    def _log_loader(self, level, label, type, method, msg=""):
        """
        A common log format for loading/unloading libraries and modules.

        :param level: Log level - debug, info, warn...
        :param label: Module label "x10", "messages"
        :param type: Type of item being loaded: library, module
        :param method: Method being called.
        :param msg: Optional message to include.
        :return:
        """
        logit = func = getattr(logger, level)
        logit("Loader: {label}({type})::{method} - {msg}", label=label, type=type, method=method, msg=msg)

    def import_libraries_failure(self, failure):
        logger.error("Got failure during import of library: {failure}", failure=failure)

    @inlineCallbacks
    def import_libraries(self):
        """
        Import then "init" all libraries. Call "loadLibraries" when done.
        """
        logger.debug("Importing server libraries.")
        # d = Deferred()
        # d.callback(1)
        for name, config in HARD_LOAD.items():
            if self.sigint:
                return
            HARD_LOAD[name]['__init__'] = 'Starting'
            pathName = "yombo.lib.%s" % name
            self.import_component(pathName, name, 'library')
            HARD_LOAD[name]['__init__'] = True

        logger.debug("Calling init functions of libraries.")
        self.run_phase = "libraries_init"
        for name, config in HARD_LOAD.items():
            if self.sigint:
                return
            if self.check_operation_mode(config['operation_mode']) is False:
                HARD_LOAD[name]['_init_'] = False
                continue
            HARD_LOAD[name]['_init_'] = 'Starting'
            # self._log_loader('debug', name, 'library', 'init', 'About to call _init_.')

            component = name.lower()
            library = self.loadedLibraries[component]
            library._event_loop = self.event_loop

            library._AMQP = self.loadedLibraries['amqp']
            library._AMQPYombo = self.loadedLibraries['amqpyombo']
            library._Atoms = self.loadedLibraries['atoms']
            library._Commands = self.loadedLibraries['commands']
            library._Configs = self.loadedLibraries['configuration']
            library._Devices = self.loadedLibraries['devices']
            library._DeviceTypes = self.loadedLibraries['devicetypes']
            library._GPG = self.loadedLibraries['gpg']
            library._InputTypes = self.loadedLibraries['inputtypes']
            library._Libraries = self.loadedLibraries
            library._Loader = self
            library._LocalDB = self.loadedLibraries['localdb']
            library._Modules = self._moduleLibrary
            library._Nodes = self.loadedLibraries['nodes']
            library._Notifications = self.loadedLibraries['notifications']
            library._Localize = self.loadedLibraries['localize']
            library._MQTT = self.loadedLibraries['mqtt']
            library._Queue = self.loadedLibraries['queue']
            library._SQLDict = self.loadedLibraries['sqldict']
            library._SSLCerts = self.loadedLibraries['sslcerts']
            library._States = self.loadedLibraries['states']
            library._Statistics = self.loadedLibraries['statistics']
            library._Tasks = self.loadedLibraries['tasks']
            library._Times = self.loadedLibraries['times']
            library._YomboAPI = self.loadedLibraries['yomboapi']
            library._Variables = self.loadedLibraries['variables']
            if hasattr(library, '_init_') and isinstance(library._init_, collections.Callable) \
                    and yombo.utils.get_method_definition_level(library._init_) != 'yombo.core.module.YomboModule':
                d = Deferred()
                d.addCallback(lambda ignored: self._log_loader('debug', name, 'library', 'init', 'About to call _init_.'))
                d.addCallback(lambda ignored: maybeDeferred(library._init_))
                d.addErrback(self.import_libraries_failure)
                # d.addCallback(lambda ignored: self._log_loader('debug', name, 'library', 'init', 'Done with call _init_.'))
                d.callback(1)
                yield d
                # d.addCallback(maybeDeferred, library._init_)
                # self._log_loader('debug', name, 'library', 'init', 'Finished to call _init_.')
                # try:
                #     d = yield maybeDeferred(library._init_, self)
                # except YomboCritical, e:
                #     logger.error("---==(Critical Server Error in init function for library: {name})==----", name=name)
                #     logger.error("--------------------------------------------------------")
                #     logger.error("Error message: {e}", e=e)
                #     logger.error("--------------------------------------------------------")
                #     e.exit()
                # except:
                #     logger.error("-------==(Error in init function for library: {name})==---------", name=name)
                #     logger.error("1:: {e}", e=sys.exc_info())
                #     logger.error("---------------==(Traceback)==--------------------------")
                #     logger.error("{e}", e=traceback.print_exc(file=sys.stdout))
                #     logger.error("--------------------------------------------------------")
                HARD_LOAD[name]['_init_'] = True
            else:
                logger.error("----==(Library doesn't have init function: {name})==-----", name=name)

    def check_operation_mode(self, allowed):
        """
        Checks if something should be run based on the current operation_mode.
        :param config: Either string or list or posible operation_modes
        :return: True/False
        """
        op_mode = self.operation_mode

        if op_mode is None:
            return True

        def check_operation_mode_inside(mode, op_mode):
            if mode == 'all':
                return True
            elif mode == op_mode:
                return True
            return False

        if isinstance(allowed, str):  # we have a string
            return check_operation_mode_inside(allowed, op_mode)
        else: # we have something else
            for item in allowed:
                if check_operation_mode_inside(item, op_mode):
                    return True

    def library_invoke_failure(self, failure, requested_library, hook_name):
        logger.error("Got failure during library invoke for hook ({requested_library}::{hook_name}): {failure}",
                     requested_library=requested_library,
                     hook_name=hook_name,
                     failure=failure)

    @inlineCallbacks
    def library_invoke(self, requested_library, hook, **kwargs):
        """
        Invokes a hook for a a given library. Passes kwargs in, returns the results to caller.
        """
        requested_library = requested_library.lower()
        if requested_library not in self.loadedLibraries:
            raise YomboWarning('Requested library is missing: %s' % requested_library)

        if 'called_by' not in kwargs:
            raise YomboWarning("Unable to call hook '%s:%s', missing 'called_by' named argument." % (requested_library, hook))
        calling_component = kwargs['called_by']

        cache_key = requested_library + hook
        if cache_key in self._invoke_list_cache:
            if self._invoke_list_cache[cache_key] is False:
                # logger.warn("Cache hook ({cache_key})...SKIPPED", cache_key=cache_key)
                returnValue(None) # skip. We already know function doesn't exist.
        library = self.loadedLibraries[requested_library]
        if requested_library == 'Loader':
            returnValue(None)
        if not (hook.startswith("_") and hook.endswith("_")):
            hook = library._Name.lower() + "_" + hook
        if hasattr(library, hook):
            method = getattr(library, hook)
            if isinstance(method, collections.Callable):
                if library._Name not in self.hook_counts:
                    self.hook_counts[library._Name] = {}
                if hook not in self.hook_counts:
                    self.hook_counts[library._Name][hook] = {'Total Count': {'count': 0}}
                # print "hook counts: %s" % self.hook_counts
                # print "hook counts: %s" % self.hook_counts[library._Name][hook]
                if calling_component not in self.hook_counts[library._Name][hook]:
                    self.hook_counts[library._Name][hook][calling_component] = {'count': 0}
                self.hook_counts[library._Name][hook][calling_component]['count'] = self.hook_counts[library._Name][hook][calling_component]['count'] + 1
                self.hook_counts[library._Name][hook]['Total Count']['count'] = self.hook_counts[library._Name][hook]['Total Count']['count'] + 1
                self._invoke_list_cache[cache_key] = True

                try:
                    d = Deferred()
                    d.addCallback(lambda ignored: self._log_loader('debug', library._Name, 'library', hook,
                                                                   'About to call _init_.'))
                    # print("calling %s:%s" % (library._Name, hook))
                    d.addCallback(lambda ignored: maybeDeferred(method, **kwargs))
                    d.addErrback(self.library_invoke_failure, requested_library, hook)
                    d.callback(1)
                    results = yield d
                    return results
                except RuntimeWarning as e:
                    pass
            else:
                logger.debug("Cache library hook ({library}:{hook})...setting false", library=library._FullName, hook=hook)
                logger.debug("----==(Library {library} doesn't have a callable function: {function})==-----", library=library._FullName, function=hook)
                raise YomboWarning("Hook is not callable: %s" % hook)
        else:
#            logger.debug("Cache hook ({library}:{hook})...setting false", library=library._FullName, hook=hook)
            self._invoke_list_cache[cache_key] = False

    @inlineCallbacks
    def library_invoke_all(self, hook, fullName=False, **kwargs):
        """
        Calls library_invoke for all loaded libraries.
        """
        results = {}
        to_process = {}
        if 'components' in kwargs:
            to_process = kwargs['components']
        else:
            for library_name, library in self.loadedLibraries.items():
#                print "library %s" % library
                label = library._FullName.lower() if fullName else library._Name.lower()
                to_process[library_name] = label

        for library_name, library in self.loadedLibraries.items():
            # logger.debug("invoke all:{libraryName} -> {hook}", libraryName=library_name, hook=hook )
            try:
                result = yield self.library_invoke(library_name, hook, **kwargs)
                if result is None:
                    continue
                results[library._FullName] = result
            except YomboWarning:
                pass
            except YomboHookStopProcessing as e:
                e.collected = results
                e.by_who =  label
                raise

        returnValue(results)

    def import_component(self, pathName, componentName, componentType, componentUUID=None):
        """
        Load component of given name. Can be a core library, or a module.
        """
        pymodulename = pathName.lower()
        self._log_loader('debug', componentName, componentType, 'import', 'About to import.')
        try:
            pyclassname = ReSearch("(?<=\.)([^.]+)$", pathName).group(1)
        except AttributeError:
            self._log_loader('error', componentName, componentType, 'import', 'Not found. Path: %s' % pathName)
            logger.error("Library or Module not found: {pathName}", pathName=pathName)
            raise YomboCritical("Library or Module not found: %s", pathName)
        try:
            module_root = __import__(pymodulename, globals(), locals(), [], 0)
        except ImportError as detail:
            self._log_loader('error', componentName, componentType, 'import', 'Not found. Path: %s' % pathName)
            logger.error("--------==(Error: Library or Module not found)==--------")
            logger.error("----Name: {pathName},  Details: {detail}", pathName=pathName, detail=detail)
            logger.error("---------------==(Traceback)==--------------------------")
            logger.error("{trace}", trace=traceback.format_exc())
            logger.error("--------------------------------------------------------")
            raise ImportError("Cannot import module, not found.")

        module_tail = reduce(lambda p1, p2: getattr(p1, p2), [module_root, ]+pymodulename.split('.')[1:])
        # print "module_tail: %s   pyclassname: %s" % (module_tail, pyclassname)
        klass = getattr(module_tail, pyclassname)
        # print "klass: %s  " % klass

        # Put the component into various lists for mgmt
        if not isinstance(klass, collections.Callable):
            logger.warn("Unable to start class '{classname}', it's not callable.", classname=pyclassname)
            raise ImportError("Unable to start class '%s', it's not callable."  % pyclassname)

        try:
            # Instantiate the class
            # logger.debug("Instantiate class: {pyclassname}", pyclassname=pyclassname)
            moduleinst = klass()  # start the class, only libraries get the loader
            if componentType == 'library':
                if componentName.lower() == 'modules':
                    self._moduleLibrary = moduleinst

                self.loadedComponents["yombo.gateway.lib." + str(componentName.lower())] = moduleinst
                self.loadedLibraries[str(componentName.lower())] = moduleinst
                # this is mostly for manhole module, but maybe useful elsewhere?
                temp = componentName.split(".")
                self.libraryNames[temp[-1]] = moduleinst
            else:
                self.loadedComponents["yombo.gateway.modules." + str(componentName.lower())] = moduleinst
                return moduleinst, componentName.lower()

        except YomboCritical as e:
            logger.debug("@!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            logger.debug("{e}", e=e)
            logger.debug("@!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            e.exit()
            raise

    @inlineCallbacks
    def unload_libraries(self):
        """
        Only called when server is doing shutdown. Stops controller, server control and server data..
        """
        logger.debug("Stopping libraries: {stuff}", stuff=HARD_UNLOAD)
        for name, config in HARD_UNLOAD.items():
            if self.check_operation_mode(config['operation_mode']):
                logger.debug("stopping: {name}", name=name)
                yield self.library_invoke(name, "_stop_", called_by=self)

        for name, config in HARD_UNLOAD.items():
            if self.check_operation_mode(config['operation_mode']):
                logger.debug("_unload_: {name}", name=name)
                yield self.library_invoke(name, "_unload_", called_by=self)

    def _handleError(self, err):
#        logger.error("Error caught: %s", err.getErrorMessage())
#        logger.error("Error type: %s  %s", err.type, err.value)
        err.raiseException()

    def get_loaded_component(self, name):
        """
        Returns loaded module object by name. Module must be loaded.
        """
        return self.loadedComponents[name.lower()]

    def get_all_loaded_components(self):
        """
        Returns loaded module object by name. Module must be loaded.
        """
        return self.loadedComponents

    def find_function(self, component_type, component_name, component_function):
        """
        Finds a function within the system by namme. This is useful for when you need to
        save a pointer to a callback to sql or a dictionary, but cannot save pointers to
        a function because the system may restart. This offers another method to reach
        various functions within the system.

        :param component_type: Either 'module' or 'library'.
        :param component_name: Module or libary name.
        :param component_function: Name of the function. A string for direct access to the function or a list
            can be provided and it will search the a dictionary of items for a callback.
        :return:
        """

        if component_type == 'library':
            if component_name not in self.loadedLibraries:
                logger.info("Library not found: {loadedLibraries}", loadedLibraries=loadedLibraries)
                raise YomboWarning("Cannot library name.")

            if isinstance(component_function, list):
                if hasattr(self.loadedLibraries[component_name], component_function[0]):
                    remote_attribute = getattr(self.loadedLibraries[component_name], component_function[0]) # the dictionary
                    if component_function[1] in remote_attribute:
                        if not isinstance(remote_attribute[component_function[1]], collections.Callable): # the key should be callable.
                            logger.info(
                                "Could not find callable library function by name: '{component_type} :: {component_name} :: (list) {component_function}'",
                                component_type=component_type, component_name=component_name, component_function=component_function)
                            raise YomboWarning("Cannot find callable")
                        else:
                            logger.info("Look ma, I found a cool function here.")
                            return remote_attribute[component_function[1]]
            else:
                if hasattr(self.loadedLibraries[component_name], component_function):
                    method = getattr(self.loadedLibraries[component_name], component_function)
                    if not isinstance(method, collections.Callable):
                        logger.info(
                            "Could not find callable modoule function by name: '{component_type} :: {component_name} :: {component_function}'",
                            component_type=component_type, component_name=component_name, component_function=component_function)
                        raise YomboWarning("Cannot find callable")
                    else:
                        return method
        elif component_type == 'module':
            modules = self._moduleLibrary
            if component_name not in modules._modulesByName:
                raise YomboWarning("Cannot module name.")

            if hasattr(modules._modulesByName[component_name], component_function[0]):
                remote_attribute = getattr(modules._modulesByName[component_name], component_function[0])
                if component_function[1] in remote_attribute:
                    if not isinstance(remote_attribute[component_function[1]], collections.Callable):  # the key should be callable.
                        logger.info(
                            "Could not find callable module function by name: '{component_type} :: {component_name} :: (list){component_function}'",
                            component_type=component_type, component_name=component_name,
                            component_function=component_function)
                        raise YomboWarning("Cannot find callable")
                    else:
                        logger.info("Look ma, I found a cool function here.")
                        return remote_attribute[component_function[1]]
            else:
                if hasattr(modules._modulesByName[component_name], component_function):
                    method = getattr(modules._modulesByName[component_name], component_function)
                    if not isinstance(method, collections.Callable):
                        logger.info(
                            "Could not find callable module function by name: '{component_type} :: {component_name} :: {component_function}'",
                            component_type=component_type, component_name=component_name,
                            component_function=component_function)
                        raise YomboWarning("Cannot find callable")
                    else:
                        return method
        else:
            logger.warn("Not a valid component_type: {component_type}", component_type=component_type)
            raise YomboWarning("Invalid component_type.")


_loader = None

def setup_loader(testing=False):
    global _loader
    if not _loader:
        _loader = Loader(testing)
    return _loader

def get_loader():
    global _loader
    return _loader

def get_the_loaded_components():
    global _loader
    return _loader.get_all_loaded_components()

def stop_loader():
    global _loader
    if not _loader:
        return
    else:
        _loader.unload()
    return