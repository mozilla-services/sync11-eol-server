# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import json
import unittest
import contextlib

from webtest import TestApp
from pyramid import testing

from cornice.tests.support import CatchErrors


class TestSync11EOLService(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.include('sync11eol')
        wsgiapp = self.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)
        self.username = os.urandom(10).encode('hex')
        self.root = '/1.1/' + self.username

    def tearDown(self):
        testing.tearDown()

    def test_info_collections(self):
        # /info/collections tracks metaglobal and cryptokeys, but
        # no other collections.  It is created on demand.
        r = self.app.get(self.root + '/info/collections')
        self.assertEquals(r.json, {})
        self.app.put(self.root + '/storage/meta/global', '{}')
        r = self.app.get(self.root + '/info/collections')
        self.assertEquals(r.json.keys(), ['meta'])
        self.app.put(self.root + '/storage/crypto/keys', '{}')
        r = self.app.get(self.root + '/info/collections')
        self.assertEquals(sorted(r.json.keys()), ['crypto', 'meta'])
        # The other /info URLs give the EOL response.
        self.app.get(self.root + '/info/collections_count', status=513)

    def test_meta_global(self):
        # /meta/global can be read and written to, but not deleted.
        self.app.get(self.root + '/storage/meta/global', status=404)
        r = self.app.put(self.root + '/storage/meta/global', '{}')
        ts = float(r.body)
        r = self.app.get(self.root + '/storage/meta/global')
        self.assertEquals(r.json['modified'], ts)
        self.app.delete(self.root + '/storage/meta/global', status=513)

    def test_meta_fxa_credentials(self):
        # /meta/fxa_credentials can be read and written to, but not deleted.
        self.app.get(self.root + '/storage/meta/fxa_credentials', status=404)
        r = self.app.put(self.root + '/storage/meta/fxa_credentials', '{}')
        ts = float(r.body)
        r = self.app.get(self.root + '/storage/meta/fxa_credentials')
        self.assertEquals(r.json['modified'], ts)

    def test_crypto_keys(self):
        # /crypto/keys can be read and written to, but not deleted.
        self.app.get(self.root + '/storage/crypto/keys', status=404)
        r = self.app.put(self.root + '/storage/crypto/keys', '{}')
        ts = float(r.body)
        r = self.app.get(self.root + '/storage/crypto/keys')
        self.assertEquals(r.json['modified'], ts)
        self.app.delete(self.root + '/storage/crypto/keys', status=513)

    def test_storage_delete(self):
        # A DELETE /storage will appear to succeed
        self.app.delete(self.root + '/storage')

    def test_other(self):
        # All other parts of the API return the EOL response.
        r = self.app.get(self.root + '/storage/bookmarks', status=513)
        alert = json.loads(r.headers['X-Weave-Alert'])
        self.assertEquals(sorted(alert.keys()), ['code', 'message', 'url'])
        self.assertEquals(alert['code'], 'hard-eol')
        self.app.post(self.root + '/storage/history', '[{}]', status=513)
        self.app.delete(self.root + '/storage/tabs', status=513)
        self.app.get(self.root + '/meta/globular', status=513)

    def test_authentication(self):
        url = self.root + '/storage/meta/global'
        # Can set/get data without explicit credentials.
        self.app.put(url, '{"from": 0}')
        r = self.app.get(url)
        self.assertEquals(r.json['from'], 0)
        # Can't read that data when credentials are provided.
        auth1 = {'Authorization': 'Basic ONE'}
        r = self.app.get(url, headers=auth1, status=404)
        # Can set private data when credentials are provided.
        self.app.put(url, '{"from": 1}', headers=auth1)
        r = self.app.get(url, headers=auth1)
        self.assertEquals(r.json['from'], 1)
        # And it doesn't clobber data from other credentials.
        r = self.app.get(url)
        self.assertEquals(r.json['from'], 0)
        # Different credentials give different data.
        auth2 = {'Authorization': 'Basic TWO'}
        r = self.app.get(url, headers=auth2, status=404)
        self.app.put(url, '{"from": 2}', headers=auth2)
        r = self.app.get(url, headers=auth2)
        self.assertEquals(r.json['from'], 2)
        r = self.app.get(url, headers=auth1)
        self.assertEquals(r.json['from'], 1)

    def test_expected_device_flow(self):
        # The client checks /meta/global and finds it missing.
        self.app.get(self.root + '/storage/meta/global', status=404)
        # It resets the account and uploads metaglobal and cryptokeys.
        self.app.delete(self.root + '/storage')
        self.app.put(self.root + '/storage/meta/global', '{}')
        self.app.put(self.root + '/storage/crypto/keys', '{}')
        # It fetches the data it just uploaded, to sanity-check.
        r = self.app.get(self.root + '/info/collections')
        self.assertEqual(sorted(r.json.keys()), ['crypto', 'meta'])
        self.app.get(self.root + '/storage/crypto/keys')
        # It uploads migration info into fxa_credentials.
        SENTINEL = '{"uid": "foobar"}'
        self.app.put(self.root + '/storage/meta/fxa_credentials', SENTINEL)
        # It goes to actually sync, and sees the EOL error.
        self.app.post(self.root + '/storage/bookmarks', '[{}]', status=513)
        # Another device comes along and checks /info/collections.
        r = self.app.get(self.root + '/info/collections')
        self.assertEqual(sorted(r.json.keys()), ['crypto', 'meta'])
        # It bootstraps into the encryption and fetches the migration data.
        self.app.get(self.root + '/storage/crypto/keys')
        r = self.app.get(self.root + '/storage/meta/fxa_credentials')
        self.assertEqual(r.json['uid'], 'foobar')


class TestSync11EOLServiceConfig(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.include('sync11eol')
        wsgiapp = self.config.make_wsgi_app()
        wsgiapp = CatchErrors(wsgiapp)
        self.app = TestApp(wsgiapp)

    @contextlib.contextmanager
    def make_config(self, **kwds):
        config = testing.setUp(**kwds)
        config.include('sync11eol')
        config.commit()
        yield config
        testing.tearDown()

    @contextlib.contextmanager
    def make_app(self, **kwds):
        with self.make_config(**kwds) as config:
            yield TestApp(CatchErrors(config.make_wsgi_app()))

    def test_configurable_alert_details(self):
        settings = {
            'sync11eol.message': 'SYNC HAS SUNK',
            'sync11eol.url': 'http://sadtrombone.com/'
        }
        with self.make_app(settings=settings) as app:
            r = app.get('/1.1/testme/storage/bookmarks', status=513)
            alert = json.loads(r.headers['X-Weave-Alert'])
            self.assertEquals(sorted(alert.keys()), ['code', 'message', 'url'])
            self.assertEquals(alert['code'], 'hard-eol')
            self.assertEquals(alert['message'], 'SYNC HAS SUNK')
            self.assertEquals(alert['url'], 'http://sadtrombone.com/')

    def test_configurable_secret_key(self):
        settings = {
            'sync11eol.secret_key': 'secretive',
        }
        with self.make_config(settings=settings) as config:
            secret_key = config.registry.settings['sync11eol.secret_key']
            self.assertEquals(secret_key, 'secretive')

    def test_configurable_memcached_settings(self):
        settings = {
            'memcached.server': 'localhost:12345',
            'memcached.key_prefix': 'testme',
        }
        with self.make_config(settings=settings) as config:
            mc = config.registry['sync11eol.mcclient']
            self.assertEquals(mc.pool.server, 'localhost:12345')
            self.assertEquals(mc.key_prefix, 'testme')
