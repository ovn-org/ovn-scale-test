======================
Binding Strategy Guide
======================

Overview
========

In OVN, a logical port can be bind to a local OVS port on any
chassis/hypervisor, depending on the VM scheduler (e.g., ``nova-scheduler``).
The binding strategy potentially impacts the network performance. That is
binding all logical ports from a logical network on a single hypervisor performs
differently than distributing the ports on multiple hypervisors.

The container-based ovn-scale-test deployment allows to configure the binding
strategy in creating and binding port rally task.


Binding Configuration
=====================

Use ``networks_per_sandbox`` to control how logical networks and the logical
ports are bind to chassis.

For example, given ``ovn_number_chassis: 10`` (10 emulated chassis) and
``network_number: 10`` (10 logical networks), the binding varies depending
on the value of ``networks_per_sandbox``.

- ``networks_per_sandbox: "10"``: this is the default case. All networks will
be evenly distributed to all chassis.

- ``networks_per_sandbox: "2"``: each chassis has ports belong to two logical
networks. In this case, the 10 logical networks are divided into 5 groups, say
[n0, n1], [n2, n3], [n4, n5], [n6, n7], [n8, n9]. Then ports in [n0, n1] are
bind to chassis 0 and 1, [n2, n3] to chassis 2 and 3, and so forth. As a
result, each chassis has two logical network as configured.

- ``networks_per_sandbox: "1"``: each chassis has ports belong to only one
logical network. In this case, the 10 logical network will have a one-to-one
mapping to the 10 chassis. Note that this is the extreme case as opposite to
``networks_per_sandbox: "10"``.


Constraint
~~~~~~~~~

TBD

Implementation Detail
=====================

TBD
