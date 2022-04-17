import json
import os
import sys
import logging


sys.path.append(os.path.join(os.getcwd(), '..'))
from common.globals import ENCODING, MAX_PACKAGE_LENGTH, DEF_IP, ERROR
import log.client_log_config
from log.decorator import log
LOGGER = logging.getLogger('server') if 'server.py' in sys.argv[0] else logging.getLogger('client')


@log
def get_message(sender_sock):
    try:
        encoded_data = sender_sock.recv(MAX_PACKAGE_LENGTH)
    except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as err:
        LOGGER.debug(f'Соединение сброшено: {err}')
        return
    if encoded_data:
        str_response, response = None, None
        if isinstance(encoded_data, bytes):
            str_response = encoded_data.decode(ENCODING)
            if isinstance(str_response, str):
                try:
                    response = json.loads(str_response)
                except json.JSONDecodeError:
                    LOGGER.error(f'Не удалось декодировать полученную Json строку: {str_response}.')
                    sys.exit(1)
                if isinstance(response, dict):
                    return response
                else:
                    LOGGER.error(f'ОШИБКА! сообщение: "{response}" не является DICT')
            else:
                LOGGER.error(f'ОШИБКА! сообщение: "{str_response}" не является STR')
        else:
            LOGGER.error(f'ОШИБКА! сообщение: "{str_response}" не декодируется как {bytes}')
        sender_sock.close()
        ValueError()


@log
def send_message(sock, message):
    if not isinstance(message, dict):
        LOGGER.error(f'ОШИБКА! сообщение "{message}" не является DICT')
        raise TypeError
    LOGGER.debug(f'Отправляю сообщение: {message}')
    sock.send(json.dumps(message).encode(ENCODING))


@log
def is_ip_bad(ip: str):
    if ip == '': return False
    if not isinstance(ip, str):
        LOGGER.error(f'ОШИБКА! Полученный IP: {ip} не является STR')
        ValueError()
    ip_list = ip.split('.')
    return len(ip_list) != 4 or any(not n.isdecimal() or int(n) not in range(0, 255) for n in ip_list)


@log
def is_port_bad(port):
    if isinstance(port, int):
        return not 1024 < port < 65535
    if isinstance(port, str):
        return not 1024 < int(port) < 65535
    LOGGER.error(f'Полученный PORT: {port} за пределами 1024-65535')
    ValueError()


@log
def is_name_bad(name: str):
    if name is not None and (not isinstance(name, str) or len(name) < 3):
        LOGGER.error(f'ОШИБКА: Полученный NAME: {name} не является STR или слишком короток')
        return True
    return False


@log
def check_default_param(options, param):
    if options.get(param)[1](options.get(param)[2]):
        LOGGER.error(f'ОШИБКА параметра переданного в ф-ю -> ('
                     f'{options.get(param)[3]}='
                     f'{options.get(param)[2]}), внешние параметры не определены.')
        raise ValueError
    LOGGER.debug(f'Внешний парметр {options.get(param)[3]} не определен, использую ('
                 f'{options.get(param)[3]}={options.get(param)[2]})')
    options.get(param)[0] = options.get(param)[2]


@log
def handle_parameters(ip: str, port: int):
    argv = sys.argv
    options = {
        '-a': [None, is_ip_bad, ip, 'IP'],
        '-p': [None, is_port_bad, port, 'PORT'],
        '-n': [None, is_name_bad, None, 'NAME']
    }
    if len(argv) > 1:
        k = 0
        for param in options.keys():
            if param in argv:
                i = argv.index(param) + 1
                if i <= len(argv):
                    if not options.get(param)[1](argv[i]):
                        options.get(param)[0] = argv[i]
                    else:
                        check_default_param(options, param)
            else:
                check_default_param(options, param)
    else:
        LOGGER.debug(f'Параметры запуска не указаны')
        k = 2
    LOGGER.debug(f'Использую: {" ".join(options.get(key)[3]+"="+str(options.get(key)[k] if options.get(key)[k] else "ANY") for key in options)}')
    return options.get('-a')[k], options.get('-p')[k], options.get('-n')[k]
