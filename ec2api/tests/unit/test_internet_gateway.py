# Copyright 2014
# The Cloudscaling Group, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import mock
from neutronclient.common import exceptions as neutron_exception
from oslo_config import cfg

from ec2api.tests.unit import base
from ec2api.tests.unit import fakes
from ec2api.tests.unit import matchers


class IgwTestCase(base.ApiTestCase):

    def setUp(self):
        super(IgwTestCase, self).setUp()
        self.DB_IGW_1_DETACHED = fakes.gen_db_igw(fakes.ID_EC2_IGW_1)
        self.DB_IGW_2_ATTACHED = fakes.gen_db_igw(fakes.ID_EC2_IGW_2,
                                                  fakes.ID_EC2_VPC_2)

    def test_create_igw(self):
        self.db_api.add_item.return_value = fakes.DB_IGW_2

        resp = self.execute('CreateInternetGateway', {})

        self.assertEqual(resp['http_status_code'], 200)
        self.assertIn('internetGateway', resp)
        igw = resp['internetGateway']
        self.assertThat(fakes.EC2_IGW_2, matchers.DictMatches(igw))
        self.db_api.add_item.assert_called_with(
                mock.ANY, 'igw', {})

    def test_attach_igw(self):
        conf = cfg.CONF
        self.addCleanup(conf.reset)
        conf.set_override('external_network', fakes.NAME_OS_PUBLIC_NETWORK)
        self.set_mock_db_items(fakes.DB_IGW_1, fakes.DB_IGW_2, fakes.DB_VPC_2)
        self.neutron.list_networks.return_value = (
                {'networks': [{'id': fakes.ID_OS_PUBLIC_NETWORK}]})

        resp = self.execute(
                'AttachInternetGateway',
                {'VpcId': fakes.ID_EC2_VPC_2,
                 'InternetGatewayId': fakes.ID_EC2_IGW_2})

        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])
        self.db_api.get_item_by_id.assert_any_call(mock.ANY,
                                                   fakes.ID_EC2_IGW_2)
        self.db_api.get_item_by_id.assert_any_call(mock.ANY,
                                                   fakes.ID_EC2_VPC_2)
        self.db_api.get_items.assert_called_once_with(mock.ANY, 'igw')
        self.db_api.update_item.assert_called_once_with(
                mock.ANY, self.DB_IGW_2_ATTACHED)
        self.neutron.add_gateway_router.assert_called_once_with(
                fakes.ID_OS_ROUTER_2,
                {'network_id': fakes.ID_OS_PUBLIC_NETWORK})
        self.neutron.list_networks.assert_called_once_with(
                **{'router:external': True,
                   'name': fakes.NAME_OS_PUBLIC_NETWORK})

    def test_attach_igw_invalid_parameters(self):
        def do_check(error_code):
            resp = self.execute(
                    'AttachInternetGateway',
                    {'VpcId': fakes.ID_EC2_VPC_2,
                     'InternetGatewayId': fakes.ID_EC2_IGW_2})

            self.assertEqual(400, resp['http_status_code'])
            self.assertEqual(error_code, resp['Error']['Code'])
            self.assertEqual(0, self.neutron.add_gateway_router.call_count)
            self.assertEqual(0, self.db_api.update_item.call_count)

            self.neutron.reset_mock()
            self.db_api.reset_mock()

        self.set_mock_db_items(fakes.DB_VPC_2)
        do_check('InvalidInternetGatewayID.NotFound')

        self.set_mock_db_items(fakes.DB_IGW_2)
        do_check('InvalidVpcID.NotFound')

        self.set_mock_db_items(self.DB_IGW_2_ATTACHED, fakes.DB_VPC_2)
        do_check('Resource.AlreadyAssociated')

        self.set_mock_db_items(
            fakes.DB_IGW_2, fakes.DB_VPC_2,
            fakes.gen_db_igw(fakes.ID_EC2_IGW_1, fakes.ID_EC2_VPC_2))
        do_check('InvalidParameterValue')

    def test_attach_igw_rollback(self):
        conf = cfg.CONF
        self.addCleanup(conf.reset)
        conf.set_override('external_network', fakes.NAME_OS_PUBLIC_NETWORK)
        self.set_mock_db_items(fakes.DB_IGW_1, fakes.DB_IGW_2, fakes.DB_VPC_2)
        self.neutron.list_networks.return_value = (
                {'networks': [{'id': fakes.ID_OS_PUBLIC_NETWORK}]})
        self.neutron.add_gateway_router.side_effect = Exception()

        self.execute('AttachInternetGateway',
                     {'VpcId': fakes.ID_EC2_VPC_2,
                      'InternetGatewayId': fakes.ID_EC2_IGW_2})

        self.db_api.update_item.assert_any_call(
                mock.ANY, fakes.DB_IGW_2)

    def test_detach_igw(self):
        self.set_mock_db_items(fakes.DB_IGW_1, fakes.DB_VPC_1)

        resp = self.execute(
                'DetachInternetGateway',
                {'VpcId': fakes.EC2_VPC_1['vpcId'],
                 'InternetGatewayId': fakes.EC2_IGW_1['internetGatewayId']})

        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])
        self.db_api.get_item_by_id.assert_any_call(mock.ANY,
                                                   fakes.ID_EC2_IGW_1)
        self.db_api.get_item_by_id.assert_any_call(mock.ANY,
                                                   fakes.ID_EC2_VPC_1)
        self.db_api.update_item.assert_called_once_with(
                mock.ANY, self.DB_IGW_1_DETACHED)
        self.neutron.remove_gateway_router.assert_called_once_with(
                fakes.ID_OS_ROUTER_1)

    def test_detach_igw_invalid_parameters(self):
        def do_check(error_code):
            resp = self.execute(
                    'DetachInternetGateway',
                    {'VpcId': fakes.ID_EC2_VPC_1,
                     'InternetGatewayId': fakes.ID_EC2_IGW_1})

            self.assertEqual(400, resp['http_status_code'])
            self.assertEqual(error_code, resp['Error']['Code'])
            self.assertEqual(0, self.neutron.remove_gateway_router.call_count)
            self.assertEqual(0, self.db_api.update_item.call_count)

            self.neutron.reset_mock()
            self.db_api.reset_mock()

        self.set_mock_db_items(fakes.DB_VPC_1)
        do_check('InvalidInternetGatewayID.NotFound')

        self.set_mock_db_items(fakes.DB_IGW_1)
        do_check('InvalidVpcID.NotFound')

        self.set_mock_db_items(self.DB_IGW_1_DETACHED, fakes.DB_VPC_1)
        do_check('Gateway.NotAttached')

    def test_detach_igw_no_router(self):
        self.set_mock_db_items(fakes.DB_IGW_1, fakes.DB_VPC_1)
        self.neutron.remove_gateway_router.side_effect = (
                neutron_exception.NotFound)

        resp = self.execute(
                'DetachInternetGateway',
                {'VpcId': fakes.ID_EC2_VPC_1,
                 'InternetGatewayId': fakes.ID_EC2_IGW_1})

        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])
        self.neutron.remove_gateway_router.assert_called_once_with(
                fakes.ID_OS_ROUTER_1)

    def test_detach_igw_rollback(self):
        self.set_mock_db_items(fakes.DB_IGW_1, fakes.DB_VPC_1)
        self.neutron.remove_gateway_router.side_effect = Exception()

        self.execute(
                'DetachInternetGateway',
                {'VpcId': fakes.EC2_VPC_1['vpcId'],
                 'InternetGatewayId': fakes.EC2_IGW_1['internetGatewayId']})

        self.db_api.update_item.assert_any_call(
                mock.ANY, fakes.DB_IGW_1)

    def test_delete_igw(self):
        self.set_mock_db_items(fakes.DB_IGW_2)

        resp = self.execute(
                'DeleteInternetGateway',
                {'InternetGatewayId': fakes.ID_EC2_IGW_2})

        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])
        self.db_api.get_item_by_id.assert_called_once_with(mock.ANY,
                                                           fakes.ID_EC2_IGW_2)
        self.db_api.delete_item.assert_called_once_with(mock.ANY,
                                                        fakes.ID_EC2_IGW_2)

    def test_delete_igw_invalid_parameters(self):
        def do_check(error_code):
            resp = self.execute(
                    'DeleteInternetGateway',
                    {'InternetGatewayId': (
                            fakes.EC2_IGW_1['internetGatewayId'])})

            self.assertEqual(400, resp['http_status_code'])
            self.assertEqual(error_code, resp['Error']['Code'])
            self.assertEqual(0, self.db_api.delete_item.call_count)

            self.neutron.reset_mock()
            self.db_api.reset_mock()

        self.set_mock_db_items()
        do_check('InvalidInternetGatewayID.NotFound')

        self.set_mock_db_items(fakes.DB_IGW_1)
        do_check('DependencyViolation')

    def test_describe_igw(self):
        self.set_mock_db_items(fakes.DB_IGW_1, fakes.DB_IGW_2)

        resp = self.execute('DescribeInternetGateways', {})
        self.assertEqual(200, resp['http_status_code'])
        self.assertThat(resp['internetGatewaySet'],
                        matchers.ListMatches([fakes.EC2_IGW_1,
                                              fakes.EC2_IGW_2]))

        resp = self.execute('DescribeInternetGateways',
                            {'InternetGatewayId.1': fakes.ID_EC2_IGW_2})
        self.assertEqual(200, resp['http_status_code'])
        self.assertThat(resp['internetGatewaySet'],
                        matchers.ListMatches([fakes.EC2_IGW_2]))
        self.db_api.get_items_by_ids.assert_called_once_with(
            mock.ANY, set([fakes.ID_EC2_IGW_2]))

        self.check_filtering(
            'DescribeInternetGateways', 'internetGatewaySet',
            [('internet-gateway-id', fakes.ID_EC2_IGW_2),
             ('attachment.state', 'available'),
             ('attachment.vpc-id', fakes.ID_EC2_VPC_1)])
        self.check_tag_support(
            'DescribeInternetGateways', 'internetGatewaySet',
            fakes.ID_EC2_IGW_2, 'internetGatewayId')
