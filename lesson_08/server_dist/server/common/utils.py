import json
import os
import sys
import logging

sys.path.append(os.path.join(os.getcwd(), '..'))
from common.globals import ENCODING, MAX_PACKAGE_LENGTH
from log.decorator import log

LOGGER = logging.getLogger('server') if 'server.py' in sys.argv[0] else logging.getLogger('client')


# @log
def get_message(sender_sock):
    """Метод принимает сообщение и обрабатывает ошибки соединения. Принимает:
    сокет отправителя
    """
    try:
        encoded_data = sender_sock.recv(MAX_PACKAGE_LENGTH)
    except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as err:
        # LOGGER.debug(f'Соединение сброшено: {err}')
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
    """Метод отправляет сообщение в указаный сокет. Принимает:
    сокет получателя, сообщение
    """
    if not isinstance(message, dict):
        LOGGER.error(f'ОШИБКА! сообщение "{message}" не является DICT')
        raise TypeError
    LOGGER.debug(f'Отправляю сообщение: {message}')
    sock.send(json.dumps(message).encode(ENCODING))


@log
def is_ip_bad(ip: str):
    """Метод проверяет соответствие ip-адреса формату. Принимает:
    ip-адрес
    """
    if ip == '': return False
    if not isinstance(ip, str):
        LOGGER.error(f'ОШИБКА! Полученный IP: {ip} не является STR')
        return True
        # ValueError()
    ip_list = ip.split('.')
    return len(ip_list) != 4 or any(not n.isdecimal() or int(n) not in range(0, 255) for n in ip_list)


@log
def is_port_bad(port):
    """Метод проверяет соответствие порта формату. Принимает:
    порт
    """
    if isinstance(port, int):
        return not 1024 < port < 65535
    if isinstance(port, str):
        try:
            return not 1024 < int(port) < 65535
        except ValueError:
            LOGGER.error(f'Полученный PORT: {port} должен быть числом')
            return True
    LOGGER.error(f'Полученный PORT: {port} за пределами 1024-65535')
    return True
    # ValueError()


@log
def is_name_bad(name: str):
    """Метод проверяет соответствие имени пользователя формату. Принимает:
    имя пользователя
    """
    if name is not None and (not isinstance(name, str) or len(name) < 3):
        LOGGER.error(f'ОШИБКА: Полученный NAME: {name} не является STR или слишком короток')
        return True
    return False


@log
def check_default_param(options, param):
    """Метод проверяет наличие параметра переданного методу напрямую. Принимает:
    словарь эталонных команд и ограничений, проверяемый параметр/аргумент
    """
    if options.get(param)[1](options.get(param)[2]):
        err = (f'ОШИБКА параметра переданного в ф-ю -> ('
               f'{options.get(param)[3]}='
               f'{options.get(param)[2]}), внешние параметры не определены.')
        LOGGER.error(err)
        raise ValueError(err)
    LOGGER.debug(f'Внешний парметр {options.get(param)[3]} не определен, использую ('
                 f'{options.get(param)[3]}={options.get(param)[2]})')
    options.get(param)[0] = options.get(param)[2]


@log
def handle_parameters(ip: str, port: str):
    """Метод проверяет соответствие параметров переданных приложению.
    При отсутствии передает проверку внутренних параметров в check_default_param. Принимает:
    список параметров вида "-a 127.0.0.1 -p 7777 -name test2 -pwd 123456"
    """
    argv = sys.argv
    options = {
        '-a': [None, is_ip_bad, ip, 'IP'],
        '-p': [None, is_port_bad, port, 'PORT'],
        '-name': [None, is_name_bad, None, 'NAME'],
        '-pwd': [None, is_name_bad, None, 'PWD']
    }
    if len(argv) > 1:
        k = 0
    else:
        LOGGER.debug(f'Параметры запуска не указаны')
        k = 2
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

    LOGGER.debug(f'Использую: '
                 f'{" ".join(options.get(key)[3] + "=" + str(options.get(key)[k] if options.get(key)[k] else "ANY") for key in options)}')
    return options.get('-a')[k], int(options.get('-p')[k]), options.get('-name')[k], options.get('-pwd')[k]
