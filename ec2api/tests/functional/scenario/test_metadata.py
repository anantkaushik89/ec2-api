# Copyright 2015 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import base64

from oslo_log import log
from tempest_lib.common.utils import data_utils

from ec2api.tests.functional import base
from ec2api.tests.functional import config
from ec2api.tests.functional.scenario import base as scenario_base
from ec2api.tests.functional import ssh

CONF = config.CONF
LOG = log.getLogger(__name__)


class MetadataTest(scenario_base.BaseScenarioTest):

    def test_metadata(self):
        if not CONF.aws.image_id:
            raise self.skipException('aws image_id does not provided')

        key_name = data_utils.rand_name('testkey')
        pkey = self.create_key_pair(key_name)
        sec_group_name = self.create_standard_security_group()
        user_data = data_utils.rand_uuid()
        instance_id = self.run_instance(KeyName=key_name, UserData=user_data,
                                        SecurityGroups=[sec_group_name])

        resp, data = self.client.DescribeInstanceAttribute(
            InstanceId=instance_id, Attribute='userData')
        self.assertEqual(200, resp.status_code, base.EC2ErrorConverter(data))
        self.assertEqual(data['UserData']['Value'],
                         base64.b64encode(user_data))

        ip_address = self.get_instance_ip(instance_id)

        ssh_client = ssh.Client(ip_address, CONF.aws.image_user, pkey=pkey)

        url = 'http://169.254.169.254'
        data = ssh_client.exec_command('curl %s/latest/user-data' % url)
        self.assertEqual(user_data, data)

        data = ssh_client.exec_command('curl %s/latest/meta-data/ami-id' % url)
        self.assertEqual(CONF.aws.image_id, data)
