=========
Rally OVS
=========


What is Rally OVS
==================

Rally OVS is a plugin of openstack Rally.

Rally OVS is intended to provide the community with a OVN control plan scalability test tool that is capable of performing **specific**, **complicated** and **reproducible** test cases on **simulated** scenarios.

When something fails, performs slowly or doesn't scale, it's really hard to answer different questions on "what", "why" and "where" has happened.

For start using Rally OVS, you need to have a `Rally <https://github.com/openstack/rally>`_ installed, the workflow is also similar to Rally's.



Rally OVS step-bystep
=====================
In the following tutorial, we will guide you step-by-step through different use cases that might occur in Rally.

Installation Rally
-------------------
Because Rally OVS is mostly a plugin of Rally, you should install Rally firstly. Because Rally is dedicated to OpenStack now(this situation will be change soon, Rally developers are splitting Rally from OpenStack), Rally OVS makes some changes on Rally to skip OpenSTack specified code, and these changes have not been pushed to upstream. Hence you need to use a folked Rally from repo https://github.com/l8huang/rally.git, you can clone it and install it by running its installation script:

.. code-block:: bash

    $ git clone https://github.com/l8huang/rally.git
    $ cd rally
    $ ./install_rally.sh

If you execute the script as regular user, Rally will create a new virtual environment in ~/rally/ and install in it Rally, and will use sqlite as database backend. If you execute the script as root, Rally will be installed system wide. For more installation options, please refer to the `Rally installation <http://rally.readthedocs.org/en/latest/install.html#install>`_ page.

Note: Rally requires Python version 2.7 or 3.4.

Installation Rally OVS
----------------------
After Raly is installed, you can install Rally OVS on top of it.
Firstly get a copy of Rally OVS from repo https://github.com/l8huang/rally-ovs:
.. code-block:: bash

    $ git clone https://github.com/l8huang/rally-ovs
    # cd rally-ovs
    $ ./install_rally_ovs.sh

If installed successful, you can see:

.. code-block::

    ==================================
    Installation of Rally OVS is done!
    ==================================

    In order to work with Rally you have to enable the virtual environment
    with the command:

        . /home/<user>/rally/bin/activate

    You need to run the above command on every new shell you open before
    using Rally, but just once per session.

    Information about your Rally installation:

      * Method: virtualenv
      * Virtual Environment at: /home/<user>/rally
      * Configuration file at: /home/<user>/rally/etc/rally
      * Samples at: /home/<user>/rally/samples
