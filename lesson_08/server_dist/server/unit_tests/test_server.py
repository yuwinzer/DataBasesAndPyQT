import os
import sys
import unittest

sys.path.append(os.path.join(os.getcwd(), '../'))
from server.server_core import handle_client_message
from client.common import ACTION, PRESENCE, RESPONSE, ERROR, TIME, USER, ACCOUNT_NAME


class TestServer(unittest.TestCase):
    ok_dict = {RESPONSE: 200}
    err_dict = {RESPONSE: 400, ERROR: 'Bad request'}

    def test_ok(self):
        self.assertEqual(handle_client_message(
            {ACTION: PRESENCE, TIME: 1.1, USER: {ACCOUNT_NAME: 'Guest'}}), self.ok_dict)

    def test_no_action(self):
        self.assertEqual(handle_client_message(
            {TIME: 1.1, USER: {ACCOUNT_NAME: 'Guest'}}), self.err_dict)

    def test_wrong_action(self):
        self.assertEqual(handle_client_message(
            {ACTION: 'Тут был Вася', TIME: 1.1, USER: {ACCOUNT_NAME: 'Guest'}}), self.err_dict)

    def test_no_time(self):
        self.assertEqual(handle_client_message(
            {ACTION: PRESENCE, USER: {ACCOUNT_NAME: 'Guest'}}), self.err_dict)

    def test_no_user(self):
        self.assertEqual(handle_client_message(
            {ACTION: PRESENCE, TIME: 1.1}), self.err_dict)

    def test_anon_user(self):
        self.assertEqual(handle_client_message(
            {ACTION: PRESENCE, TIME: 1.1, USER: {ACCOUNT_NAME: 'Anon'}}), self.err_dict)
