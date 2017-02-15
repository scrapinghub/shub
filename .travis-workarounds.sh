#!/bin/bash
set -e
set -x

if [[ "${TOXENV}" == "pypy" ]]; then
    sudo add-apt-repository -y ppa:pypy/ppa
    sudo apt-get -qy update
    sudo apt-get install -y pypy pypy-dev
    # This is required because we need to get rid of the Travis installed PyPy
    # or it'll take precedence over the PPA installed one.
    sudo rm -rf /usr/local/pypy/bin
fi

if [[ "$TRAVIS_OS_NAME" == "osx" ]]; then
    brew update > /dev/null

    brew install zoidbergwill/python/python35

    PATH="/usr/local/bin:$PATH"

    # Use brew python for virtualenv
    /usr/local/bin/virtualenv -p /usr/local/bin/python3.5 ~/virtualenv/python3.5
fi
