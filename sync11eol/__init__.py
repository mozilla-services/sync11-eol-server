# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import time

from pyramid.response import Response
from pyramid.view import view_config

from mozsvc.config import get_configurator
from mozsvc.storage.mcclient import MemcachedClient


MC_TTL = 60


def get_timestamp():
    return int(time.time())


def mc_get(request, collection):
    mc = request.registry["sync11eol.mcclient"]
    key = request.matchdict["username"] + "/" + collection
    return mc.get(key)


def mc_set(request, collection, value):
    mc = request.registry["sync11eol.mcclient"]
    key = request.matchdict["username"] + "/" + collection
    return mc.set(key, value, time=MC_TTL)


def get_bso(request, collection):
    bso = mc_get(request, collection)
    if bso is None:
        return Response(status=404)
    r = Response(json.dumps(bso), status=200)
    r.headers["Content-Type"] = "application/json"
    r.headers["X-Weave-Timestamp"] = str(get_timestamp())
    return r


def put_bso(request, collection):
    now = get_timestamp()
    try:
        bso = json.loads(request.body)
        bso["modified"] = now
    except (ValueError, TypeError):
        return Response("0", status="400")
    mc_set(request, collection, bso)
    r = Response(str(now), status=200)
    r.headers["Content-Type"] = "application/json"
    r.headers["X-Weave-Timestamp"] = str(now)
    return r


@view_config(route_name="metaglobal", request_method="GET")
def get_meta_global(request):
    return get_bso(request, "meta")


@view_config(route_name="metaglobal", request_method="PUT")
def put_meta_global(request):
    return put_bso(request, "meta")


@view_config(route_name="cryptokeys", request_method="GET")
def get_crypto_keys(request):
    return get_bso(request, "crypto")


@view_config(route_name="cryptokeys", request_method="PUT")
def put_crypto_keys(request):
    return put_bso(request, "crypto")


@view_config(route_name="collections", renderer="json")
def get_info_collections(request):
    info = {}
    for collection in ("meta", "crypto"):
        bso = mc_get(request, collection)
        if bso is not None:
            info[collection] = bso["modified"]
    return info


@view_config(route_name="storage", request_method="DELETE")
def del_storage(request):
    r = Response("0", status=200)
    r.headers["Content-Type"] = "application/json"
    r.headers["X-Weave-Timestamp"] = str(get_timestamp())
    return r


@view_config(route_name="other")
@view_config(route_name="metaglobal", request_method="DELETE")
@view_config(route_name="cryptokeys", request_method="DELETE")
def hard_eol(request):
    response = Response("0")
    response.status = "513 SERVICE EOL"
    response.content_type = "application/json"
    response.headers["X-Weave-Alert"] = json.dumps({
        'code': 'hard-eol',
        'message': 'sync has sunk',
        'url': 'http://example.com'
    })
    return response


def includeme(config):
    config.include("cornice")
    config.include("mozsvc")

    prefix = "/{api:1.0|1|1.1}/{username:[a-zA-Z0-9._-]{1,100}}"
    config.add_route("collections", prefix + "/info/collections")
    config.add_route("metaglobal", prefix + "/storage/meta/global")
    config.add_route("cryptokeys", prefix + "/storage/crypto/keys")
    config.add_route("storage", prefix + "/storage")
    config.add_route("other", prefix + "*other")
    config.scan('sync11eol')

    config.registry["sync11eol.mcclient"] = MemcachedClient()


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()
