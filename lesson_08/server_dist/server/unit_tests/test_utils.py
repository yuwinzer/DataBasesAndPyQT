import os
import sys
import json
import unittest
from unittest.mock import patch
sys.path.append(os.path.join(os.getcwd(), '../../../lesson_05'))
from client.common.utils import get_message, send_message, handle_parameters
from client.common import ACTION, PRESENCE, RESPONSE, ERROR, TIME, USER, ACCOUNT_NAME,\
    DEF_IP, DEF_PORT, ENCODING


class TestUtils(unittest.TestCase):
    # Если нет одного параметра - используется другой (аргумент или по умолчанию)
    def test_handle_parameters_without_ip_argv(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-p', DEF_PORT]):
            self.assertEqual(handle_parameters(ip=DEF_IP, port=DEF_PORT), (DEF_IP, DEF_PORT))

    def test_handle_parameters_without_ip_var(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-a', DEF_IP, '-p', DEF_PORT]):
            self.assertEqual(handle_parameters(ip='', port=DEF_PORT), (DEF_IP, DEF_PORT))

    def test_handle_parameters_without_port_argv(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-a', DEF_IP]):
            self.assertEqual(handle_parameters(ip=DEF_IP, port=DEF_PORT), (DEF_IP, DEF_PORT))

    def test_handle_parameters_without_port_var(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-a', DEF_IP, '-p', DEF_PORT]):
            self.assertEqual(handle_parameters(ip=DEF_IP, port=''), (DEF_IP, DEF_PORT))

    # Ошибка, если аргументы или значения по умолчанию не подходят
    def test_handle_parameters_without_ip_parameter(self):
        with patch.object(sys, 'argv', ['common.utils.py']):
            self.assertRaises(ValueError, handle_parameters, ip='', port=DEF_PORT)

    def test_handle_parameters_with_wrong_ip_parameter(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-a', '127.635.0.1']):
            self.assertRaises(ValueError, handle_parameters, ip='127.0.500.1', port=DEF_PORT)

    def test_handle_parameters_with_mistype_ip_parameter(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-a', 'aaa.qqq.ttt.fff']):
            self.assertRaises(ValueError, handle_parameters, ip='127.0.0.1a', port=DEF_PORT)

    def test_handle_parameters_with_mistype_port(self):
        with patch.object(sys, 'argv', ['common.utils.py', '-p', 'aaa.qqq.ttt.fff']):
            self.assertRaises(ValueError, handle_parameters, ip='127.0.0.1', port=1000)

    def test_handle_parameters_with_no(self):
        with patch.object(sys, 'argv', ['common.utils.py']):
            self.assertRaises(ValueError, handle_parameters, ip='127.0.0.1a', port='')


class TestSocket:
    def __init__(self, test_dict):
        self.test_dict = test_dict
        self.received_msg = None
        self.encoded_msg = None

    def send(self, msg):
        self.encoded_msg = json.dumps(self.test_dict).encode(ENCODING)
        self.received_msg = msg

    def recv(self, max_len):
        return json.dumps(self.test_dict).encode(ENCODING)


class TestCommunication(unittest.TestCase):
    send_dict = {ACTION: PRESENCE, TIME: 1.1, USER: {ACCOUNT_NAME: 'Guest'}}
    ok_dict = {RESPONSE: 200}
    err_dict = {RESPONSE: 400, ERROR: 'Bad request'}

    def test_send_message_ok(self):
        test_socket = TestSocket(self.send_dict)
        send_message(test_socket, self.send_dict)
        self.assertEqual(test_socket.encoded_msg, test_socket.received_msg)

    def test_send_message_err(self):
        test_socket = TestSocket(self.send_dict)
        send_message(test_socket, self.send_dict)
        self.assertRaises(TypeError, send_message, test_socket, 'try')

    def test_get_message_ok(self):
        test_sock_ok = TestSocket(self.ok_dict)
        self.assertEqual(get_message(test_sock_ok), self.ok_dict)

    def test_get_message_err(self):
        test_sock_err = TestSocket(self.err_dict)
        self.assertEqual(get_message(test_sock_err), self.err_dict)
