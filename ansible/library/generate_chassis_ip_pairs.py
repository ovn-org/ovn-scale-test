#!/usr/bin/python

DOCUMENTATION = '''
---
module: generate_chassis_ip_pairs
version_added: "0.1"
short_description: Generate a list of IP
description:
    - Generate a list of IP
options:
    save:
        description:
            - Generate IP list
        default: False
'''

EXAMPLES = '''
# Generate ip list
# Usage Examples -
- name: Generate IP for emulated chassis
'''

import os
import json
import netaddr
from netaddr.ip import IPRange

class t_ip_data:
    def __init__(self,):
        self.index=[ ]
        self.ip_list=[ ]

class t_farm_data:
    def __init__(self,):
        self.farm_index=[ ]
        self.num_sandbox_farm=[ ]
        self.start_cidr_farm=[ ]

def main():
    module = AnsibleModule(
        argument_spec=dict(
            start_cidr=dict(required=True),
            num_emulation_hosts=dict(required=False, default="null"),
            num_ip=dict(required=True)
        ),
        supports_check_mode=True
    )

    start_cidr = module.params['start_cidr']
    num_emulation_hosts = module.params['num_emulation_hosts']
    num_ip = module.params['num_ip']

    sandbox_cidr = netaddr.IPNetwork(start_cidr)
    sandbox_hosts = netaddr.iter_iprange(sandbox_cidr.ip, sandbox_cidr.last)

    ip_data = t_ip_data()

    chassis_per_host = int(num_ip) / int(num_emulation_hosts)
    overflow = 0
    for i in range(0, int(num_ip)):
        '''
        cidr = start_cidr_ip.split('.')[0] + "." + \
               start_cidr_ip.split('.')[1] + "." + \
               start_cidr_ip.split('.')[2] + "." + \
               str(int(start_cidr_ip.split('.')[3]) + i)
        '''
        # ip_data.index.append(i % int(num_emulation_hosts))
        index = i / chassis_per_host
        if (index >= int(num_emulation_hosts)):
            index = int(num_emulation_hosts) - 1
            overflow += 1
        ip_data.index.append(index)
        ip_data.ip_list.append(str(sandbox_hosts.next()))

    farm_data = t_farm_data()
    num_sandbox = 0
    sandbox_hosts = netaddr.iter_iprange(sandbox_cidr.ip, sandbox_cidr.last)
    for i in range(0, int(num_emulation_hosts)):
        farm_data.farm_index.append(i)

        num_sandbox = chassis_per_host
        if (i == int(num_emulation_hosts) - 1):
            num_sandbox = chassis_per_host + overflow
        farm_data.num_sandbox_farm.append(num_sandbox)

        farm_data.start_cidr_farm.append(str(sandbox_hosts.next()))
        for i in range (0, num_sandbox - 1):
            sandbox_hosts.next()

    module.exit_json(changed=True,ip_index=ip_data.index, \
                     ip_index_list=str(ip_data.ip_list), \
                     prefixlen=str(sandbox_cidr.prefixlen),
                     farm_index=farm_data.farm_index,
                     num_sandbox_farm=farm_data.num_sandbox_farm,
                     start_cidr_farm=farm_data.start_cidr_farm)

# import module snippets
from ansible.module_utils.basic import *  # noqa
if __name__ == '__main__':
    main()
