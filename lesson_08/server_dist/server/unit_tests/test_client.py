import os
import sys
import unittest

sys.path.append(os.path.join(os.getcwd(), '../'))
from client.transport import create_presence, handle_answer
from common.globals import ACTION, PRESENCE, RESPONSE, ERROR, TIME, USER, ACCOUNT_NAME


class TestClient(unittest.TestCase):
    def test_create_presence(self):
        test = create_presence()
        test[TIME] = 1.1
        self.assertEqual(test, {ACTION: PRESENCE, TIME: 1.1, USER: {ACCOUNT_NAME: 'Guest'}})

    def test_response_200(self):
        self.assertEqual(handle_answer({RESPONSE: 200}), '200 : OK')

    def test_response_400(self):
        self.assertEqual(handle_answer({RESPONSE: 400, ERROR: 'Bad request'}), '400 : Bad request')

    def test_response_absent(self):
        self.assertRaises(ValueError, handle_answer, {ERROR: 'Bad request'})
