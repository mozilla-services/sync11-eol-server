# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup, find_packages


requires = ['mozsvc>=0.8']
tests_require = requires = ['WebTest']
            

setup(name='sync11eol',
      version='0.1.0',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      entry_points="""\
      [paste.app_factory]
      main = sync11eol:main
      """,
      install_requires=requires,
      tests_require=tests_require,
      test_suite='sync11eol.tests')
