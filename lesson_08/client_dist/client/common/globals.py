import logging

RESPONSE_1 = 1
LOGGING_LEVEL = logging.DEBUG
ENCODING = 'utf-8'
MAX_PACKAGE_LENGTH = 2048
MAX_CONNECTIONS = 5
DEF_IP = '127.0.0.1'
DEF_PORT = 7777

ACTION = 'action'
TIME = 'time'
USER = 'user'
ACCOUNT_NAME = 'account_name'
SENDER = 'from'
DESTINATION = 'to'
DATA = 'bin'
PUBLIC_KEY = 'pubkey'

MESSAGE = 'message'
MESSAGE_TEXT = 'mess_text'
EXIT = 'exit'
PRESENCE = 'presence'
RESPONSE = 'response'
ERROR = 'error'
ALERT = 'alert'
USER_LIST = 'user_list'
ONLINE = 'online'
GET_CONTACTS = 'get_contacts'
ADD_CONTACT = 'add_contact'
DEL_CONTACT = 'del_contact'
DEF_IP_FOR_RESPONSE = 'def_ip_for_response'
PUBLIC_KEY_REQUEST = 'pubkey_need'
LIST_INFO = 'data_list'

# 200
RESPONSE_200 = {RESPONSE: 200}
# 202
RESPONSE_202 = {RESPONSE: 202,
                LIST_INFO: None
                }
# 400
RESPONSE_400 = {
    RESPONSE: 400,
    ERROR: None
}
# 205
RESPONSE_205 = {
    RESPONSE: 205
}

# 511
RESPONSE_511 = {
    RESPONSE: 511,
    DATA: None
}
