"""
Statistics allow the gateway to trace various data points. This can be used to track how much time of a day the
sun is up, or average temperatures, number of commands sent, etc.  Statistics can be used in conjunction with
or as a replacement for device status history. Sometimes it's easier to trace device status here so you can get
averages or a specific datapoint for a device.

.. warning::

  All data values must be an int or decimal (float). This is because data here should be chartable. Devices that
  are on/off or open/closed, can be 1/0.

There are three types of statistics:

  1) Counter - Used to track the number of events.
  2) Averages - Keep adding data points to this, and it will be be averaged along with 90 percentile stats.
  3) Datapoint - Just a simple data point. Not used much.

Any library or module can create statistics, however, a good name for the statistic must be created. A statistic is
named with a dot notation.  For example: module.mycoolmodule.commands.sent and module.mycoolmodule.commands.sent
This allows filtering like this: module.mycoolmodule.commands.* to see all the commands your module processed.

Some addtional examples:

  * lib.configuration.cache.hits
  * lib.configuration.cache.misses
  * lib.messages.count.status
  * lib.messages.count.command
  * lib.amqp.count.sent
  * lib.amqp.count.received
  * system.memory.used
  * system.memory.free
  * system.cpu.used
  * system.cpu.free
  * system.storage.disk1.used
  * system.storage.disk1.free

Here are
some guidelines:

  1) The first section should be either lib or module.
  2) The second section should be the name of the library or module.
  3) The third-eigth sections should be named from a top-down order (like the example above).

Naming standards:

  1) Devices should start with device: device.devicename(or)deviceid.energyused
  2) State should start with state: state.sun.visable = 1
  3) Atoms should start with atom: atom.cpu.count (kind of useless info, but you get the idea)
  4) System type data (disk drive size, cpu, ram, etc, should start with system.
     Eg: system.memory.used, system.memory.free, system.storage.dropbox.used
  5) Things like your house environment is up to you within your module.  For example:
     house.downstairs.livingroom.temperature, house.refrigerator.temperature, house.refrigerator.open,
     house.upstairs.kidsbedroom.temperature, house.upstairs.kidsbedroom.occupied

In the house examples, you can get an average of all temperatures with a result set filter of "house.*.*.temperature",
or "house.upstairs.*.temperature"

*Usage**:

.. code-block:: python

   self._Statistics.increment("module.mymodule.requests.sent")
   self._Statistics.increment("module.mymodule.requests.received")
   self._Statistics.averages("house.upstairs.den.temperature", data['den'])
   self._Statistics.datapoint("house.upstairs.den.occupied", occupied_sensor['den'])

.. versionadded:: 0.11.0
.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>

:copyright: Copyright 2015-2016 by Yombo.
:license: LICENSE for details.
"""
# Import python libraries
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re

# Import twisted libraries
from twisted.internet.task import LoopingCall
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

# Import Yombo libraries
from yombo.core.exceptions import YomboWarning
from yombo.core.library import YomboLibrary
from yombo.utils import percentile, global_invoke_all
from yombo.core.log import get_logger

logger = get_logger('library.statistics')


class Statistics(YomboLibrary):
    """
    Library to process all the statics.
    """
    enabled = True  # set to tru to start, will be updated when configurations is loaded.
    count_bucket_duration = 5
    averages_bucket_duration = 5
    _counters = {}  # stores counter information before it's saved to database
    _averages = {}  # stores averages type information
    _datapoints = {}  # stores datapoint data

    def _init_(self, loader):
        """
        Brings the library module online. Responsible for setting up framework for storing statistics.
        :param loader: Loader library.
        :return:
        """
        self.loader = loader
        self.enabled = self._Configs.get('statistics', 'enabled', True)
        self.enabled = self._Configs.get('statistics', 'upload', True)
        self.enabled = self._Configs.get('statistics', 'anonymous', True)

        if self.enabled is not True:
            return

        self.gwuuid = self._Configs.get("core", "gwuuid")

        # defines bucket time span, default is 5 minutes for all buckets
        self.count_bucket_duration = self._Configs.get('statistics', 'count_bucket_duration', 5)  # 5 minutes for count buckets
        self.averages_bucket_duration = self._Configs.get('statistics', 'averages_bucket_duration', 5)  # 5 minutes for averages buckets

        # defines how long to keep things. All values in days! 0 - forever
        self.count_bucket_life_full = self._Configs.get('statistics', 'count_bucket_life_full', 30, False)
        self.count_bucket_life_hourly = self._Configs.get('statistics', 'count_bucket_life_hourly', 120, False)
        self.count_bucket_life_daily = self._Configs.get('statistics', 'count_bucket_life_daily', 0, False)
        self.averages_bucket_life_full = self._Configs.get('statistics', 'averages_bucket_life_full', 30, False)
        self.averages_bucket_life_hourly = self._Configs.get('statistics', 'averages_bucket_life_hourly', 120, False)
        self.averages_bucket_life_daily = self._Configs.get('statistics', 'averages_bucket_life_daily', 0, False)
        self.datapoint_bucket_life_full = self._Configs.get('statistics', 'datapoint_bucket_life_full', 30, False)
        self.datapoint_bucket_life_hourly = self._Configs.get('statistics', 'datapoint_bucket_life_hourly', 120, False)
        self.datapoint_bucket_life_daily = self._Configs.get('statistics', 'datapoint_bucket_life_daily', 0, False)

        self.bucket_lifetimes = {}  # caches meta life duration. Might get set many times, no need to hammer database

        self.time_between_saves = self._Configs.get('statistics', 'time_between_saves', 1800 )  # 30 mins
        self.sendDataLoop = LoopingCall(self._save_statistics)
        self.sendDataLoop.start(self.time_between_saves, False)

        self.unload_defer = None

    def _stop_(self):
        """
        Saves statistics data to database.
        :return:
        """
        # self._save_statistics(True)
        # return
        if self.enabled is True:
            self.unload_defer = Deferred()
            self.unload_defer.callback(10)
            self.unload_defer.addCallback(lambda ignored: self._save_statistics(True))
            self.unload_defer.addErrback(self.unload_errback)
            return self.unload_defer

    def unload_errback(self, reason):
        logger.warn("Error unloading statistics: {reason}", reason=reason)


    def _module_prestart_(self, **kwargs):
        """
        This function is called before the _start_ function of all modules is called. This in turn calls the
        hook_statistics_lifetimes hook to get lifetime information about statistics.

        This allows libraries and modules to limit the lifetime of statistics. It expects a dictionary in return:
        return {'name': 'lib.amqpyombo.amqp.#',
                'lifetimes': [15, 30, 365],
               }

        The name is the filter to apply. A * can replace one section of the name, while a # will grab any name
        segments after it.

        See :py:mod:`Atoms Library <yombo.lib.automationhelpers>` for demo. All other modules are defined here...
        """
        # first, set some generic defaults. The filter matcher when processing will always use the most specific.
        self.bucket_lifetimes_default = [30, 90, 365]

        self.add_bucket_lifetime('lib.#', [10, 30, 365])
        self.add_bucket_lifetime('lib.amqpyombo.amqp.#', [5, 15, 90])  # don't really care about this! If you do, just override with same value.
        self.add_bucket_lifetime('core.#', [10, 30, 365])
        self.add_bucket_lifetime('modules.#', [10, 30, 365])

        stat_lifetimes = global_invoke_all('statistics_lifetimes')
#        print "################## %s " % automation_sources
#        logger.debug("message: automation_sources: {automation_sources}", automation_sources=automation_sources)
        for moduleName, item in stat_lifetimes.iteritems():
            if isinstance(item, dict):
                    self.add_bucket_lifetime(item['name'], item['lifetimes'])

#        print 'lifetimes: %s' % self.bucket_lifetimes

    def _get_bucket_time(self, type, bucket_time=None):
        """
        Internal function to get time for a given bucket type.

        :param type: Either count, averages, or datapoint.
        :return: A unix epoch time for a bucket.
        """
        if bucket_time is not None:
            if 60 % bucket_time != 0:
                raise YomboWarning("bucket_time must be divisible by 60.")
            bucket_minutes = bucket_time
        else:
            if type == "count":
                bucket_minutes = self.count_bucket_duration
            elif type == "averages":
                bucket_minutes = self.averages_bucket_duration
            elif type == "datapoint":
                return int(datetime.now().strftime('%s'))
            else:
                raise YomboWarning('Invalid _get_bucket_time type: %s' % type)

        now = datetime.now()
        bucket = now - timedelta(minutes = now.minute % bucket_minutes, seconds = now.second, microseconds = now.microsecond )
        return int(bucket.strftime('%s'))

    def _validate_name(self, name):
        """
        Validates the name being submitted is valid. No point in sending badly named
        items to the server, as the server will simply perform this same check and
        discard any invalid ones.

        .. note::

            If the server detects too many invalid names, the gateway will be blocked from
            saving statistics in the future.

        :param name: Label for the statistic
        :type name: string
        """
        parts = name.split('.', 10)
        if len(parts) < 3:
            raise YomboWarning("Name must have at least 3 parts, preferably at least 4.")
        elif len(parts) > 8:
            raise YomboWarning("Name has too many parts, no more than 8.")

        for count in range(0, len(parts)):
            if len(parts[count]) < 3:
                raise YomboWarning("'%s' is too short, must be at least 3 characters: " % parts[count])

    def add_bucket_lifetime(self, name, lifetimes):
        """

        :param name: name of bucket
        :param lifetimes: list - [full, hourly, daily]
        :return:
        """
        if isinstance(lifetimes, list) is False or len(lifetimes) != 3:
            raise YomboWarning("Bucket lifetimes must be a list of life int values.")
        for item in lifetimes:
            if isinstance(item, int) is False:
                raise YomboWarning("Bucket lifetimes must be a list of life int values.")
        self.bucket_lifetimes[name] = {'life': lifetimes}

    def datapoint(self, name, value, anon=False, lifetimes=None):
        """
        Set a datapoint numberic value. For example, set the amount of memory used every so often.

        .. code-block:: python

           self._Statistics.datapoint("house.upstairs.den.occupied", occupied_sensor['den'])

        :param name: Name of the statistic to save.
        :type name: string
        :param value: A numbered value to set.
        :type value: int
        :param bucket_time: How many minutes the bucket should be. Must be divisable by 60.
        :type value: bool
        :param anon: If anonymous type data, set to True, default is False
        :type value: bool
        """
        if self.enabled is not True:
            return

        self._validate_name(name)
        #bucket = datetime.datetime.now().strftime('%s')
        bucket = self._get_bucket_time('datapoint')
        if bucket not in self._datapoints:
            self._datapoints[bucket] = {}
        if name not in self._datapoints:
            self._datapoints[bucket][name] = {}
        self._datapoints[bucket][name]['value'] = value
        self._datapoints[bucket][name]['anon'] = anon
        if lifetimes is not None:
            self.add_bucket_lifetime(name, lifetimes)

    def count(self, name, value, bucket_time=None, anon=False, lifetimes=None):
        """
        Set a count value. Typically, this isn't used, instead use ``increment`` or ``decrement`` due to
        bucket time rollover.

        :param name: Name of the statistic to save.
        :type name: string
        :param value: A numbered value to set.
        :type value: int
        :param bucket_time: How many minutes the bucket should be. Must be divisable by 60.
        :type value: bool
        :param anon: If anonymous type data, set to True, default is False
        :type value: bool
        """
        if self.enabled is not True:
            return

        self._validate_name(name)

        bucket = self._get_bucket_time('count', bucket_time)

        if bucket not in self._counters:
            self._counters[bucket] = {}
        self._counters[bucket][name]['value'] = value
        self._counters[bucket][name]['anon'] = anon
        if lifetimes is not None:
            self.add_bucket_lifetime(name, lifetimes)

    def increment(self, name, count=1, bucket_time=None, anon=False, lifetimes=None):
        """
        Increment a counter value. If doesn't exist, will create the new counter for the given name.

        .. code-block:: python
        
           self._Statistics.increment("module.mymodule.requests.sent")

        :param name: Name of the statistic to save.
        :type name: string
        :param count: How many to increment by, defaults to 1.
        :type count: int
        :param bucket_time: How many minutes the bucket should be. Must be divisable by 60.
        :type value: bool
        :param anon: If anonymous type data, set to True, default is False
        :type value: bool
        """
        if self.enabled is not True:
            return
        self._validate_name(name)

        bucket = self._get_bucket_time('count', bucket_time)

        if bucket not in self._counters:
            self._counters[bucket] = {}

        if name not in self._counters[bucket]:
                self._counters[bucket][name] = {}
                self._counters[bucket][name]['value'] = count
                self._counters[bucket][name]['anon'] = anon
        else:
                self._counters[bucket][name]['value'] += count
                self._counters[bucket][name]['anon'] = anon

        if lifetimes is not None:
            self.add_bucket_lifetime(name, lifetimes)


    def decrement(self, name, count=1, bucket_time=None, anon=False, lifetimes=None):
        """
        Decrement a counter value. If doesn't exist, will create the new counter for the given name.

        .. code-block:: python
        
           self._Statistics.decrement("module.mymodule.requests.sent")

        :param name: Name of the statistic to save.
        :type name: string
        :param count: How many to increment by, defaults to -1.
        :type count: int
        :param bucket_time: How many minutes the bucket should be. Must be divisable by 60.
        :type value: bool
        :param anon: If anonymous type data, set to True, default is False
        :type value: bool
        """
        if self.enabled is not True:
            return

        self._validate_name(name)

        bucket = self._get_bucket_time('count', bucket_time)

        if bucket not in self._counters:
            self._counters[bucket] = {}

        if name not in self._counters[bucket]:
                self._counters[bucket][name] = {}
                self._counters[bucket][name]['value'] = -count
                self._counters[bucket][name]['anon'] = anon
        else:
                self._counters[bucket][name]['value'] -= count
                self._counters[bucket][name]['anon'] = anon

        if lifetimes is not None:
            self.add_bucket_lifetime(name, lifetimes)

    def averages(self, name, value, bucket_time=None, anon=False, lifetimes=None):
        """
        Set a time on how long something took to complete in milliseconds. A single timer can be set many times, but
        it will be averaged per bucket.

        .. code-block:: python
        
           self._Statistics.averages("house.upstairs.den.temperature", data['den'])

        :param name: Name of the statistic to save.
        :type name: string
        :param value: How long something took in milliseconds.
        :type value: int
        :param bucket_time: How many minutes the bucket should be. Must be divisable by 60.
        :type value: bool
        :param anon: If anonymous type data, set to True, default is False
        :type value: bool
        """
        if self.enabled is not True:
            return

        self._validate_name(name)

        bucket = self._get_bucket_time('averages', bucket_time)

        if bucket not in self._averages:
            self._averages[bucket] = {}

        if name not in self._averages[bucket]:
            self._averages[bucket][name] = []
        self._averages[bucket][name].append({'value': value, 'anon': anon})

        if lifetimes is not None:
            self.add_bucket_lifetime(name, lifetimes)

    @inlineCallbacks
    def _save_statistics(self, full=False):
        """
        Internal function to save the statistics information to database. This is performed regularly while the gateway
        is running and during shutdown. For perfomance reasons, it's not saved instantly.
        """
        if self.enabled is not True:
            return

        current_count_bucket = self._get_bucket_time('count')
        current_averages_bucket = self._get_bucket_time('averages')
        current_datapoint_bucket = self._get_bucket_time('count')

        for bucket in self._counters.keys():
            if full or bucket < (current_count_bucket):
                for name in self._counters[bucket].keys():
                    yield self._Libraries['localdb'].save_statistic(bucket, "counter", name,
                                                                    self._counters[bucket][name]['value'],
                                                                    self._counters[bucket][name]['anon'])
            if full:                    
                del self._counters[bucket]

        for bucket in self._averages.keys():
            if full or bucket < (current_averages_bucket):
                for name in self._averages[bucket].keys():
#                    print "name: %s" % name
                    # save_data.append({'type': 'count', 'name': name, 'value': self._averages[bucket][name]})

                    values = []
#                    print "_averages: %s" % self._averages[bucket][name]
                    for item in self._averages[bucket][name]:
                        values.append(item['value'])
                        anon = item['anon']
#                    print "values: %s" % values
                    sorted_values = sorted(values)

                    median = percentile(list(sorted_values), 0.50)
                    percentile90 = percentile(sorted_values, 0.90)
                    values_90 = []

                    for val in sorted_values:
                        if val <= percentile90:
                            values_90.append(val)
                        else:
                            break
                    median_90 = percentile(values_90, 0.50)

                    # print "sorted_values: %s" % sorted_values
                    # print "valpercentile90es_90: %s" % percentile90
                    # print "values_90: %s" % values_90
                    average_data = {
                        'count': len(sorted_values),
                        'median': median,
                        'upper': sorted_values[-1],
                        'lower': sorted_values[0],
                        'upper_90': values_90[0],
                        'lower_90': values_90[-1],
                        'median_90': median_90,
                    }
#                    print "average data: %s" % average_data
                    yield self._Libraries['localdb'].save_statistic(bucket, "average", name, median_90, anon, average_data)
            if full:                    
                del self._averages[bucket]
            else:
                self._upload_statistics()

        for bucket in self._datapoints.keys():
            if full or bucket < (current_datapoint_bucket):
#                print "buck datapoints: %s" % self._datapoints[bucket]
                for name in self._datapoints[bucket].keys():
                    yield self._Libraries['localdb'].save_statistic(bucket, "datapoint", name,
                                                                    self._datapoints[bucket][name]['value'],
                                                                    self._datapoints[bucket][name]['anon'])
    
            if full:                    
                del self._datapoints[bucket]
                self.consolidate_db()  # for testing

    @inlineCallbacks
    def consolidate_db(self):
        """
        CPU intensive function consolidates statistic information.

        NOT COMPLETE. Just geting started.

        Steps:
        1) Generate full list of names (ask sql for unique).
        2) Match list of names with filters.
        3) Ask SQL for names with date ranges as defined in filter+lifetime  *continue from here*
        4) Add all the data up.
        5) Remove date range of data from SQL
        6) Add new consolidated data back to SQL.
        :return:
        """

        #        1) Generate full list of names.
        records = yield self._Libraries['localdb'].get_distinct_stat_names()

        names = {}
        for record in records:
            names[record['name']] = {'bucket_min':record['bucket_min'],'bucket_max':record['bucket_min']}

        #       2) Match list of names with filters.
        def make_regex(bucket_lifetimes):
            thelist = {}
            for filter, data in bucket_lifetimes.iteritems():
                thelist[filter] = re.compile(filter.replace('#', '.*').replace('$', '\$').replace('+', '[/\$\s\w\d]+'))
            return thelist

        def select_closest( the_list, search_for):  # semi-reusing fuzzydict..
            stringDiffLib = SequenceMatcher()
            stringDiffLib.set_seq1(search_for.lower())
            # examine each key in the dict
            best_ratio = 0
            best_match = None
            for key in the_list:
                # key must be a string, otherwise it is skipped!
                try:
                    stringDiffLib.set_seq2(key.lower())
                except TypeError:
                    continue                # might get here, even though it's not a string. Catch it!
                try:
                    # get the match ratio
                    curRatio = stringDiffLib.ratio()
                except TypeError:
                    break
                # if this is the best ratio so far - save it and the value
                if curRatio > best_ratio:
                    best_ratio = curRatio
                    best_match = key
            return best_match

        regexs = make_regex(self.bucket_lifetimes)

        # get all possible matching filters
        for name, name_info in names.iteritems():
          for filter, regex in regexs.iteritems():
            result = regex.match(name)
            if result is not None:
              if 'filters' not in names[name]:
                  names[name] = {'filters': []}
              names[name]['filters'].append(filter)

        # now lets strip this down
        for name, data in names.iteritems():
            if 'filters' in data:
                filter = select_closest(data['filters'], name)
                del names[name]['filters']
                names[name]['life'] = self.bucket_lifetimes[filter]['life']
            else:
                names[name]['life'] = [0, 0, 0]

        print names
#{'home.kitchen.bar': {'life': [1, 3, 5]}, 'home.office.light': {'life': [2, 4, 6]}, 'home.den.light': {'life': [2, 4, 6]}}


        #        3) Ask SQL for names with date ranges as defined in filter+lifetime  *continue from here*


    def _upload_statistics(self):
        """
        Internal function to upload statistics to Yombo based on system settings. This is called periodically
        to check if any statistics need to be uploaded, usually after a save event occcurs.
        
        Not implemented yet.
        :return: 
        """
        pass
    #             amqpBody.append({"name":name + ".count", "value"  : count, "timestamp": key})
    #             amqpBody.append({"name":name + ".median", "value" : median, "timestamp": key})
    #             amqpBody.append({"name":name + ".upper", "value"  : max, "timestamp": key})
    #             amqpBody.append({"name":name + ".lower", "value"  : min, "timestamp": key})
    #             amqpBody.append({"name":name + ".upper_90", "value"  : temp[-1], "timestamp": key})
    #             amqpBody.append({"name":name + ".lower_90", "value"  : temp[0], "timestamp": key})
    #             amqpBody.append({"name":name + ".median_90", "value" : median_90, "timestamp": key})
    #
    #     for time in bucketsSent:
    #         del self._averages[time]
    #
    #     for key, items in self._datapoints:
    #         for name, value in items:
    #             amqpBody.append({"name":name, "value" : value , "timestamp": key})
    #
    #     #TODO: Send to AMQP library for actual sending.
    #     request = {
    #           "DataType": "Objects",
    #           "Request": amqpBody,
    #         }
    #
    #     logger.info("Request (senddata): {request}", request=request)
    #
    #     requestmsg = {
    #         "exchange_name"    : "ysrv.e.gw_stats",
    #         "routing_key"      : '*',
    #         "body"             : request,
    #         "properties" : {
    #             "correlation_id" : random_string(length=12),
    #             "user_id"        : self.gwuuid,
    #             "headers"        : {
    #                 "Source"        : "yombo.gateway.lib.statistics:" + self.gwuuid,
    #                 "Destination"   : "yombo.server.configs",
    #                 "Type"          : "Stats",
    #                 },
    #             },
    #         "callback"          : None,
    #         }
    #
    #     return requestmsg
