..
    Copyright 2016 Ebay Inc.

    Licensed under the Apache License, Version 2.0 (the "License"); you may
    not use this file except in compliance with the License. You may obtain
    a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
    License for the specific language governing permissions and limitations
    under the License.


.. _install:

Installation
============
Because **OVN Scale Test** is mostly a plugin of Rally, you should install
Rally firstly, then install it on top of Rally.


Install Rally
-------------------
Rally is dedicated to OpenStack now(this situation will be change soon,
Rally developers are splitting Rally from OpenStack:
`Rally Brainstorm <https://docs.google.com/document/d/1hMwkiOPI5MwYK5Ncp4kyvryuWOaLyMLVTvNNks9qQ7w/edit#heading=h.4wzyyv2no1n7>`_),
**OVN Scale Test** makes some changes on Rally to skip OpenStack specific code,
and these changes have not been pushed to Rally upstream. Hence you need to use
a forked Rally from repo https://github.com/l8huang/rally.git, you can clone it
and install it by running its installation script:

.. code-block:: bash

    $ git clone https://github.com/l8huang/rally.git
    $ cd rally
    $ ./install_rally.sh

If you execute the script as regular user, Rally will create a new virtual
environment in ~/rally/ and install in it, and will use sqlite as database
backend. If you execute the script as root, Rally will be installed system wide.
For more installation options,
please refer to the `Rally installation <http://rally.readthedocs.org/en/latest/install.html#install>`_ page.

Note: Rally requires Python version 2.7 or 3.4.

Install OVN Scale Test
----------------------
After Rally is installed, you can install **OVN Scale Test** now.
Get a copy of it from repo https://github.com/openvswitch/ovn-scale-test.git:

.. code-block:: bash

    $ git clone https://github.com/openvswitch/ovn-scale-test.git
    $ cd ovn-scale-test
    $ ./install.sh

If installed successful, you can see:

.. code-block:: console

    ======================================
    Installation of OVN scale test is done!
    =======================================

    In order to work with Rally you have to enable the virtual environment
    with the command:

        . /home/<user>/rally/bin/activate

    You need to run the above command on every new shell you opened before
    using Rally, but just once per session.

    Information about your Rally installation:

      * Method: virtualenv
      * Virtual Environment at: /home/<user>/rally
      * Configuration file at: /home/<user>/rally/etc/rally
      * Samples at: /home/<user>/rally/samples


Run ``./install.sh`` with option ``--help`` to have a list of all
available options:

.. code-block:: console

    $ ./install.sh --help
    Usage: install.sh [options]

    This script will install OVN scale test tool in your system.

    Options:
      -h, --help             Print this help text
      -v, --verbose          Verbose mode
      -s, --system           Install system-wide.
      -d, --target DIRECTORY Install Rally virtual environment into DIRECTORY.
                             (Default: /home/lhuang8/rally if not root).
      --url                  Git repository public URL to download Rally OVS from.
                             This is useful when you have only installation script and want to install Rally
                             from custom repository.
                             (Default: https://github.com/l8huang/rally-ovs.git).
                             (Ignored when you are already in git repository).
      --branch               Git branch name name or git tag (Rally OVS release) to install.
                             (Default: latest - master).
                             (Ignored when you are already in git repository).
      -y, --yes              Do not ask for confirmation: assume a 'yes' reply
                             to every question.
      -p, --python EXE       The python interpreter to use. Default: /home/lhuang8/rally/bin/python
      --develop              Install Rally with editable source code try.
                             (Default: false)
      --no-color             Disable output coloring.


**Notes:** ``--system`` option is not supported yet.


