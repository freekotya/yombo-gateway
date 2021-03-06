#This file was created by Yombo for use with Yombo Python gateway automation
#software.  Details can be found at http://yombo.net
"""

.. note::

  For more information see: `YomboAPI @ Module Development <https://docs.yombo.net/Libraries/YomboAPI>`_


Manages interactions with api.yombo.net

.. moduleauthor:: Mitch Schwenk <mitch-gw@yombo.net>
.. versionadded:: 0.11.0

:copyright: Copyright 2016 by Yombo.
:license: LICENSE for details.
:view-source: `View Source Code <https://docs.yombo.net/gateway/html/current/_modules/yombo/lib/yomboapi.html>`_
"""
# Import python libraries
import msgpack
from hashlib import sha1
import treq

try: import simplejson as json
except ImportError: import json

# Import twisted libraries
from twisted.internet.defer import inlineCallbacks, Deferred, returnValue
from twisted.web.client import Agent
from twisted.internet import reactor

# Import Yombo libraries
from yombo.ext.expiringdict import ExpiringDict
from yombo.core.exceptions import YomboWarning, YomboWarningCredentails
from yombo.core.library import YomboLibrary
from yombo.core.log import get_logger
from yombo.utils import bytes_to_unicode, unicode_to_bytes

logger = get_logger('library.yomboapi')

class YomboAPI(YomboLibrary):

    # contentType = None

    def _init_(self, **kwargs):
        self.custom_agent = Agent(reactor, connectTimeout=20)
        self.contentType = self._Configs.get('yomboapi', 'contenttype', 'application/json', False)  # TODO: Msgpack later
        self.base_url = self._Configs.get('yomboapi', 'baseurl', "https://api.yombo.net/api", False)
        self.allow_system_session = self._Configs.get('yomboapi', 'allow_system_session', True)
        self.init_defer = None

        self.api_key = self._Configs.get('yomboapi', 'api_key', 'aBMKp5QcQoW43ipauw88R0PT2AohcE', False)
        self.valid_system_session = None
        self.valid_login_key = None
        self.session_validation_cache = ExpiringDict()

        try:
            self.system_session = self._Configs.get('yomboapi', 'auth_session')  # to be encrypted with gpg later
            self.system_login_key = self._Configs.get('yomboapi', 'login_key')  # to be encrypted with gpg later
        except KeyError:
            self.system_session = None
            self.system_login_key = None

        if self._Loader.operating_mode == 'run':
            self.init_defer = Deferred()
            self.validate_system_login()
            return self.init_defer

    @inlineCallbacks
    def gateway_index(self, session=None):
        results = yield self.request("GET", "/v1/gateway", None, session)
        if results['code'] == 200:
            returnValue(results)
        elif results['code'] == 404:
            raise YomboWarning("Server cannot get gateways")
        else:
            if results['content']['message'] == "Invalid Token.":
                raise YomboWarningCredentails("URI: '%s' requires credentials." % results['content']['response']['uri'])
            raise YomboWarning("Unknown error: %s" % results['content'])

    @inlineCallbacks
    def gateway_get(self, gateway_id, session=None):
        results = yield self.request("GET", "/v1/gateway/%s" % gateway_id, None, session)
        if results['code'] == 200:
            returnValue(results)
        elif results['code'] == 404:
            raise YomboWarning("Server cannot find requested gateway: %s" % gateway_id)
        else:
            raise YomboWarning("Unknown error: %s" % results['content']['message'])

    @inlineCallbacks
    def gateway_put(self, gateway_id, values, session=None):
        results = yield self.request("PATCH", "/v1/gateway/%s" % gateway_id, values, session)
        if results['code'] == 200:
            returnValue(results)
        elif results['code'] == 404:
            raise YomboWarning("Server cannot find requested gateway: %s" % gateway_id)
        else:
            raise YomboWarning("Unknown error: %s" % results['content']['message'])

    @inlineCallbacks
    def gateway__module_get(self, gateway_id, session=None):
        results = yield self.request("GET", "/v1/gateway/%s/modules" % gateway_id, None, session)
        if results['code'] == 200:
            returnValue(results)
        elif results['code'] == 404:
            raise YomboWarning("Server cannot find requested gateway: %s" % gateway_id)
        else:
            raise YomboWarning("Unknown error: %s" % results['content']['message'])

    @inlineCallbacks
    def gateway__module_put(self, gateway_id, values, session=None):
        results = yield self.request("PUT", "/v1/gateway/%s/modules" % gateway_id, values, session)
        if results['code'] == 200:
            returnValue(results)
        elif results['code'] == 404:
            raise YomboWarning("Server cannot find requested gateway: %s" % gateway_id)
        else:
            raise YomboWarning("Unknown error: %s" % results['content']['message'])

    @inlineCallbacks
    def gateway_config_index(self, gateway_id, session=None):
        results = yield self.request("GET", "/v1/gateway/%s/config" % gateway_id, None, session)
        if results['code'] == 200:
            returnValue(results)
        elif results['code'] == 404:
            raise YomboWarning("Server cannot get gateways")
        else:
            raise YomboWarning("Unknown error: %s" % results['content']['message'])

    # Below are the core help functions

    def save_system_session(self, session):
        self.system_session = session
        self._Configs.set('yomboapi', 'auth_session', session)  # to be encrypted with gpg later

    def save_system_login_key(self, login_key):
        self.system_login_key = login_key
        self._Configs.set('yomboapi', 'login_key', login_key)  # to be encrypted with gpg later

    def select_session(self, session_id=None, session_key=None):
        if session_id is None or session_key is None:
            if self.allow_system_session:
                return self.system_session, self.system_login_key

        logger.info("select_session: Yombo API has no session data for 'selection_session'")
        return None, None

    def clear_session_cache(self, session=None):
        if (session is None):
            self.session_validation_cache.clear()
        else:
            hashed = sha1(session)
            if hashed in self.session_validation_cache:
                del self.session_validation_cache[hashed]  # None works too...

    @inlineCallbacks
    def validate_system_login(self):
        """
        Validates that the system has a valid user login key and an active system session.

        If the system session is invalid or expired, it will attempt to automatically createa  new session with
        the systemt he login key.

        If the system login key is invalid, the system will exit.

        :return:
        """
        if self.allow_system_session is False:
            self._States.set('yomboapi.valid_system_session', False)
            self.valid_system_session = False
            self._States.set('yomboapi.valid_login_key', False)
            self.valid_login_key = False
            if self.init_defer is not None:
                self.init_defer.callback(10)
            returnValue(False)

        if self.system_session is None and self.system_login_key is None:
            logger.warn("No saved system session information and no login_key. Disabling automated system changes.")
            self._States.set('yomboapi.valid_system_session', False)
            self.valid_system_session = False
            self._States.set('yomboapi.valid_login_key', False)
            self.valid_login_key = False
            if self.init_defer is not None:
                self.init_defer.callback(10)
            returnValue(False)

        if self.system_login_key is None:
            logger.warn("System doesn't have a login key!")
        else:
            results = yield self.do_validate_login_key(self.system_login_key)
            if results is True:
                logger.debug("System has a valid login key.")
                self._States.set('yomboapi.valid_login_key', True)
                self.valid_login_key = True
            else:
                logger.warn("System has an invalid login key.")
                self._States.set('yomboapi.valid_login_key', False)
                self.valid_login_key = False

        self.clear_session_cache()
        results = yield self.do_validate_session(self.system_session)
        if results is True:
            logger.debug("Yombo API has a system session!")
            self._States.set('yomboapi.valid_system_session', True)
            self.valid_system_session = True
            if self.init_defer is not None:
                self.init_defer.callback(10)
            returnValue(True)
        else:  # if invalid, try to get one with the login key!
            if self.valid_login_key:
                results = yield self.user_login_with_key(self.system_login_key)
                if results is not False:
                    self._Configs.set('yomboapi', 'auth_session', results['session'])  # to be encrypted with gpg later
                    self.system_session = results['session']
                    self._States.set('yomboapi.valid_system_session', True)
                    self.valid_system_session = True
                    if self.init_defer is not None:
                        self.init_defer.callback(10)
                    returnValue(True)

        logger.warn("Yombo API does not have a login system session!")
        self._States.set('yomboapi.valid_system_session', False)
        self.valid_system_session = False

        if self.init_defer is not None:
            self.init_defer.callback(10)
        returnValue(False)

    @inlineCallbacks
    def validate_session(self, session_id=None, session_key=None, clear_cache=False):
        session_id, session_key = self.select_session(session_id, session_key)
        if session_id is None or session_key is None:
            logger.debug("Yombo API session information is not valid: {id}:{key}", id=session_id, key=session_key)

        hashed = sha1(session_id + session_key)
        if hashed in self.session_validation_cache:
            if clear_cache is True:
                del self.session_validation_cache[hashed]
            else:
                returnValue(self.session_validation_cache[hashed])

        results = yield self.do_validate_session(session_id, session_key)
        self.session_validation_cache[hashed] = results
        returnValue(results)

    @inlineCallbacks
    def do_validate_login_key(self, login_key):
        try:
            results = yield self.request("GET", "/v1/user/login_key/validate/%s" % login_key)
        except Exception as e:
            logger.info("do_validate_login_key API Errror: {error}", error=e)
            returnValue(False)

        logger.debug("Login key results: REsults from API: {results}", results=results['content'])
        # waiting on final API.yombo.com to complete this.  If we get something, we are good for now.

        if (results['content']['code'] != 200):
            returnValue(False)
        else:
            returnValue(results['content']['response']['login'])

    @inlineCallbacks
    def do_validate_session(self, session):
        try:
            results = yield self.request("GET", "/v1/user/session/validate", None, session=session)
        except Exception as e:
            logger.debug("$$$1 API Errror: {error}", error=e)
            returnValue(False)

        logger.debug("$$$a REsults from API: {results}", results=results['content'])
# waiting on final API.yombo.com to complete this.  If we get something, we are good for now.

        if (results['content']['code'] != 200):
            returnValue(False)
        else:
            returnValue(results['content']['response']['login'])


    @inlineCallbacks
    def user_login_with_key(self, login_key):
        results = yield self.request("POST", "/v1/user/login", {'login_key': login_key}, False)
        try:
            results = yield self.request("POST", "/v1/user/login", {'login_key': login_key}, False)
        except Exception as e:
            logger.debug("$$$2 API Errror: {error}", error=e)
            returnValue(False)

        logger.info("user_login_with_key Results from API for login w key: {results}", results=results['content'])
        # waiting on final API.yombo.com to complete this.  If we get something, we are good for now.

        if (results['content']['code'] != 200):
            returnValue(False)
        elif (results['content']['message'] == 'Logged in'):
            returnValue(results['content']['response']['login'])
        else:
            returnValue(False)

    @inlineCallbacks
    def user_login_with_credentials(self, username, password, g_recaptcha_response):
        # credentials = { 'username':username, 'password':password}
        results = yield self.request("POST", "/v1/user/login", {'username':username, 'password':password, 'g-recaptcha-response': g_recaptcha_response}, False)
        logger.info("$$$3 REsults from API login creds: {results}", results=results)

        return results

    @inlineCallbacks
    def gateways(self, session_info=None):
        results = yield self.request("GET", "/v1/gateway")
        logger.debug("$$$4 REsults from API: {results}", results=results)

        if results['Code'] == 200:  # life is good!
            returnValue(results['Response']['Gateway'])
        else:
            returnValue(False)

    def make_headers(self, session):
        headers = {
            'Content-Type': self.contentType,
            'Authorization': 'Yombo-Gateway-v1',
            'x-api-key': self.api_key,
            'User-Agent': 'yombo-gateway-v0_12_0',
        }
        if session is not None:
            headers['Authorization'] = 'Bearer %s' % session

        # for k, v in headers.items():
        #     headers[k] = v.encode('utf-8')
        return headers

    def errorHandler(self,result):
        raise YomboWarning("Problem with request: %s" % result)

    @inlineCallbacks
    def request(self, method, path, data=None, session=None):
        path = self.base_url + path

        logger.debug("{method}: {path}", method=method, path=path)
        # if session is False:
        #     session = None
        if session is None:
            if self.system_session is None:
                if self.valid_system_session is False:
                    raise YomboWarningCredentails("Yombo request needs an API session.")
            session = self.system_session
        if session is False:
            session = None
        results = None
        headers = self.make_headers(session)

        if data is not None:
            data = json.dumps(data).encode()
        logger.debug("yombo api request data: {data}", data=data)

        if method == 'GET':
            results = yield self._get(path, headers, data)
        elif method == 'POST':
            results = yield self._post(path, headers, data)
        elif method == 'PATCH':
            results = yield self._patch(path, headers, data)
        elif method == 'PUT':
            results = yield self._put(path, headers, data)
        elif method == 'DELETE':
            results = yield self._delete(path, headers, data)
        else:
            raise Exception("Bad request type?? %s: %s" % (method, path) )

        returnValue(results)

    @inlineCallbacks
    def _get(self, path, headers, args=None):
        path = path
        # response = yield treq.get(path, params=args, agent=self.custom_agent, headers=headers)
        response = yield treq.get(path, headers=headers, params=args)
        content = yield treq.content(response)
        # logger.debug("getting URL: {path}  headers: {headers}", path=path, agent=self.custom_agent, headers=headers)
        final_response = self.decode_results(content, self.response_headers(response), response.code, response.phrase)
        returnValue(final_response)

    @inlineCallbacks
    def _patch(self, path, headers, data):
        print("yapi patch called. path: %s... headers: %s... data: %s" % (path, headers, data))
        response = yield treq.patch(path, data=data, agent=self.custom_agent, headers=headers)
        content = yield treq.content(response)
        final_response = self.decode_results(content, self.response_headers(response), response.code, response.phrase)
        returnValue(final_response)

    @inlineCallbacks
    def _post(self, path, headers, data):
        print("yapi post called. path: %s... headers: %s... data: %s" % (path, headers, data))

        response = yield treq.post(path, data=data, agent=self.custom_agent, headers=headers)
        content = yield treq.content(response)
        final_response = self.decode_results(content, self.response_headers(response), response.code, response.phrase)
        print("dddd: %s" % final_response)
        returnValue(final_response)

    @inlineCallbacks
    def _put(self, path, headers, data):
        response = yield treq.put(path, data=data, agent=self.custom_agent, headers=headers)
        content = yield treq.content(response)
        final_response = self.decode_results(content, self.response_headers(response), response.code, response.phrase)
        returnValue(final_response)

    @inlineCallbacks
    def _delete(self, path, headers, args={}):
        response = yield treq.delete(path, params=args, agent=self.custom_agent, headers=headers)
        content = yield treq.content(response)
        final_response = self.decode_results(content, self.response_headers(response), response.code, response.phrase)
        returnValue(final_response)
    #
    # def __encode(self, data):
    #     return json.dumps(data)

    def response_headers(self, response):
        data = {}
        raw_headers = bytes_to_unicode(response.headers._rawHeaders)
        for key, value in raw_headers.items():
            data[key.lower()] = value
        return data

    def decode_results(self, content, headers, code, phrase):
        # print("decode_results headers: %s" % headers)

        content_type = headers['content-type'][0]

        # print( "######  content: %s" % content)
        if content_type == 'application/json':
            try:
                content = json.loads(content)
                content_type = "dict"
            except Exception:
                raise YomboWarning("Receive yombo api response reported json, but isn't: %s" % content)
        elif content_type == 'application/msgpack':
            try:
                content = msgpack.loads(content)
                content_type = "dict"
            except Exception:
                raise YomboWarning("Receive yombo api response reported msgpack, but isn't.")
        else:
            try:
                content = json.loads(content)
                content_type = "dict"
            except Exception:
                try:
                    content = msgpack.loads(content)
                    content_type = "dict"
                except Exception:
                    content_type = "string"

        results = {
            'content': content,
            'content_type': content_type,
            'code': code,
            'phrase': phrase,
            'headers': headers,
        }
        if content_type == "string":
            results['code'] = 500
            results['data'] = []
            results['content'] = {
                'message': 'Unknown api error',
                'html_message': 'Unknown api error',
            }
            print("Error content: %s" % content)
            return results
        else:
            if 'response' in content:
                if 'locator' in content['response']:
                    results['data'] = content['response'][content['response']['locator']]
                else:
                    results['data'] = []
            return results

