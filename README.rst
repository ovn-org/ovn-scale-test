==============
OVN Scale Test
==============


What is OVN Scale Test
======================

OVN Scale Test is a plugin of openstack Rally.

OVN Scale Test is intended to provide the community with a OVN control plan
scalability test tool that is capable of performing **specific**,
**complicated** and **reproducible** test cases on **simulated** scenarios.

When something fails, performs slowly or doesn't scale, it's really hard to
answer different questions on "what", "why" and "where" without a solid
scalability testing framework.

For start using this tool, you need to have a
`Rally <https://github.com/openstack/rally>`_ installed, the workflow is also
similar to Rally's.



OVN Scale Test step-by-step
===========================
In the following tutorial, we will guide you step-by-step through different use
cases that might occur in Rally.

Install Rally
-------------------
Because this test tool is mostly a plugin of Rally, you should install Rally
firstly. Rally is dedicated to OpenStack now(this situation will be change soon,
Rally developers are splitting Rally from OpenStack:
`Rally Brainstorm <https://docs.google.com/document/d/1hMwkiOPI5MwYK5Ncp4kyvryuWOaLyMLVTvNNks9qQ7w/edit#heading=h.4wzyyv2no1n7>`_),
this tool makes some changes on Rally to skip OpenStack specific code, and these
changes have not been pushed to upstream. Hence you need to use a forked Rally
from repo https://github.com/l8huang/rally.git, you can clone it and install it
by running its installation script:

.. code-block:: bash

    $ git clone https://github.com/l8huang/rally.git
    $ cd rally
    $ ./install_rally.sh

If you execute the script as regular user, Rally will create a new virtual
environment in ~/rally/ and install in it, and will use sqlite as database
backend. If you execute the script as root, Rally will be installed system wide.
For more installation options, please refer to the `Rally installation <http://rally.readthedocs.org/en/latest/install.html#install>`_ page.

Note: Rally requires Python version 2.7 or 3.4.

Install OVN Scale Test
----------------------
After Rally is installed, you can install OVN scale test tool on top of it.
Firstly get a copy of it from repo https://github.com/l8huang/rally-ovs:

.. code-block:: bash

    $ git clone https://github.com/l8huang/ovn-scale-test.git
    $ cd ovn-scale-test
    $ ./install.sh

If installed successful, you can see:

.. code-block::

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
