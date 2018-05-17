# Copyright 2018 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


def get_fake_context(**config):
    """Generates a fake context description for testing."""

    fake_credential = {
        "user": "fake_user",
        "host": "fake_host",
        "port": -1,
        "key": "fake_key",
        "password": "fake_password",
    }

    return {
        "task": {
            "uuid": "fake_task_uuid",
        },
        "ovn_multihost": {
            "controller": {
                "fake-controller-node": {
                    "name": "fake-controller-node",
                    "credential": fake_credential,
                },
            },
            "farms": {
                "fake-farm-node-0": {
                    "name": "fake-farm-node-0",
                    "credential": fake_credential,
                },
            },
            "install_method": "fake_install_method",
        },
        "config": config,
    }
