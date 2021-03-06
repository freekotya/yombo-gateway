# Import twisted libraries
from twisted.internet.defer import inlineCallbacks, Deferred, maybeDeferred

# Import Yombo libraries
from yombo.lib.webinterface.auth import require_auth

def route_gateways(webapp):
    with webapp.subroute("/gateways") as webapp:
        @webapp.route('/')
        @require_auth()
        def page_gateways(webinterface, request, session):
            return webinterface.redirect(request, '/gateways/index')

        @webapp.route('/index')
        @require_auth()
        def page_lib_gateways_index(webinterface, request, session):
            page = webinterface.get_template(request, webinterface._dir + 'pages/gateways/index.html')
            webinterface.home_breadcrumb(request)
            webinterface.add_breadcrumb(request, "/gateways/index", "Gateways")
            return page.render(alerts=webinterface.get_alerts(),
                               gateways=webinterface._Gateways.get_gateways(),
                               )

        @webapp.route('/<string:gateway_id>/details')
        @require_auth()
        def page_lib_gateways_details(webinterface, request, session, gateway_id):
            try:
                gateway = webinterface._Gateways.get(gateway_id)
            except Exception as e:
                print("gatew find error: %s" % e)
                webinterface.add_alert('Gateway was not found.  %s' % gateway_id, 'warning')
                redirect = webinterface.redirect(request, '/gateways/index')
                return redirect
            page = webinterface.get_template(request, webinterface._dir + 'pages/gateways/details.html')
            webinterface.home_breadcrumb(request)
            webinterface.add_breadcrumb(request, "/gateways/index", "Gateways")
            webinterface.add_breadcrumb(request, "/gateways/%s/details" % gateway_id, gateway.label)
            page = page.render(alerts=webinterface.get_alerts(),
                               gateway=gateway,
                               gateways=webinterface._Gateways.get_gateways(),
                               # devices=webinterface._Devices.devices,
                               devicetypes=webinterface._DeviceTypes.device_types,
                               )
            return page