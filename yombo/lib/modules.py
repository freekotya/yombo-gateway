# This file was created by Yombo for use with Yombo Python gateway automation
# software.  Details can be found at https://yombo.net
"""
.. rst-class:: floater

.. note::

  For more information see: `Modules @ Module Features <https://yombo.net/docs/features/modules/>`_

Manages all modules within the system. Provides a single reference to perform module lookup functions, etc.

Also calls module hooks as requested by other libraries and modules.

.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>

:copyright: Copyright 2012-2017 by Yombo.
:license: LICENSE for details.
"""
# Import python libraries
import ConfigParser
import sys
import traceback
from time import time
import hashlib
from functools import partial

# Import twisted libraries
from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue

# Import Yombo libraries
from yombo.core.exceptions import YomboHookStopProcessing, YomboWarning, YomboCritical
from yombo.core.library import YomboLibrary
from yombo.core.log import get_logger
from yombo.utils import search_instance, do_search_instance, dict_merge
from yombo.utils.decorators import memoize_ttl

from yombo.utils.maxdict import MaxDict

logger = get_logger('library.modules')

SYSTEM_MODULES = {}
SYSTEM_MODULES['automationhelpers'] = {
    'id': 'automationhelpers', # module_id
    'gateway_id': 'local',
    'module_type': 'logic',
    'machine_label': 'AutomationHelpers',
    'label': 'Automation Helpers',
    'short_description': "Adds basic platforms to the automation rules.",
    'description': "Adds basic platforms to the automation rules.",
    'description_formatting': 'text',
    'install_branch': 'system',
    'install_count': '',
    'see_also': '',
    'prod_branch': '',
    'dev_branch': '',
    'prod_version': '',
    'dev_version': '',
    'repository_link': '',
    'issue_tracker_link': '',
    'doc_link': 'https://yombo.net/docs/features/automation-rules/',
    'git_link': '',
    'public': '2',
    'status': '1',
    'created': int(time()),
    'updated': int(time()),
    'load_source': 'system modules',
    }

class Modules(YomboLibrary):
    """
    A single place for modudule management and reference.
    """

    _rawModulesList = {}

    modules = {}  # Stores a list of modules. Populated by the loader module at startup.

    _localModuleVars = {}  # Used to store modules variables from file import

    def __contains__(self, module_requested):
        """
        .. note:: The command must be enabled to be found using this method. Use :py:meth:`get <Commands.get>`
           to set status allowed.

        Checks to if a provided command id, label, or machine_label exists.

            >>> if '137ab129da9318' in self._Commands:

        or:

            >>> if 'living room light' in self._Commands:

        :raises YomboWarning: Raised when request is malformed.
        :param module_requested: The command ID, label, or machine_label to search for.
        :type module_requested: string
        :return: Returns true if exists, otherwise false.
        :rtype: bool
        """
        try:
            self.get(module_requested)
            return True
        except:
            return False

    def __getitem__(self, module_requested):
        """
        .. note:: The module must be enabled to be found using this method. Use :py:meth:`get <Modules.get>`
           to set status allowed.

        Attempts to find the device requested using a couple of methods.

            >>> off_cmd = self._Modules['Sjho381jSASD013ug']  #by id

        or:

            >>> off_cmd = self._Modules['homevision']  #by label & machine_label

        :raises YomboWarning: Raised when request is malformed.
        :raises KeyError: Raised when request is not found.
        :param module_requested: The module ID, label, or machine_label to search for.
        :type module_requested: string
        :return: A pointer to the module instance.
        :rtype: instance
        """
        return self.get(module_requested)


    def __setitem__(self, module_requested, value):
        """
        Sets are not allowed. Raises exception.

        :raises Exception: Always raised.
        """
        raise Exception("Not allowed.")

    def __delitem__(self, module_requested):
        """
        Deletes are not allowed. Raises exception.

        :raises Exception: Always raised.
        """
        raise Exception("Not allowed.")
    def __iter__(self):
        """ iter modules. """
        return self.modules.__iter__()

    def __len__(self):
        """
        Returns an int of the number of modules configured.

        :return: The number of modules configured.
        :rtype: int
        """
        return len(self.modules)

    def __str__(self):
        """
        Returns the name of the library.
        :return: Name of the library
        :rtype: string
        """
        return "Yombo modules library"

    def keys(self):
        """
        Returns the keys (module ID's) that are configured.

        :return: A list of module IDs. 
        :rtype: list
        """
        return self.modules.keys()

    def items(self):
        """
        Gets a list of tuples representing the modules configured.

        :return: A list of tuples.
        :rtype: list
        """
        return self.modules.items()

    def iteritems(self):
        return self.modules.iteritems()

    def iterkeys(self):
        return self.modules.iterkeys()

    def itervalues(self):
        return self.modules.itervalues()

    def values(self):
        return self.modules.values()

    def _init_(self):
        """
        Init doesn't do much. Just setup a few variables. Things really happen in start.
        """
        self.gwid = self._Configs.get("core", "gwid")
        self._invoke_list_cache = {}  # Store a list of hooks that exist or not. A cache.
        self.hook_counts = {}  # keep track of hook names, and how many times it's called.
        self.hooks_called = MaxDict(200, {})
        self.module_search_attributes = ['_module_id', '_module_type', '_label', '_machine_label', '_description',
            'short_description', 'description_formatting', '_public', '_status']

    @inlineCallbacks
    def load_modules(self):
        """
        Loads the modules. Imports and calls various module hooks at startup.

        **Hooks implemented**:

        * _modules_created_ : Only called to libraries, is called before modules called for _init_.
        * _init_ : Only called to modules, is called as part of the _init_ sequence.
        * _modules_inited_ : Only called to libraries, is called after modules called for _init_.
        * _preload_ : Only called to modules, is called before _load_.
        * _modules_preloaded_ : Only called to libraries, is called after modules called for _preload_.
        * _load_ : Only called to modules, is called as part of the _load_ sequence.
        * _modules_loaded_ : Only called to libraries, is called after modules called for _load_.
        * _prestart_ : Only called to modules, is called as part of the _prestart_ sequence.
        * _modules_prestarted_ : Only called to libraries, is called after modules called for _prestart_.
        * _start_ : Only called to modules, is called as part of the _start_ sequence.
        * _modules_started_ : Only called to libraries, is called after modules called for _start_.
        * _started_ : Only called to modules, is called as part of the _started_ sequence.
        * _modules_start_finished_ : Only called to libraries, is called after modules called for _started_.

        :return:
        """
#        logger.debug("starting modules::load_modules !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        yield self.build_raw_module_list()  # Create a list of modules, includes localmodules.ini
        yield self.import_modules()  # Just call "import moduleName"

        logger.debug("starting modules::init....")
        # Init
        yield self._Loader.library_invoke_all("_modules_created_", called_by=self)
        yield self.module_init_invoke()  # Call "_init_" of modules
        yield self._Loader.library_invoke_all("_modules_inited_", called_by=self)

        # Pre-Load
        logger.debug("starting modules::pre-load....")
        yield self.module_invoke_all("_preload_yombo_internal_", called_by=self)
        yield self.module_invoke_all("_preload_", called_by=self)
        yield self._Loader.library_invoke_all("_modules_preloaded_", called_by=self)
        # Load
        yield self.module_invoke_all("_load_yombo_internal_", called_by=self)
        yield self.module_invoke_all("_load_", called_by=self)
        yield self._Loader.library_invoke_all("_modules_loaded_", called_by=self)

        # Pre-Start
        yield self.module_invoke_all("_prestart_yombo_internal_", called_by=self)
        yield self.module_invoke_all("_prestart_", called_by=self)
        yield self._Loader.library_invoke_all("_modules_prestarted_", called_by=self)

        # Start
        yield self.module_invoke_all("_start_yombo_internal_", called_by=self)
        yield self.module_invoke_all("_start_", called_by=self)
        yield self._Loader.library_invoke_all("_modules_started_", called_by=self)

        yield self.module_invoke_all("_started_yombo_internal_", called_by=self)
        yield self.module_invoke_all("_started_", called_by=self)
        yield self._Loader.library_invoke_all("_modules_start_finished_", called_by=self)

    @inlineCallbacks
    def unload_modules(self):
        """
        Unloads modules.

        **Hooks implemented**:

        * _module_stop_ : Only called to libraries, is called before modules called for _stop_.
        * _stop_ : Only called to modules, is called as part of the _stop_ sequence.
        * _module_unload_ : Only called to libraries, is called before modules called for _unload_.
        * _unload_ : Only called to modules, is called as part of the _unload_ sequence.

        :return:
        """
        self._Loader.library_invoke_all("_module_stop_", called_by=self)
        self.module_invoke_all("_stop_")

        keys = self.modules.keys()
        self._Loader.library_invoke_all("_module_unload_", called_by=self)
        for module_id in keys:
            module = self.modules[module_id]
            if int(module._status) != 1:
                continue

            try:
                self.module_invoke(module._Name, "_unload_", called_by=self)
            except YomboWarning:
                pass
            finally:
                yield self._Loader.library_invoke_all("_module_unloaded_", called_by=self)
                delete_component = module._FullName
                self.del_imported_module(module_id, module._Name.lower())
                if delete_component.lower() in self._Loader.loadedComponents:
                    del self._Loader.loadedComponents[delete_component.lower()]

    @inlineCallbacks
    def build_raw_module_list(self):
        try:
            fp = open("localmodules.ini")
            ini = ConfigParser.SafeConfigParser()
            ini.optionxform=str
            ini.readfp(fp)
            for section in ini.sections():
                options = ini.options(section)
                if 'mod_machine_label' in options:
                    mod_machine_label = ini.get(section, 'mod_machine_label')
                    options.remove('mod_machine_label')
                else:
                    mod_machine_label = section

                if 'mod_label' in options:
                    mod_label = ini.get(section, 'mod_label')
                    options.remove('mod_label')
                else:
                    mod_label = section

                if 'mod_short_description' in options:
                    mod_short_description = ini.get(section, 'mod_short_description')
                    options.remove('mod_short_description')
                else:
                    mod_short_description = section

                if 'mod_description' in options:
                    mod_description = ini.get(section, 'mod_description')
                    options.remove('mod_description')
                else:
                    mod_description = section

                if 'mod_description_formatting' in options:
                    mod_description_formatting = ini.get(section, 'mod_description_formatting')
                    options.remove('mod_description_formatting')
                else:
                    mod_description_formatting = 'text'

                if 'mod_module_type' in options:
                    mod_module_type = ini.get(section, 'mod_module_type')
                    options.remove('mod_module_type')
                else:
                    mod_module_type = ""

                if 'mod_see_also' in options:
                    mod_see_also = ini.get(section, 'mod_see_also')
                    options.remove('mod_see_also')
                else:
                    mod_see_also = ""

                if 'mod_module_type' in options:
                    mod_module_type = ini.get(section, 'mod_module_type')
                    options.remove('mod_module_type')
                else:
                    mod_module_type = ""

                if 'mod_doc_link' in options:
                    mod_doc_link = ini.get(section, 'mod_doc_link')
                    options.remove('mod_doc_link')
                else:
                    mod_doc_link = ""

                newUUID = hashlib.md5(mod_machine_label).hexdigest()
                self._rawModulesList[newUUID] = {
                  'id': newUUID, # module_id
                  'gateway_id': 'local',
                  'module_type': mod_module_type,
                  'machine_label': mod_machine_label,
                  'label': mod_label,
                  'short_description': mod_short_description,
                  'description': mod_description,
                  'description_formatting': mod_description_formatting,
                  'see_also': mod_see_also,
                  'install_count': 1,
                  'install_branch': '',
                  'prod_branch': '',
                  'dev_branch': '',
                  'repository_link': '',
                  'issue_tracker_link': '',
                  'doc_link': mod_doc_link,
                  'git_link': '',
                  'prod_version': '',
                  'dev_version': '',
                  'public': '0',
                  'status': '1',
                  'created': int(time()),
                  'updated': int(time()),
                  'load_source': 'localmodules.ini'
                }

                self._localModuleVars[mod_label] = {}
                for item in options:
                    logger.info("Adding module from localmodule.ini: {item}", item=item)
                    if item not in self._localModuleVars[mod_label]:
                        self._localModuleVars[mod_label][item] = []
                    values = ini.get(section, item)
                    values = values.split(":::")
                    for value in values:
                        variable = {
                            'data_relation_id': newUUID,
                            'data_relation_type': 'module',
                            'field_machine_label': item,
                            'field_label': item,
                            'value': value,
                            'data_weight': 0,
                            'field_weight': 0,
                            'encryption': "nosuggestion",
                            'input_min': -8388600,
                            'input_max': 8388600,
                            'input_casing': 'none',
                            'input_required': 0,
                            'input_type_id': "any",
                            'variable_id': 'xxx',
                            'created': int(time()),
                            'updated': int(time()),
                        }
                        self._localModuleVars[mod_label][variable['field_machine_label']].append(variable)

#            logger.debug("localmodule vars: {lvars}", lvars=self._localModuleVars)
            fp.close()
        except IOError as (errno, strerror):
            logger.debug("localmodule.ini error: I/O error({errornumber}): {error}", errornumber=errno, error=strerror)

        # Local system modules.
        for module_name, data in SYSTEM_MODULES.iteritems():
            # print data
            if self._Configs.get('system_modules', data['machine_label'], 'enabled') != 'enabled':
                continue
            self._rawModulesList[data['id']] = data

        modulesDB = yield self._LocalDB.get_modules()
        # print "modulesdb: %s" % modulesDB
        # print " "
        for module in modulesDB:
            # print "module: %s" % module
            self._rawModulesList[module.id] = module.__dict__
            self._rawModulesList[module.id]['load_source'] = 'sql'
        # print "_rawModulesList: %s" % self._rawModulesList

#        logger.debug("Complete list of modules, before import: {rawModules}", rawModules=self._rawModulesList)

    def import_modules(self):
        logger.debug("Import modules: self._rawModulesList: {_rawModulesList}", _rawModulesList=self._rawModulesList)
        for module_id, module in self._rawModulesList.iteritems():
            pathName = "yombo.modules.%s" % module['machine_label']
            # print "loading: %s" % pathName
            try:
                module_instance, module_name = self._Loader.import_component(pathName, module['machine_label'], 'module', module['id'])
            except ImportError, e:
                continue
            except:
                logger.error("--------==(Error: Loading Module)==--------")
                logger.error("----Name: {pathName}", pathName=pathName)
                logger.error("---------------==(Traceback)==--------------------------")
                logger.error("{trace}", trace=traceback.format_exc())
                logger.error("--------------------------------------------------------")
                logger.error("Not loading module: %s" % module['machine_label'])
                continue

            self.add_imported_module(module['id'], module_name, module_instance)
            self.modules[module_id]._hooks_called = {}
            self.modules[module_id]._module_id = module['id']
            self.modules[module_id]._module_type = module['module_type']
            self.modules[module_id]._machine_label = module['machine_label']
            self.modules[module_id]._label = module['label']
            self.modules[module_id]._short_description = module['short_description']
            self.modules[module_id]._description = module['description']
            self.modules[module_id]._description_formatting = module['description_formatting']
            self.modules[module_id]._install_count = module['install_count']
            self.modules[module_id]._see_also = module['see_also']
            self.modules[module_id]._repository_link = module['repository_link']
            self.modules[module_id]._issue_tracker_link = module['issue_tracker_link']
            self.modules[module_id]._doc_link = module['doc_link']
            self.modules[module_id]._git_link = module['git_link']
            self.modules[module_id]._install_branch = module['install_branch']
            self.modules[module_id]._prod_branch = module['prod_branch']
            self.modules[module_id]._dev_branch = module['prod_branch']
            self.modules[module_id]._prod_version = module['prod_version']
            self.modules[module_id]._dev_version = module['dev_version']
            self.modules[module_id]._public = module['public']
            self.modules[module_id]._status = module['status']
            self.modules[module_id]._created = module['created']
            self.modules[module_id]._updated = module['updated']
            self.modules[module_id]._load_source = module['load_source']
            self.modules[module_id]._device_types = []  # populated by Modules::module_init_invoke
            # print "loading modules: %s" % self.modules[module_id]._machine_label
            # print "loading modules: %s" % self.modules[module_id]._status


    @inlineCallbacks
    def get_module_variables(self, module_name, data_relation_type, data_relation_id):
        variables = yield self._Variables.get_variable_fields_data(
            data_relation_type=data_relation_type,
            data_relation_id=data_relation_id)

        if module_name in self._localModuleVars:
            returnValue(dict_merge(variables, self._localModuleVars[module_name]))

        returnValue(variables)

    @inlineCallbacks
    def module_init_invoke(self):
        """
        Calls the _init_ functions of modules.
        """
        module_init_deferred = []

        for module_id, module in self.modules.iteritems():
            self.modules_invoke_log('debug', module._FullName, 'module', 'init', 'About to call _init_.')

            # Get variables, and merge with any local variable settings
            # print "getting vars for module: %s" % module_id
            # print "getting vars: %s "% module_variables
            # module._ModuleVariables_get_live = self._Variables.get_variable_fields_data_callable(
            #     data_relation_type='module',
            #     data_relation_id=module_id)
            #

            module._ModuleVariables = partial(
                self.get_module_variables,
                module._Name,
                'module',
                module_id,
            )

            module._ModuleDevices = partial(
                self.module_devices,
                module_id,
            )

            module._ModuleDeviceTypes = partial(
                self.module_device_types,
                module_id,
            )


            # if yombo.utils.get_method_definition_level(module._init_) != 'yombo.core.module.YomboModule':
            module._ModuleType = self._rawModulesList[module_id]['module_type']

            module._Atoms = self._Loader.loadedLibraries['atoms']
            module._Automation = self._Loader.loadedLibraries['automation']
            module._AMQP = self._Loader.loadedLibraries['amqp']
            module._AMQPYombo = self._Loader.loadedLibraries['amqpyombo']
            module._Commands = self._Loader.loadedLibraries['commands']
            module._Configs = self._Loader.loadedLibraries['configuration']
            module._CronTab = self._Loader.loadedLibraries['crontab']
            module._GPG = self._Loader.loadedLibraries['gpg']
            module._Libraries = self._Loader.loadedLibraries
            module._Libraries = self._Loader.loadedLibraries
            module._Localize = self._Loader.loadedLibraries['localize']
            module._Modules = self
            module._MQTT = self._Loader.loadedLibraries['mqtt']
            module._Nodes = self._Loader.loadedLibraries['nodes']
            module._Notifications = self._Loader.loadedLibraries['notifications']
            module._Queue = self._Loader.loadedLibraries['queue']
            module._SQLDict = self._Loader.loadedLibraries['sqldict']
            module._SSLCerts = self._Loader.loadedLibraries['sslcerts']
            module._States = self._Loader.loadedLibraries['states']
            module._Statistics = self._Loader.loadedLibraries['statistics']
            module._Tasks = self._Loader.loadedLibraries['tasks']
            module._Times = self._Loader.loadedLibraries['times']
            module._YomboAPI = self._Loader.loadedLibraries['yomboapi']
            module._Variables = self._Loader.loadedLibraries['variables']
            module._VoiceCmds = self._Loader.loadedLibraries['voicecmds']

            module._Devices = self._Loader.loadedLibraries['devices']  # Basically, all devices
            module._DeviceTypes = self._Loader.loadedLibraries['devicetypes']  # All device types.
            module._InputTypes = self._Loader.loadedLibraries['inputtypes']  # Input Types

            module._hooks_called['_init_'] = 0
            if int(module._status) != 1:
                continue

            module_device_types = yield self._LocalDB.get_module_device_types(module_id)
            # print "module_device_types = %s" % module_device_types
            for module_device_type in module_device_types:
                if module_device_type.id in module._DeviceTypes:
                    self.modules[module_id]._device_types.append(module_device_type.id)

#                module_init_deferred.append(maybeDeferred(module._init_))
#                continue
#             d = yield maybeDeferred(module._init_)
            try:
                # exc_info = sys.exc_info()
#                module_init_deferred.append(maybeDeferred(module._init_))
                d = yield maybeDeferred(module._init_)
                module._hooks_called['_init_'] = 1
#                    d.errback(self.SomeError)
#                    yield d
            except YomboCritical as e:
                logger.error("---==(Critical Server Error in _init_ function for module: {name})==----", name=module._FullName)
                logger.error("--------------------------------------------------------")
                logger.error("Error message: {e}", e=e)
                logger.error("--------------------------------------------------------")
                e.exit()
            except Exception:
                logger.error("-------==(Error in init function for module: {name})==---------", name=module._FullName)
                logger.error("1:: {e}", e=sys.exc_info())
                logger.error("---------------==(Traceback)==--------------------------")
                logger.error("3{e}", e=traceback.format_exc())
                logger.error("--------------------------------------------------------")
                # except:
                #     exc_type, exc_value, exc_traceback = sys.exc_info()
                #     logger.error("------==(ERROR During _init_ of module: {module})==-------", module=module._FullName)
                #     logger.error("1:: {e}", e=sys.exc_info())
                #     logger.error("---------------==(Traceback)==--------------------------")
                #     logger.error("{e}", e=traceback.print_exc(file=sys.stdout))
                #     logger.error("--------------------------------------------------------")
                #     logger.error("{e}", e=traceback.print_exc())
                #     logger.error("--------------------------------------------------------")
                #     logger.error("{e}", e=repr(traceback.print_exception(exc_type, exc_value, exc_traceback,
                #               limit=5, file=sys.stdout)))
                #     logger.error("--------------------------------------------------------")
#        logger.debug("!!!!!!!!!!!!!!!!!!!!!1 About to yield while waiting for module_init's to be done!")
#        yield DeferredList(module_init_deferred)
#        logger.debug("!!!!!!!!!!!!!!!!!!!!!2 Done yielding for while waiting for module_init's to be done!")

    def SomeError(self, error):
        logger.error("Received an error: {error}", error=error)

    @inlineCallbacks
    def module_invoke(self, requestedModule, hook, called_by=None, **kwargs):
        """
        Invokes a hook for a a given module. Passes kwargs in, returns the results to caller.
        """
        if called_by is not None:
            called_by = called_by._FullName
        else:
            called_by = 'Unknown'
        cache_key = requestedModule + hook
        if cache_key in self._invoke_list_cache:
            if self._invoke_list_cache[cache_key] is False:
                return  # skip. We already know function doesn't exist.
        module = self.get(requestedModule)
        if module._Name == 'yombo.core.module.YomboModule':
            self._invoke_list_cache[cache_key] is False
            # logger.warn("Cache module hook ({cache_key})...SKIPPED", cache_key=cache_key)
            returnValue(None)
            # raise YomboWarning("Cannot call YomboModule hooks")
        if not (hook.startswith("_") and hook.endswith("_")):
            hook = module._Name.lower() + "_" + hook
        self.modules_invoke_log('debug', requestedModule, 'module', hook, 'About to call.')
        if hasattr(module, hook):
            method = getattr(module, hook)
            if callable(method):
                if module._Name not in self.hook_counts:
                    self.hook_counts[module._Name] = {}
                if hook not in self.hook_counts[module._Name]:
                    self.hook_counts[module._Name][hook] = {'Total Count': {'count': 0}}
                # print "hook counts: %s" % self.hook_counts
                # print "hook counts: %s" % self.hook_counts[library._Name][hook]
                if called_by not in self.hook_counts[module._Name][hook]:
                    self.hook_counts[module._Name][hook][called_by] = {'count': 0}
                self.hook_counts[module._Name][hook][called_by]['count'] = self.hook_counts[module._Name][hook][called_by]['count'] + 1
                self.hook_counts[module._Name][hook]['Total Count']['count'] = self.hook_counts[module._Name][hook]['Total Count']['count'] + 1
                self.hooks_called[int(time())] = {
                    'module': module._Name,
                    'hook': hook,
                    'called_by': called_by,
                }

                try:
#                    results = yield maybeDeferred(method, **kwargs)
                    self._invoke_list_cache[cache_key] = True
                    if hook not in module._hooks_called:
                        module._hooks_called[hook] = 1
                    else:
                        module._hooks_called[hook] += 1
                    results = yield maybeDeferred(method, **kwargs)
                    returnValue(results)
                    # return method(**kwargs)
                # except Exception, e:
                #     logger.error("---==(Error in {hook} function for module: {name})==----", hook=hook, name=module._FullName)
                #     logger.error("--------------------------------------------------------")
                #     logger.error("Error message: {e}", e=e)
                #     logger.error("--------------------------------------------------------")
                except Exception, e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    logger.error("------==(ERROR During {hook} of module: {name})==-------", hook=hook, name=module._FullName)
                    logger.error("1:: {e}", e=sys.exc_info())
                    logger.error("---------------==(Traceback)==--------------------------")
                    logger.error("{e}", e=traceback.print_exc())
                    logger.error("--------------------------------------------------------")
                    # logger.error("{e}", e=repr(traceback.print_exception(exc_type, exc_value, exc_traceback,
                    #           limit=10, file=sys.stdout)))
                    # logger.error("--------------------------------------------------------")
            else:
                logger.debug("----==(Module {module} doesn't have a callable function: {function})==-----", module=module._FullName, function=hook)
        else:
            self._invoke_list_cache[cache_key] = False
            # logger.debug("Cache module hook ({library}:{hook})...setting false", library=module._FullName, hook=hook)

    @inlineCallbacks
    def module_invoke_all(self, hook, full_name=None, called_by=None, **kwargs):
        """
        Calls module_invoke for all loaded modules.
        """
        logger.debug("in module_invoke_all: hook: {hook}", hook=hook)
        if full_name == None:
            full_name = False
        results = {}
        for module_id, module in self.modules.iteritems():
            if int(module._status) != 1:
                continue

            label = module._FullName.lower() if full_name else module._Name.lower()
            try:
                 result = yield self.module_invoke(module._Name, hook, called_by=called_by, **kwargs)
                 if result is not None:
                     results[label] = result
            except YomboWarning:
                pass
            except YomboHookStopProcessing as e:
                e.collected = results
                e.by_who =  label
                raise

        returnValue(results)

    @inlineCallbacks
    def load_module_data(self):

        self.startDefer.callback(10)

    def add_imported_module(self, module_id, module_label, module_instance):
        logger.debug("adding module: {module_id}:{module_label}", module_id=module_id, module_label=module_label)
        self.modules[module_id] = module_instance

    def del_imported_module(self, module_id, module_label):
        logger.debug("deleting module_id: {module_id} from this list: {list}", module_id=module_id, list=self.modules)
        del self.modules[module_id]

    def get(self, module_requested, limiter=None, status=None):
        """
        Attempts to find the module requested using a couple of methods. Use the already defined pointer within a
        module to find another other:

            >>> someModule = self._Modules['137ab129da9318']  #by uuid

        or:

            >>> someModule = self._Modules['Homevision']  #by name

        :raises YomboWarning: For invalid requests.
        :raises KeyError: When item requested cannot be found.
        :param module_requested: The module id or module label to search for.
        :type module_requested: string
        :param limiter_override: Default: .89 - A value between .5 and .99. Sets how close of a match it the search should be.
        :type limiter_override: float
        :param status: Deafult: 1 - The status of the module to check for.
        :type status: int
        :return: Pointer to requested device.
        :rtype: dict
        """
        if limiter is None:
            limiter = .89

        if limiter > .99999999:
            limiter = .99
        elif limiter < .10:
            limiter = .10

        if module_requested in self.modules:
            item = self.modules[module_requested]
            if status is not None and item.status != status:
                raise KeyError("Requested mdule found, but has invalid status: %s" % item._status)
            return item
        else:
            attrs = [
                {
                    'field': '_module_id',
                    'value': module_requested,
                    'limiter': limiter,
                },
                {
                    'field': '_label',
                    'value': module_requested,
                    'limiter': limiter,
                },
                {
                    'field': '_machine_label',
                    'value': module_requested,
                    'limiter': limiter,
                }
            ]
            try:
                logger.debug("Get is about to call search...: %s" % module_requested)
                found, key, item, ratio, others = do_search_instance(attrs, self.modules,
                                                                     self.module_search_attributes,
                                                                     limiter=limiter,
                                                                     operation="highest")
                # logger.debug("found module by search: {module_id}", module_id=key)
                if found:
                    return item
                else:
                    raise KeyError("Module not found: %s" % module_requested)
            except YomboWarning, e:
                raise KeyError('Searched for %s, but found had problems: %s' % (module_requested, e))

    def search(self, _limiter=None, _operation=None, **kwargs):
        """
        Search for modules based on attributes for all modules.

        :param limiter_override: Default: .89 - A value between .5 and .99. Sets how close of a match it the search should be.
        :type limiter_override: float
        :param status: Deafult: 1 - The status of the module to check for.
        :return: 
        """
        for attr, value in kwargs.iteritems():
            if "_%s" % attr in self.module_search_attributes:
                kwargs[attr]['field'] = "_%s" % attr

        return search_instance(kwargs, self.modules, self.module_search_attributes, _limiter, _operation)

    def modules_invoke_log(self, level, label, type, method, msg=""):
        """
        A common log format for loading/unloading libraries and modules.

        :param level: Log level - debug, info, warn...
        :param label: Module label "x10", "messages"
        :param type: Type of item being loaded: library, module
        :param method: Method being called.
        :param msg: Optional message to include.
        :return:
        """
        logit = getattr(logger, level)
        logit("({log_source}) {label}({type})::{method} - {msg}", label=label, type=type, method=method, msg=msg)

    @memoize_ttl(120)
    def module_devices(self, module_id):
        """
        A list of devices for a given module id.

        :raises YomboWarning: Raised when module_id is not found.
        :param module_id: The Module ID to return device types for.
        :return: A dictionary of devices for a given module id.
        :rtype: list
        """
        if module_id not in self.modules:
                return {}

        temp = {}
        # print "dt..module_id: %s" % module_id
        # print "dt..self._Modules.modules[module_id].device_types: %s" % self._Modules._moduleClasses[module_id].device_types
        for dt in self.module_device_types(module_id):
            # print "self._DeviceTypes[dt].get_devices(): %s" % self._DeviceTypes[dt].get_devices()
            temp.update(self._DeviceTypes[dt].get_devices())

        return temp

    def module_device_types(self, module_id, return_value=None):
        if return_value is None:
            return_value = 'dict'
        elif return_value not in (['id', 'dict']):
            raise YomboWarning("module_device_types 'return_value' accepts: 'id' or 'dict'")

        if module_id not in self.modules:
            if return_value == 'id':
                return []
            elif return_value == 'dict':
                return {}

        if return_value == 'id':
            return self.modules[module_id]._device_types
        elif return_value == 'dict':
            results = {}
            for device_type_id in self.modules[module_id]._device_types:
                results[device_type_id] = self._DeviceTypes[device_type_id]
            return results


    @inlineCallbacks
    def add_module(self, data, **kwargs):
        """
        Adds a module to be installed. A restart is required to complete.

        :param data:
        :param kwargs:
        :return:
        """
        api_data = {
            'module_id': data['module_id'],
            'install_branch': data['install_branch'],
            'status': 1,
        }

        module_results = yield self._YomboAPI.request('POST', '/v1/gateway/%s/module' % self.gwid, api_data)
        # print("add module results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't add module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
                'module_id': data['module_id'],
            }
            returnValue(results)

        # print("checking if var data... %s" % data)
        if 'variable_data' in data:
            # print("adding variable data...")
            variable_data = data['variable_data']
            for field_id, var_data in variable_data.iteritems():
                # print("field_id: %s" % field_id)
                # print("var_data: %s" % var_data)
                for data_id, value in var_data.iteritems():
                    # print("data_id: %s" % data_id)
                    if data_id.startswith('new_'):
                        # print("data_id starts with new...")
                        post_data = {
                            'gateway_id': self.gwid,
                            'field_id': field_id,
                            'relation_id': data['module_id'],
                            'relation_type': 'module',
                            'data_weight': 0,
                            'data': value,
                        }
                        # print("post_data: %s" % post_data)
                        var_data_results = yield self._YomboAPI.request('POST', '/v1/variable/data', post_data)
                        # print "var_data_results: %s"  % var_data_results
                        if var_data_results['code']  > 299:
                            results = {
                                'status': 'failed',
                                'msg': "Couldn't add module variables",
                                'apimsg': var_data_results['content']['message'],
                                'apimsghtml': var_data_results['content']['html_message'],
                                'module_id': data['module_id']
                            }
                            returnValue(results)
                    else:
                        post_data = {
                            'data_weight': 0,
                            'data': value,
                        }
                        # print("posting to: /v1/variable/data/%s" % data_id)
                        # print("post_data: %s" % post_data)
                        var_data_results = yield self._YomboAPI.request('PATCH', '/v1/variable/data/%s' % data_id, post_data)
                        if var_data_results['code']  > 299:
                            # print("bad results module_results: %s" % module_results)
                            # print("bad results var_data_results: %s" % var_data_results)
                            results = {
                                'status': 'failed',
                                'msg': "Couldn't add module variables",
                                'apimsg': var_data_results['content']['message'],
                                'apimsghtml': var_data_results['content']['html_message'],
                                'module_id': data['module_id']
                            }
                            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module added.",
            'module_id': data['module_id']
        }
        returnValue(results)

    @inlineCallbacks
    def edit_module(self, module_id, data, **kwargs):
        """
        Edit the module installation information. A reboot is required for this to take effect.

        :param data:
        :param kwargs:
        :return:
        """
        api_data = {
            'install_branch': data['install_branch'],
            'status': data['status'],
        }

        module_results = yield self._YomboAPI.request('PATCH', '/v1/gateway/%s/module/%s' % (self.gwid, module_id), api_data)
        # print("module edit results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't edit module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module edited.",
            'module_id': module_id
        }
        returnValue(results)

    @inlineCallbacks
    def remove_module(self, module_id, **kwargs):
        """
        Delete a module. Calls the API to perform this task. A restart is required to complete.

        :param module_id: The module ID to disable.
        :param kwargs:
        :return:
        """
        if module_id not in self.modules:
            raise YomboWarning("module_id doesn't exist. Nothing to remove.", 300, 'disable_module', 'Modules')

        module_results = yield self._YomboAPI.request('DELETE', '/v1/gateway/%s/module/%s' % (self.gwid, module_id))
        # print("delete module results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't delete module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        self._LocalDB.set_module_status(module_id, 2)
        self._LocalDB.del_variables('module', module_id)

        results = {
            'status': 'success',
            'msg': "Module deleted.",
            'module_id': module_id,
        }
        #todo: add task to remove files.
        #todo: add system for "do something on next startup..."
        returnValue(results)

    @inlineCallbacks
    def enable_module(self, module_id, **kwargs):
        """
        Enable a module. Calls the API to perform this task. A restart is required to complete.

        :param module_id: The module ID to enable.
        :param kwargs:
        :return:
        """
        logger.debug("enabling module: {module_id}", module_id=module_id)
        api_data = {
            'status': 1,
        }

        if module_id not in self.modules:
            raise YomboWarning("module_id doesn't exist. Nothing to enable.", 300, 'enable_module', 'Modules')

        module_results = yield self._YomboAPI.request('PATCH', '/v1/gateway/%s/module/%s' % (self.gwid, module_id), api_data)
        # print("enable module results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't enable module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        self._LocalDB.set_module_status(module_id, 1)

        results = {
            'status': 'success',
            'msg': "Module enabled.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def disable_module(self, module_id, **kwargs):
        """
        Disable a module. Calls the API to perform this task. A restart is required to complete.

        :param module_id: The module ID to disable.
        :param kwargs:
        :return:
        """
        logger.debug("disabling module: {module_id}", module_id=module_id)
        api_data = {
            'status': 0,
        }

        if module_id not in self.modules:
            raise YomboWarning("module_id doesn't exist. Nothing to disable.", 300, 'disable_module', 'Modules')

        module_results = yield self._YomboAPI.request('PATCH', '/v1/gateway/%s/module/%s' % (self.gwid, module_id), api_data)
        # print("disable module results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't disable module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        self._LocalDB.set_module_status(module_id, 0)

        results = {
            'status': 'success',
            'msg': "Module disabled.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_add(self, data, **kwargs):
        """
        Add a module at the Yombo server level, not at the local gateway level.

        :param data:
        :param kwargs:
        :return:
        """
        module_results = yield self._YomboAPI.request('POST', '/v1/module', data)
        # print("module edit results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't add module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module added.",
            'module_id': module_results['data']['id'],
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_edit(self, module_id, data, **kwargs):
        """
        Edit a module at the Yombo server level, not at the local gateway level.

        :param data:
        :param kwargs:
        :return:
        """
        module_results = yield self._YomboAPI.request('PATCH', '/v1/module/%s' % (module_id), data)
        # print("module edit results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't edit module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module edited.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_delete(self, module_id, **kwargs):
        """
        Delete a module at the Yombo server level, not at the local gateway level.

        :param data:
        :param kwargs:
        :return:
        """
        module_results = yield self._YomboAPI.request('DELETE', '/v1/module/%s' % module_id)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't delete module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module deleted.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_enable(self, module_id, **kwargs):
        """
        Enable a module at the Yombo server level, not at the local gateway level.

        :param module_id: The module ID to enable.
        :param kwargs:
        :return:
        """
        api_data = {
            'status': 1,
        }

        module_results = yield self._YomboAPI.request('PATCH', '/v1/module/%s' % module_id, api_data)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't enable module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module enabled.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_disable(self, module_id, **kwargs):
        """
        Enable a module at the Yombo server level, not at the local gateway level.

        :param module_id: The module ID to disable.
        :param kwargs:
        :return:
        """
        # print "disabling module: %s" % module_id
        api_data = {
            'status': 0,
        }

        module_results = yield self._YomboAPI.request('PATCH', '/v1/module/%s' % module_id, api_data)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't disable module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module disabled.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_device_type_add(self, module_id, device_type_id):
        """
        Associate a device type to a module

        :param module_id: The module
        :param device_type_id: The device type to associate
        :return:
        """
        data = {
            'module_id': module_id,
            'device_type_id': device_type_id,
        }

        module_results = yield self._YomboAPI.request('POST', '/v1/module_device_type', data)
        # print("module edit results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't associate device type to module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Device type associated to module.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def dev_module_device_type_remove(self, module_id, device_type_id):
        """
        Removes an association of a device type from a module

        :param module_id: The module
        :param device_type_id: The device type to  remove association
        :return:
        """

        module_results = yield self._YomboAPI.request('DELETE', '/v1/module_device_type/%s/%s' % (module_id, device_type_id))
        # print("module edit results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't remove association device type from module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Device type removed from module.",
            'module_id': module_id,
        }
        returnValue(results)

    @inlineCallbacks
    def _api_change_status(self, module_id, new_status, **kwargs):
        """
        Used to enabled, disable, or undelete a module. Calls the API

        Disable a module. Calls the API to perform this task. A restart is required to complete.

        :param module_id: The module ID to disable.
        :param kwargs:
        :return:
        """
        # print "disabling module: %s" % module_id
        api_data = {
            'module_id': module_id,
            'status': new_status,
        }

        if module_id not in self.modules:
            raise YomboWarning("module_id doesn't exist. Nothing to disable.", 300, 'disable_module', 'Modules')

        module_results = yield self._YomboAPI.request('PATCH', '/v1/gateway/%s/module/%s' % (self.gwid, module_id))
        # print("disable module results: %s" % module_results)

        if module_results['code']  > 299:
            results = {
                'status': 'failed',
                'msg': "Couldn't disable module",
                'apimsg': module_results['content']['message'],
                'apimsghtml': module_results['content']['html_message'],
                'module_id': module_id,
            }
            returnValue(results)

        results = {
            'status': 'success',
            'msg': "Module disabled.",
            'module_id': module_id,
        }
        returnValue(results)

