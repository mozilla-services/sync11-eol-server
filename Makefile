VIRTUALENV = virtualenv
NOSE = local/bin/nosetests
PYTHON = local/bin/python
PIP = local/bin/pip
FLAKE8 = local/bin/flake8
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/syncstorage-build.${USER}
PYPI = https://pypi.python.org/simple

INSTALL = $(PIP) install -i $(PYPI)


.PHONY: all build test clean

all:	build

build:
	$(VIRTUALENV) --no-site-packages --distribute ./local
	$(INSTALL) -U Distribute
	$(INSTALL) -U -r requirements.txt
	$(PYTHON) ./setup.py develop


test:
	$(INSTALL) -q nose flake8
	$(FLAKE8) sync11eol
	$(NOSE) sync11eol/tests

clean:
	rm -rf ./local
