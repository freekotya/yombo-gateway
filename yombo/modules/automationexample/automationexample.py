"""
A simple module to test and demonstrate various automation hooks.

This module also creates a few rules for demonstration.

:copyright: 2016 Yombo
:license: MIT
"""
import time
from twisted.internet import reactor

from yombo.core.log import get_logger
from yombo.core.module import YomboModule

logger = get_logger("modules.automationexample")


class AutomationExample(YomboModule):
    """
    This module adds a couple rules and toggles
    """
    def _init_(self, **kwargs):
        logger.info("Output from translation: {out}", out=_('automationexample','demo.automationexample')) # demo of using i18n...

    def _load_(self, **kwargs):
        # in 3 seconds from now, change the state - test the trigger
        self._States['demo.automationexample'] = 1
        reactor.callLater(3, self.set_low)
        # pass

    def _automation_rules_list_(self, **kwargs):
        """
        Implements hook _automation_rules_list_ hook as implemented by the library automation. This defines a few
        example rules. Notice the reference to 'component_function'. This the function that is called when the
        rule fires. Notice that the function name can be reference by name as if it were implemented by a text file,
        or a reference to the function be submitted. Passing a reference to a function provides higher assurance the
        proper function is called and should be used when creating rules within a module.

        :return: Returns a dictionary of rules to be parsed.
        :rtype: dict
        """
        return
        return{'rules': [
            {
                'name': 'Empty test 0',
                'trigger': {
                    'source': {
                        'platform': 'states',
                        'name': 'demo.automationexample',
                    },
                    'filter': {
                        'platform': 'basic_values',
                        'value': 0
                    }
                },
                # 'condition': [
                #     {
                #     'source': {
                #         'platform': 'atoms',
                #         'name': 'kernel',
                #         },
                #     'filter': {
                #         'platform': 'basic_values',
                #         'value': 'Linux'
                #         }
                #     },
                #     {
                #     'source': {
                #         'platform': 'states',
                #         'name': 'is.light',
                #         },
                #     'filter': {
                #         'platform': 'basic_values',
                #         'value': 'false'
                #         }
                #     },
                # ],
                'action': [
                    {
                        'platform': 'call_function',
                        'component_type': 'module',
                        'component_name': 'AutomationExample',
                        'component_function': 'call_when_low',
                        'delay': '10s',
                        'arguments': {
                            'argument1': 'somevalue'
                        }
                    },
                    # {
                    #     'platform': 'devices',
                    #     'device': 'hv out 1',
                    #     'command': 'open',
                    #     'arguments': {
                    #         'delay': '10',
                    #     }
                    # },
                    {
                        'platform': 'states',
                        'name': 'is.day',
                        'value': False
                    }
                ]
            },
            {
                'name': 'Empty test 1',
                'trigger': {
                    'source': {
                        'platform': 'states',
                        'name': 'demo.automationexample',
                    },
                    'filter': {
                        'platform': 'basic_values',
                        'value': 1
                    }
                },
                'action': [
                    {
                        'platform': 'call_function',
                        'component_callback': self.call_when_high,
                        'delay': 10,
                        'arguments': {
                            'argument1': 'somevalue'
                        }
                    },
                    # {
                    #     'platform': 'states',
                    #     'device': 'hv out 1',
                    #     'command': 'close',
                    #     'arguments': {
                    #         'delay': '10',
                    #     }
                    # }
                    {
                        'platform': 'states',
                        'name': 'is.day',
                        'value': True
                    }
                ],
            },
            # {
            #     'name': 'AutomationExample',
            #     'description': 'Test rule created in AutomationExample module',
            #     'trigger': {
            #         'source': {



            #             'platform': 'devices',
            #             'device': 'hv out 1',
            #         },
            #         'filter': {
            #             'platform': 'basic_values',
            #             'value': 1
            #         }
            #     },
            #     'action': [
            #         {
            #             'platform': 'call_function',
            #             'component_callback': self.call_when_high,
            #             'arguments': {
            #                 'command': 'off'
            #             }
            #         }
            #     ]
            # }
            ]
        }
        
    # def _start_(self, **kwargs):
        # logger.info("States: Is Light: {times_light}", times_light=self._States['is.light'])
        # logger.info("Atoms: Kernel: {kernel}", kernel=self._Atoms['kernel'])
        # self._States['demo.automationexample'] = 1

    def set_high(self):
        logger.info("in set_high - setting automationexample = 1")
        self._States['demo.automationexample'] = 1

    def set_low(self):
        logger.info("in set_low - setting automationexample = 0")
        self._States['demo.automationexample'] = 0

    def call_when_high(self, **kwargs):
        logger.info("it's now high! {kwargs}", kwargs=kwargs)
        self.set_low()

    def call_when_low(self, **kwargs):
        logger.info("it's now low! {kwargs}", kwargs=kwargs)
        self.set_high()
        #reactor.callLater(5, self.set_high)

    def _stop_(self, **kwargs):
        pass
    
    def _unload_(self, **kwargs):
        pass
