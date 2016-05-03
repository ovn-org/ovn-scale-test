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

def main():
    module = AnsibleModule(
        argument_spec=dict(
            start_cidr=dict(required=True),
            group_size=dict(required=False, default="null"),
            num_ip=dict(required=True)
        ),
        supports_check_mode=True
    )

    start_cidr = module.params['start_cidr']
    group_size = module.params['group_size']
    num_ip = module.params['num_ip']

    sandbox_cidr = netaddr.IPNetwork(start_cidr)
    sandbox_hosts = netaddr.iter_iprange(sandbox_cidr.ip, sandbox_cidr.last)

    ip_data = t_ip_data()

    chassis_per_host = int(num_ip) / int(group_size)
    for i in range(0, int(num_ip)):
        '''
        cidr = start_cidr_ip.split('.')[0] + "." + \
               start_cidr_ip.split('.')[1] + "." + \
               start_cidr_ip.split('.')[2] + "." + \
               str(int(start_cidr_ip.split('.')[3]) + i)
        '''
        # ip_data.index.append(i % int(group_size))
        index = i / chassis_per_host
        if (index >= int(group_size)):
            index = 0
        ip_data.index.append(index)
        ip_data.ip_list.append(str(sandbox_hosts.next()))

    module.exit_json(changed=True,ip_index=ip_data.index, \
                     ip_index_list=str(ip_data.ip_list), \
                     prefixlen=str(sandbox_cidr.prefixlen))

# import module snippets
from ansible.module_utils.basic import *  # noqa
if __name__ == '__main__':
    main()
