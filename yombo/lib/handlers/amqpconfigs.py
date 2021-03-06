# This file was created by Yombo for use with Yombo Python Gateway automation
# software.  Details can be found at https://yombo.net
"""
This handler library is responsible for handling configuration messages received from amqpyombo library.

.. warning::

   This library is not intended to be accessed by developers or users. These functions, variables,
   and classes **should not** be accessed directly by modules. These are documented here for completeness.

.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>

:copyright: Copyright 2016-2017 by Yombo.
:license: LICENSE for details.
:view-source: `View Source Code <https://github.com/yombo/yombo-gateway/blob/master/yombo/lib/handler/amqpconfigs.py>`_
"""
# Import python libraries
from collections import deque, OrderedDict
try:  # Prefer simplejson if installed, otherwise json will work swell.
    import simplejson as json
except ImportError:
    import json
import msgpack
import sys
from time import time
import traceback

# Import twisted libraries
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

# Import Yombo libraries
from yombo.core.exceptions import YomboWarning
from yombo.core.library import YomboLibrary
from yombo.core.log import get_logger
from yombo.utils import random_string, dict_has_key, bytes_to_unicode, is_true_false

logger = get_logger('library.handler.amqpconfigs')

class AmqpConfigHandler(YomboLibrary):
    """
    Handles interactions with Yombo servers through the AMQP library.
    """
    config_item_map = {
        'devices': 'gateway_devices'
    }

    config_items = {
            'categories': {
                'dbclass': "Category",
                'table': "categories",
                'library': None,
                'functions': {
                    # 'process': "enable_command",
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'category_type': 'category_type',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'description': 'description',
                    'status': 'status',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                    # '': '',
                }
            },

            'gateway_cluster': {
                'dbclass': "Gateway",
                'table': "gateways",
                'library': "gateways",
                'functions': {
                    # 'process': "enable_command",
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'is_master': 'is_master',
                    'master_gateway': 'master_gateway',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'description': 'description',
                    'mqtt_auth': 'mqtt_auth',
                    'mqtt_auth_prev': 'mqtt_auth_prev',
                    'mqtt_auth_next': 'mqtt_auth_next',
                    'mqtt_auth_last_rotate': 'mqtt_auth_last_rotate',
                    'fqdn': 'fqdn',
                    'internal_ipv4': 'internal_ipv4',
                    'external_ipv4': 'external_ipv4',
                    'internal_ipv6': 'internal_ipv6',
                    'external_ipv6': 'external_ipv6',
                    'internal_port': 'internal_port',
                    'external_port': 'external_port',
                    'internal_secure_port': 'internal_secure_port',
                    'external_secure_port': 'external_secure_port',
                    'internal_mqtt': 'internal_mqtt',
                    'internal_mqtt_le': 'internal_mqtt_le',
                    'internal_mqtt_ss': 'internal_mqtt_ss',
                    'internal_mqtt_ws': 'internal_mqtt_ws',
                    'internal_mqtt_ws_le': 'internal_mqtt_ws_le',
                    'internal_mqtt_ws_ss': 'internal_mqtt_ws_ss',
                    'externalmqtt': 'externalmqtt',
                    'externalmqtt_le': 'externalmqtt_le',
                    'externalmqtt_ss': 'externalmqtt_ss',
                    'externalmqtt_ws': 'externalmqtt_ws',
                    'externalmqtt_ws_le': 'externalmqtt_ws_le',
                    'externalmqtt_ws_ss': 'externalmqtt_ws_ss',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },
            'gateway_dns_name': {
                'dbclass': "none",
                'table': "none",
                'library': None,
                'functions': {
                },
                'purgeable': False,
                'map': {
                }
            },

            'gateway_commands': {
                'dbclass': "Command",
                'table': "commands",
                'library': "commands",
                'functions': {
                    # 'process': "enable_command",
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'machine_label': 'machine_label',
                    'voice_cmd': 'voice_cmd',
                    'label': 'label',
                    'description': 'description',
                    'always_load': 'always_load',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                    'status': 'status',
                    'public': 'public',
                    # '': '',
                }
            },

            'gateway_devices': {
                'dbclass': "Device",
                'table': "devices",
                'library': "devices",
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': True,
                'map': {
                    'id': 'id',
                    'gateway_id': 'gateway_id',
                    'area_id': 'area_id',
                    'location_id': 'location_id',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'notes': 'notes',
                    'attributes': 'attributes',
                    'description': 'description',
                    'gateway_id': 'gateway_id',
                    'device_type_id': 'device_type_id',
                    'voice_cmd': 'voice_cmd',
                    'voice_cmd_order': 'voice_cmd_order',
                    'voice_cmd_src': 'voice_cmd_src',
                    'pin_code': 'pin_code',
                    'pin_required': 'pin_required',
                    'pin_timeout': 'pin_timeout',
                    'statistic_label': 'statistic_label',
                    'statistic_lifetime': 'statistic_lifetime',
                    'statistic_type': 'statistic_type',
                    'statistic_bucket_size': 'statistic_bucket_size',
                    'data': 'data',
                    'energy_type': 'energy_type',
                    'energy_tracker_source': 'energy_tracker_source',
                    'energy_tracker_device': 'energy_tracker_device',
                    'energy_map': 'energy_map',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                    'status': 'status',
                }
            },

            'gateway_device_command_inputs': {
                'dbclass': "DeviceCommandInput",
                'table': "device_command_inputs",
                'library': None,
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'category_id': 'category_id',
                    'device_type_id': 'device_type_id',
                    'command_id': 'command_id',
                    'input_type_id': 'input_type_id',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'live_update': 'live_update',
                    'value_required': 'value_required',
                    'value_max': 'value_max',
                    'value_min': 'value_min',
                    'value_casing': 'value_casing',
                    'encryption': 'encryption',
                    'notes': 'notes',
                    'always_load': 'always_load',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'gateway_locations': {
                'dbclass': "Location",
                'table': "locations",
                'library': None,
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'description': 'description',
                    'public': 'public',
                    'status': 'status',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'gateway_device_types': {
                'dbclass': "DeviceType",
                'table': "device_types",
                'library': "devicestypes",
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'category_id': 'category_id',
                    'platform': 'platform',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'description': 'description',
                    'always_load': 'always_load',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                    'public': 'public',
                    'status': 'status',
                }
            },

            'gateway_device_type_commands': {
                'dbclass': "DeviceTypeCommand",
                'table': "device_type_commands",
                'library': None,
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'device_type_id': 'device_type_id',
                    'command_id': 'command_id',
                    'created_at': 'created_at',
                }
            },

            'gateway_input_types': {
                'dbclass': "InputType",
                'table': "input_types",
                'library': "inputtypes",
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'category_id': 'category_id',
                    'machine_label': 'machine_label',
                    'label': 'label',
                    'description': 'description',
                    'input_regex': 'input_regex',
                    'always_load': 'always_load',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                    'public': 'public',
                    'status': 'status',
                }
            },

            'gateway_modules': {
                'dbclass': "Modules",
                'table': "modules",
                'library': "modules",
                'functions': {
                    # 'enabled': "enable_command",
                    # 'disabled': "enable_command",
                    # 'deleted': "enable_command",
                },
                'purgeable': True,
                'map': {
                    'module_id': 'id',
                    'gateway_id': 'gateway_id',
                    'machine_label': 'machine_label',
                    'module_type': 'module_type',
                    'label': 'label',
                    'short_description': 'short_description',
                    'description': 'description',
                    'description_formatting': 'description_formatting',
                    'see_also': 'see_also',
                    'repository_link': 'repository_link',
                    'issue_tracker_link': 'issue_tracker_link',
                    'install_count': 'install_count',
                    'doc_link': 'doc_link',
                    'git_link': 'git_link',
                    'prod_branch': 'prod_branch',
                    'dev_branch': 'dev_branch',
                    'prod_version': 'prod_version',
                    'dev_version': 'dev_version',
                    'install_branch': 'install_branch',
                    'always_load': 'always_load',
                    'public': 'public',
                    'status': 'status',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'gateway_configs': {},  # Processed with it's own catch.

            'gateway_users': {
                'dbclass': "Users",
                'table': "users",
                'library': None,
                'functions': {
                },
                'purgeable': True,
                'map': {
                    'id': 'id',
                    'gateway_id': 'gateway_id',
                    'user_id': 'user_id',
                    'email': 'email',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'module_device_type': {
                'dbclass': "ModuleDeviceTypes",
                'table': "module_device_types",
                'library': None,
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'module_id': 'module_id',
                    'device_type_id': 'device_type_id',
                    'created_at': 'created_at',
                }
            },

            'gateway_nodes': {
                'dbclass': "Node",
                'table': "nodes",
                'library': None,
                'functions': {
                    # 'enabled': "enable_device",
                    # 'disabled': "disable_device",
                    # 'deleted': "delete_device",
                },
                'purgeable': True,
                'map': {
                    'id': 'id',
                    'parent_id': 'parent_id',
                    'gateway_id': 'gateway_id',
                    'node_type': 'node_type',
                    'weight': 'weight',
                    'label': 'label',
                    'machine_label': 'machine_label',
                    'always_load': 'always_load',
                    'destination': 'destination',
                    'data': 'data',
                    'data_content_type': 'data_content_type',
                    'status': 'status',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'variable_groups': {
                'dbclass': "VariableGroups",
                'table': "variable_groups",
                'library': "configuration",
                'functions': {
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'relation_id': 'group_relation_id',
                    'relation_type': 'group_relation_type',
                    'group_machine_label': 'group_machine_label',
                    'group_label': 'group_label',
                    'group_description': 'group_description',
                    'group_weight': 'group_weight',
                    'status': 'status',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'variable_fields': {
                'dbclass': "VariableFields",
                'table': "variable_fields",
                'library': "configuration",
                'functions': {
                },
                'purgeable': False,
                'map': {
                    'id': 'id',
                    'group_id': 'group_id',
                    'field_machine_label': 'field_machine_label',
                    'field_label': 'field_label',
                    'field_description': 'field_description',
                    'field_weight': 'field_weight',
                    'value_required': 'value_required',
                    'value_max': 'value_max',
                    'value_min': 'value_min',
                    'value_casing': 'value_casing',
                    'encryption': 'encryption',
                    'input_type_id': 'input_type_id',
                    'default_value': 'default_value',
                    'field_help_text': 'field_help_text',
                    'multiple': 'multiple',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

            'variable_data': {
                'dbclass': "VariableData",
                'table': "variable_data",
                'library': "configuration",
                'functions': {
                },
                'purgeable': True,
                'map': {
                    'id': 'id',
                    'gateway_id': 'gateway_id',
                    'field_id': 'field_id',
                    'relation_id': 'data_relation_id',
                    'relation_type': 'data_relation_type',
                    'data': 'data',
                    'data_weight': 'data_weight',
                    'created_at': 'created_at',
                    'updated_at': 'updated_at',
                }
            },

    }

    def __init__(self, amqpyombo):
        """
        Loads various variables and calls :py:meth:connect() when it's ready.

        :return:
        """
        self.parent = amqpyombo
        self.init_startup_count = 0
        self.inital_config_items_requested = 0
        self.init_defer = None  # Prevents loader from moving on until we are done.
        self.__doing_full_configs = False  # will be set to True later when download configurations
        self.__pending_updates = {}  # Holds a dict of configuration items we've asked for, but not response yet.
        self.__process_queue = {}  # Holds a list of configuration items we've asked for, but not response yet.
        self.processing = False
        self.processing_queue = False
        self.db_existing_data = {}  # used to keep track of items to add, update, or delete
        self.db_completed_ids = {}  # [table][row_id]
        self.db_delete_ids = {}  # [table][row_id]
        self.db_insert_data = {}  # [table][row_id] = orderedDicts
        self.db_update_data = {}  # [table][row_id] = Dictionaries

        self._checkProcessQueueLoop = LoopingCall(self.process_config_queue)
        self.check_download_done_calllater = None

        self._LocalDB = self.parent._LocalDB

        self.amqp = None  # holds our pointer for out amqp connection.
        self._getAllConfigsLoggerLoop = None

    def connect_setup(self, init_defer):
        """
        The connection was setup, but not quite ready to ask for configs. Just return a defer.
        :return:
        """
        self.init_defer = init_defer

    def connected(self):
        """

        :return:
        """
        self.get_system_configs()
        self.check_download_done_calllater = reactor.callLater(15, self.check_download_done)
        # return self.init_defer

    def disconnected(self):
        """
        Called by amqpyombo when the system is disconnected.
        :return:
        """
        if self._getAllConfigsLoggerLoop is not None and self._getAllConfigsLoggerLoop.running:
            self._getAllConfigsLoggerLoop.stop()
        if self._checkProcessQueueLoop is not None and self._checkProcessQueueLoop.running:
            self._checkProcessQueueLoop.stop()

        self.__pending_updates.clear()
        self.__doing_full_configs = False

        try:
            self.check_download_done_calllater.cancel()
        except:
            pass

    def _stop_(self):
        """
        Called by the Yombo system when it's time to shutdown. This in turn calls the disconnect.
        :return:
        """
        if self.init_defer.called is False:
            # reactor.callLater(0.1, self.init_defer.callback, 10) #
            self.init_defer.callback(1)  # if we don't check for this, we can't stop!

        if self._getAllConfigsLoggerLoop is not None and self._getAllConfigsLoggerLoop.running:
            self._getAllConfigsLoggerLoop.stop()
        if self._checkProcessQueueLoop is not None and self._checkProcessQueueLoop.running:
            self._checkProcessQueueLoop.stop()
        try:
            self.check_download_done_calllater.cancel()
        except:
            pass


    def check_download_done(self):
        """
        Called after 30 seconds to check if downloads have completed. If they haven't, it will just give up and move on.

        :return:
        """
        if self.__doing_full_configs == True and len(self.__process_queue) == 0:
            last_complete = self.parent._Configs.get("amqpyombo", 'lastcomplete', None, False)
            if last_complete == None:
                if self.init_startup_count > 5:
                    logger.error("Unable to reach or contact server. If problem persists, check your configs. (Help link soon.)")
                    self.reconnect = False
                    reactor.stop()
                    return
                logger.warn("Try #{count}, haven't been able to download configurations. However, there are no existing configs. Will keep trying.",
                            count=self.init_startup_count)
            else:
                if last_complete < int(time() - 60*60*48):
                    logger.warn("Try #{count}, haven't been able to download configurations. Will continue trying in background.",
                            count=self.init_startup_count)
                    logger.warn("Using old configuration information. If this persists, check your configs. (Help link soon.)")
                    if self.init_defer.called is False:
                        self.init_defer.callback(1)  # if we don't check for this, we can't stop!
                else:
                    logger.error("Unable to reach or contact server. Configurations too old to keep using. If problem persists, check your configs. (Help link soon.)")
                    self.reconnect = False
                    reactor.stop()
                    return

            self.init_startup_count = self.init_startup_count + 1
            self.check_download_done_calllater = reactor.callLater(30, self.check_download_done) #


    def process_config_response(self, msg=None, properties=None, **kwargs):
        """
        Process configuration information coming from Yombo Servers. After message is validated, the payload is
        delivered here.

        This is an intermediary method and converts the msg into usable chunks and delievered to "add_update_delete".
        In the future, these may be delievered to the individual libraries for processing.

        :param msg: raw message from AQMP
        :param properties: msg properties, so additional information can be retrieved.
        :return:
        """
        # logger.info("properties: {properties}", properties=properties)
        # logger.info("headers: {headers}", headers=properties.headers)

        if properties.headers['config_item'] not in self.config_items:
            raise YomboWarning("Configuration item '%s' not configured." % properties.headers['config_item'])
        self.__process_queue[random_string(length=10)] = {
            'msg': bytes_to_unicode(msg),
            'headers': properties.headers,
            }
        self.__pending_updates['get_%s' % properties.headers['config_item']]['status'] = 'received'

        self.process_config_queue();

    @inlineCallbacks
    def process_config_queue(self):
        """
        We queue incoming responses for processing. This helps to prevent race conditions as well as
        killing sqlite3 database with a bunch of concurrent requests.

        This is called to feed the process_config function configuration items to process and is called whenever
        we receive a configuration response item as well as a looping call to ensure everything gets processed.
        :return:
        """
        if self.processing:
            return None

        if self.processing_queue == False:
            self.processing_queue = True
            # print("self.__process_queue: %s" % self.__process_queue)
            for key in list(self.__process_queue):
                queue = self.__process_queue[key]
                # print("processing key: %s" % 'get_%s' % queue['headers']['config_item'])
                # if queue['headers']['config_item'] == 'get_gateway_cluster':
                # print("msg: %s" % queue['msg'])
                # print("self.__pending_updates: %s" % self.__pending_updates)
                self.__pending_updates['get_%s' % queue['headers']['config_item']]['status'] = 'processing'
                yield self.process_config(queue['msg'],
                                          queue['headers']['config_item'],
                                          queue['headers']['config_type'],
                                          True)
                del self.__process_queue[key]
            self.processing_queue = False


    @inlineCallbacks
    def process_config(self, msg, config_item, config_type=None, primary_config_item=None):
        """
        Process configuration information coming from Yombo Servers. After message is validated, the payload is
        delivered here.

        This is an intermediary method and converts the msg into usable chunks and delievered to "add_update_delete".
        In the future, these may be delievered to the individual libraries for processing.

        :param msg: raw message from AQMP
        :param properties: msg properties, so additional information can be retrieved.
        :return:
        """
        self.processing = True
        # print("processing config.... %s" % config_item)
        # print("processing msg.... %s" % msg)
        if msg['code'] != 200:
            logger.warn("Configuration for configuration '{type}' received an error ({code}): {error}", type=config_item, code=msg['code'], error=msg['message'])
            yield self._remove_full_download_dueue("get_" + config_item)
            self.processing = False
            return

        if config_item == "gateway_configs":
            payload = msg['data']
            for section in payload:
                for key in section['Values']:
                   self.parent._Configs.set(section['Section'], key['Key'], key['Value'])

        elif config_item == "gateway_dns_name":
            payload = msg['data']
            self.parent._Configs.set('dns', 'dns_name', payload['dns_name'])
            self.parent._Configs.set('dns', 'dns_domain', payload['dns_domain'])
            self.parent._Configs.set('dns', 'dns_domain_id', payload['dns_domain_id'])
            self.parent._Configs.set('dns', 'allow_change_at', payload['allow_change_at'])
            self.parent._Configs.set('dns', 'fqdn', payload['fqdn'])

        elif config_item in self.config_items:
            config_data = self.config_items[config_item]
            # if config_type == 'full':
                # logger.info("Truncating table: {table}", table=config_data['table'])
                # yield self._LocalDB.truncate(config_data['table'])
                # logger.info("Truncating table: {table}..done", table=config_data['table'])

            if msg['data_type'] == 'object':
                # print("field remap start object")
                data = self.field_remap(msg['data'], config_data)
                # print("field remap stop")
#                logger.info("in amqpyombo:process_config ->> config_item: {config_item}", config_item=config_item)
#                logger.info("amqpyombo::process_config - data: {data}", data=data)
#                 print("add_update_delete start object")
                yield self.add_update_delete(msg, data, config_item, config_type, True)
                # print("fadd_update_delete stop object")
                # self._Loader.loadedLibraries['devices'].add_update_delete(new_data)
                self.process_config(data, config_item)
            else:
                # print("add_update_delete start list")
                processed_data = []
                for data in msg['data']:
                    processed_data.append(self.field_remap(data, config_data))
#                    logger.info("in amqpyombo:process_config ->> config_item: {config_item}", config_item=config_item)
#                    logger.info("amqpyombo::process_config - data: {data}", data=data)
                yield self.add_update_delete(msg, processed_data, config_item, config_type, True)
                # print("add_update_delete stop list")
        else:
            logger.warn("ConfigurationUpdate::process_config - '{config_item}' is not a valid configuration item. Skipping.", config_item=config_item)
        yield self._remove_full_download_dueue("get_" + config_item)
        self.processing = False

    def field_remap(self, data, config_data):
        new_data = {}
        table_meta = self._LocalDB.db_model[config_data['table']]
        key = None
        value = None
        try:
            for key, value in data.items(): # we must re-map AMQP names to local names.  Removes ones without a DB column too.
                if key in config_data['map']:
                    # Convert ints and floats.
                    if value is None:
                        pass
                    elif table_meta[config_data['map'][key]]['type'] == "INTEGER":
                        value=int(value)
                    elif table_meta[config_data['map'][key]]['type'] == "REAL":
                        value=float(value)
                    elif table_meta[config_data['map'][key]]['type'] == "BOOLEAN":
                        value = is_true_false(value)
                    if key == 'energy_map':
                        try:
                            new_data[config_data['map'][key]] = json.dumps(value)
                            if isinstance(new_data[config_data['map'][key]], dict) is False:
                                new_data[config_data['map'][key]] = '{"0.0":0,"1.0":0}'
                        except Exception as e:
                            new_data[config_data['map'][key]] = '{"0.0":0,"1.0":0}'
                    else:
                        new_data[config_data['map'][key]] = value

                else:
                    new_data[key] = value
            return new_data
        except Exception as e:
            print("error in field remap.  Last key: %s" % key)
            print("input value: %s" % value)
            print("field remap - config_data =%s" % config_data)
            print("field remap - data =%s" % data)
            print("tablemeta: %s" % table_meta)

            logger.error("--------==(Error: Something bad              )==--------")
            logger.error("--------------------------------------------------------")
            logger.error("{error}", error=sys.exc_info())
            logger.error("---------------==(Traceback)==--------------------------")
            logger.error("{trace}", trace=traceback.print_exc(file=sys.stdout))
            logger.error("--------------------------------------------------------")

    # still in progress function. Need to clean up DB calls.
    # todo: what about updates directly to the library? Just call: config_item = get_config_item('devices')
    @inlineCallbacks
    def add_update_delete(self, msg, data_items, config_item, config_type, from_amqp_incoming=False):
        """
        Adds, updates, or delete various items based on the content of the data item being sent it. It will
        inspect the data and make a determination on what to do. It will also consider the values stored in the
        database for add vs update.

        :param data:
        :param config_item:
        :param from_amqp_incoming:
        :return:
        """
        # print("add_update_delete called...%s" % config_item)
        config_data = self.config_items[config_item]
        current_table = config_data['table']
        required_db_keys = []

        table_cols = self._LocalDB.db_model[current_table]

        if current_table not in self.db_existing_data:
            # print("creating db tracking trackers for: %s" % current_table)
            self.db_existing_data[current_table] = {}
            self.db_insert_data[current_table] = []
            self.db_update_data[current_table] = []
            self.db_completed_ids[current_table] = []
            self.db_delete_ids[current_table] = []

            select_fields = ['id']
            if 'updated_at' in table_cols:
                select_fields.append('updated_at')
            if 'created_at' in table_cols:
                select_fields.append('created_at')
            # print(" selecting table: %s  fields: %s" % (current_table, select_fields))
            records = yield self._LocalDB.select(current_table, ", ".join(select_fields))
            for record in records:
                self.db_existing_data[current_table][record['id']] = record
        # self.db_existing_data = {}  # used to keep track of items to add, update, or delete
        # self.db_delete_ids = {}  # [table][row_id]
        # self.db_insert_data = {}  # [table][row_id] = orderedDicts
        # self.db_update_data = {}  # [table][row_id] = Dictionaries

        for col, col_data in table_cols.items():
            if col_data['notnull'] == 1:
                required_db_keys.append(col)

        if isinstance(data_items, list) is False:
            data_items = (data_items,)
        to_save = deque()

        try:
            for data in data_items:
                filtered_data = {}  # dict of just keys that are allowed in the DB.
                for key, value in data.items():
                    if key in table_cols:
                        filtered_data[key] = data[key]

                if 'status' in filtered_data:
                    if filtered_data['status'] == 2:  # delete any nested items...
                        if config_item == 'gateway_modules':
                            self.item_purged(config_item, filtered_data['id'])
                            if filtered_data['id'] in self.filtered_data['modules']:
                                self.db_delete_ids['modules'].append(filtered_data['id'])
                                self.db_completed_ids['modules'].append(filtered_data['id'])
                            if filtered_data['id'] in self.db_existing_data['module_installed']:
                                self.db_delete_ids['module_installed'].append(filtered_data['id'])
                                self.db_completed_ids['module_installed'].append(filtered_data['id'])
                        elif filtered_data['id'] in self.db_existing_data[current_table]:
                            self.db_delete_ids[current_table].append(filtered_data['id'])
                            self.db_completed_ids[current_table].append(filtered_data['id'])
                        continue

                # check to make sure the record has the required columns.
                if dict_has_key(filtered_data, required_db_keys) is False:
                    logger.warn("{config_item}: Cannot do anything. Must have these keys: {needs}  Only had these keys: {has}",
                                config_item=config_item, needs=required_db_keys, has=filtered_data)
                    self.db_completed_ids[current_table].append(filtered_data['id'])
                    continue

                library = None
                if config_data['library'] is not None:
                    library = self.parent._Loader.loadedLibraries[config_data['library']]

                if config_type == 'full':
                    records = []
                else:
                    records = yield self._LocalDB.get_dbitem_by_id(config_data['dbclass'], filtered_data['id'])

                # handle any nested items here.
                if 'device_types' in data:
                    if len(data['device_types']):
                        newMsg = msg.copy()
                        newMsg['data'] = data['device_types']
                        yield self.process_config(newMsg, 'module_device_type')

                if 'variable_groups' in data:
                    if len(data['variable_groups']):
                        newMsg = msg.copy()
                        newMsg['data'] = data['variable_groups']
                        yield self.process_config(newMsg, 'variable_groups')

                if 'variable_fields' in data:
                    if len(data['variable_fields']):
                        newMsg = msg.copy()
                        newMsg['data'] = data['variable_fields']
                        yield self.process_config(newMsg, 'variable_fields')

                if 'variable_data' in data:
                    if len(data['variable_data']):
                        newMsg = msg.copy()
                        newMsg['data'] = data['variable_data']
                        yield self.process_config(newMsg, 'variable_data')

                # If a new record
                # print("if filtered_data['id'] (%s) not in self.db_existing_data[current_table] (%s) == 0:
                if filtered_data['id'] not in self.db_existing_data[current_table]:
                    if 'status' in filtered_data and filtered_data['status'] == 2: # we don't add deleted items...
                        if config_data['purgeable']:
                            self.item_purged(config_item, filtered_data['id'])
                            continue

                    item_to_insert = OrderedDict()
                    for col, col_info in table_cols.items():
                        if col in filtered_data:
                            item_to_insert[col] = filtered_data[col]
                        else:
                            item_to_insert[col] = None

                    self.db_insert_data[current_table].append(item_to_insert)
                    self.db_completed_ids[current_table].append(filtered_data['id'])
                    if 'added' in config_data['functions']:
                        klass = getattr(library, config_data['functions']['updated_at'])
                        klass(data, True)  # True = the library doesn't need to update the database

                # update records
                else:
                    # if config_item == 'gateway_modules':
                    #     print("new data: %s" % filtered_data)
                    #     print("old data: %s" % self.db_existing_data[current_table][filtered_data['id']])
                    #     print("filtered_data['updated_at']: %s" % filtered_data['updated_at'])
                    if 'updated_at' in filtered_data:
                        # Only update if records says it's newer...
                        if filtered_data['updated_at'] == self.db_existing_data[current_table][filtered_data['id']]['updated_at']:
                            self.db_completed_ids[current_table].append(data['id'])
                            continue
                    elif 'created_at' in filtered_data:
                        if filtered_data['created_at'] == self.db_existing_data[current_table][filtered_data['id']]['created_at']:
                            self.db_completed_ids[current_table].append(data['id'])
                            continue

                    item_to_update = OrderedDict()
                    for col, col_info in table_cols.items():
                        if col in filtered_data:
                            item_to_update[col] = filtered_data[col]
                        else:
                            item_to_update[col] = None

                    # print("updating table: %s" % current_table)
                    self.db_update_data[current_table].append(item_to_update)
                    self.db_completed_ids[current_table].append(filtered_data['id'])
                    # self._LocalDB.dbconfig.update(current_table, filtered_data, where=['id = ?', data['id']] )
                    if 'updated_at' in config_data['functions']:
                        klass = getattr(library, config_data['functions']['added'])
                        klass(filtered_data, True)

            # print("calling insertmany for config_data %s" % to_save)
            # if len(to_save) > 0:
            #     yield self._LocalDB.insert_many(current_table, to_save)
        except Exception as e:
            logger.error("-------==(Error: While saving new config data)==--------")
            logger.error("--------------------------------------------------------")
            logger.error("{error}", error=sys.exc_info())
            logger.error("---------------==(Traceback)==--------------------------")
            logger.error("{trace}", trace=traceback.print_exc(file=sys.stdout))
            logger.error("--------------------------------------------------------")

            logger.warn("Got exception: {e}", e=e)

    def get_config_item(self, library):
        """
        Simple lookup function to get config_item
        :param library:
        :return:
        """
        return self.config_item_map[library]

    def get_system_configs(self):
        """
        On startup, this is called to request all configuration items.

        TODO: After heavy development cycle is done, we check will be placed here to determine if the gateway
        can reach the servers or not. It it's not possible, and we some configuration data that isn't too old,
        we will can start without talking to the servers.

        :return:
        """
        self.__doing_full_configs = True
        self._full_download_start_at = time()
        self._getAllConfigsLoggerLoop = LoopingCall(self._show_pending_configs)
        self._getAllConfigsLoggerLoop.start(3, False)  # Display a log line for pending downloaded, false - Dont' show now
        self._checkProcessQueueLoop.start(0.5, False)

        logger.info("Requesting system configurations from server. This can take a few seconds.")

        allCommands = [
            "get_categories",
            "get_gateway_commands",
            "get_gateway_devices", # Includes device variable groups/fields/data
            "get_gateway_locations", # Includes device variable groups/fields/data
            "get_gateway_device_types",
            "get_gateway_modules", # Includes module variable groups/fields/data

            "get_gateway_device_type_commands",
            "get_gateway_device_command_inputs",
            "get_gateway_input_types",
            "get_gateway_users",
            "get_gateway_dns_name",
            "get_gateway_cluster",

            "get_gateway_nodes",  # Includes module variable groups/fields/data

            # "get_gateway_input_types",
            # "get_gateway_configs",

#            "GetModuleVariables",
#            "getGatewayUserTokens",
#            "getGatewayUsers",
        ]
        self.inital_config_items_requested = len(allCommands)
        cur_time = int(time())
        for item in allCommands:
            logger.debug("sending command: {item}", item=item)

           # request device updates
            body = {
                "since": self.parent._Configs.get("amqpyombo_config_times", item, 0),
            }

            self.parent._Configs.set("amqpyombo_config_times", item, cur_time),

            headers= {
                "request_type": "config",
                "config_item"  : item,
            }
            request = self.generate_config_request(headers, body)

            self.parent.publish(**request)
            self._append_full_download_queue(item)

    def item_purged(self, config_item, id):
        # request device updates
        body = {
            "id": id
        }

        headers = {
            "request_type": "config",
            "config_item": 'purged_' + config_item,
        }

        request_msg = self.parent.generate_message_request('ysrv.e.gw_config', 'yombo.gateway.lib.amqpyobo',
                                                           "yombo.server.configs", headers, body)
        request_msg['correlation_persistent'] = False
        self.parent.publish(**request_msg)

    def generate_config_request(self, headers, request_data=""):
        """
        Generate a request specific to this library - configs!

        :param headers:
        :param request_data:
        :return:
        """
        request_msg = self.parent.generate_message_request('ysrv.e.gw_config', 'yombo.gateway.lib.amqpyobo',
                                                    "yombo.server.configs", headers, request_data)
        # logger.debug("response: {request_msg}", request_msg=request_msg)
        request_msg['correlation_persistent'] = False
        return request_msg

    def _append_full_download_queue(self, table):
        """
        Adds an item to pending table queue.

        Will be removed as each config item is returned by _removeFullTableQueue.
        """
        if table not in self.__pending_updates:
            logger.debug("Adding table to request queue: {table}", table=table)
            self.__pending_updates[table] = {
                'status': 'requested',
                'request_at': time(),
            }

    @inlineCallbacks
    def _remove_full_download_dueue(self, table):
        # logger.info("Removing table from request queue: {table}", table=table)
        # logger.info("Configs pending: {pendingUpdates}", pendingUpdates=self.__pending_updates)
        if table in self.__pending_updates:
            del self.__pending_updates[table]
        else:
            return
        # logger.debug("Configs pending: {pendingUpdates}", pendingUpdates=self.__pending_updates)
        self.init_startup_count = 0
        if len(self.__pending_updates) == 0 and self.__doing_full_configs is True:
            self.__doing_full_configs = False
            self._getAllConfigsLoggerLoop.stop()
            self._checkProcessQueueLoop.stop()

            # now we do all actual database updates, deletes, inserts...
            # self.db_existing_data = {}  # used to keep track of items to add, update, or delete
            # self.db_delete_ids = {}  # [table][row_id]
            # self.db_insert_data = {}  # [table][row_id] = orderedDicts
            # self.db_update_data = {}  # [table][row_id] = Dictionaries

            for table, records in self.db_delete_ids.items():
                for completed_id in self.db_completed_ids[table]:  # delete items that were not sent to us.
                    if completed_id in self.db_existing_data[table]:
                        del self.db_existing_data[table][completed_id]
                for existing_id in list(self.db_existing_data[table].keys()):
                    print("Left over items: should be deleted.... %s: %s" % (table, existing_id))
                    records.append(existing_id)
                if len(records) > 0:
                    print("%s should be delete_many these records: %s" % (table, records))
                    yield self._LocalDB.delete_many(table, records)
            self.db_existing_data = {}

            for table, records in self.db_update_data.items():
                if len(records) > 0:
                    # print("%s should be update_many records: %s" % (table, records))
                    yield self._LocalDB.update_many(table, records, 'id')
            self.db_update_data = {}

            for table, records in self.db_insert_data.items():
                if len(records) > 0:
                    # print("%s should be insert_many these records: %s" % (table, records))
                    yield self._LocalDB.insert_many(table, records)
            self.db_update_data = {}

            reactor.callLater(0.1, self.done_with_startup_downloads) # give DB some breathing room
        else:
            if self._getAllConfigsLoggerLoop is not None and self._getAllConfigsLoggerLoop.running:
                self._getAllConfigsLoggerLoop.reset()

            if self.check_download_done_calllater is not None and self.check_download_done_calllater.active():
                self.check_download_done_calllater.reset(30)
            else:
                self.check_download_done_calllater = reactor.callLater(30, self.check_download_done)  #

    def done_with_startup_downloads(self):
        """
        Called when configuration downloads are complete.
        :return:
        """
        self.parent._Configs.set("amqpyombo", 'lastcomplete', int(time()))
        if self.init_defer.called is False:
            self.init_defer.callback(1)  # if we don't check for this, we can't stop!
            # self.parent._Notifications.add(
            #     {'title': 'Configs Downloaded', 'message': 'Downloaded system configurations from Yombo server.',
            #      'timeout': 300, 'source': 'Yombo Gateway System'})


    def _show_pending_configs(self):
        waitingTime = time() - self._full_download_start_at
        logger.debug("Waited {waitingTime} for startup; pending these configurations:", waitingTime=waitingTime)
        count_pending = 0
        currently_processing = ''
        display_waiting_on = []
        for key in list(self.__pending_updates):
            count_pending += 1
            logger.debug("Config: {config}, Status: {status}", config=key,  status=self.__pending_updates[key]['status'])
            if self.__pending_updates[key]['status'] == 'processing':
                currently_processing = key
                self.check_download_done_calllater.reset(30)
            display_waiting_on.append(key)

        if currently_processing == '':
            logger.info("Waiting for the following items from server: {the_list}", the_list=", ".join(display_waiting_on))
        else:
            logger.info("Processing configuration, {count_pending} of {numer_requested}. Currently processing: {currently_processing}", currently_processing=currently_processing,  count_pending=self.inital_config_items_requested-count_pending, numer_requested=self.inital_config_items_requested)

    def _local_log(self, level, location, msg=""):
        logit = func = getattr(logger, level)
        logit("In {location} : {msg}", location=location, msg=msg)

