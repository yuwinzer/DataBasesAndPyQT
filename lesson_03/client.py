"""
1. Реализовать метакласс ClientVerifier, выполняющий базовую проверку класса «Клиент» (для
некоторых проверок уместно использовать модуль dis):
○ отсутствие вызовов accept и listen для сокетов;
○ использование сокетов для работы по TCP;
○ отсутствие создания сокетов на уровне классов, то есть отсутствие конструкций такого
вида:
    class Client:
        s = socket()
        ...
"""
# CLIENT
import dis
import json
import sys
import threading
from time import time, sleep, strftime, localtime
from socket import socket, AF_INET, SOCK_STREAM
from common.globals import ACTION, SENDER, DESTINATION, PRESENCE, RESPONSE, ERROR, EXIT, ONLINE, \
    TIME, USER, ACCOUNT_NAME, DEF_PORT, DEF_IP, MESSAGE, MESSAGE_TEXT
from common.utils import send_message, get_message, handle_parameters
from common.errors import ReqFieldMissingError, ServerError
import logging
import log.client_log_config
from log.decorator import log

LOGGER = logging.getLogger('client')


# Метакласс
class ClientVerifier(type):
    def __init__(cls, name, parent, attrs):
        attrs_required = ['get_message', 'send_message']
        attrs_not_allowed = ['accept', 'listen', 'socket']
        required_present = False
        for attr in attrs:
            try:
                decompiled = dis.get_instructions(attrs[attr])
            except TypeError:
                pass
            else:
                for i in decompiled:
                    if i.opname == 'LOAD_GLOBAL':
                        if i.argval in attrs_required:
                            required_present = True
                        if i.argval in attrs_not_allowed:
                            raise Exception(f'В классе {name} используется недопустимое: {i.argval}')
        if not required_present:
            raise Exception(f'В классе {name} отсутствует необходимое: {attrs_required}')
        super().__init__(name, parent, attrs)


class ClientReader(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, acc_name, sock):
        self.acc_name = acc_name
        self.sock = sock
        super().__init__()

    def run(self):
        while True:
            try:
                msg = get_message(self.sock)
                if not msg:
                    sys.exit(0)
                if ACTION in msg and msg[ACTION] == MESSAGE and TIME in msg and \
                        SENDER in msg and MESSAGE_TEXT in msg:
                    if DESTINATION in msg and msg[DESTINATION] == self.acc_name:
                        print(f'ЛИЧНО [{msg[SENDER]}]: {msg[MESSAGE_TEXT]}')
                    else:
                        print(f'[{msg[SENDER]}]: {msg[MESSAGE_TEXT]}')
                    LOGGER.debug(f'Получено сообщение от пользователя {msg[SENDER]}: {msg[MESSAGE_TEXT]}')
                else:
                    LOGGER.error(f'Получено некорректное сообщение с сервера: {msg}')
            except Exception as err:
                LOGGER.error(f'Не удалось декодировать полученное сообщение: {msg} : {err}')
                break
            except (OSError, ConnectionError, ConnectionAbortedError,
                    ConnectionResetError, json.JSONDecodeError) as err:
                LOGGER.error(f'Потеряно соединение с сервером: {err}')
                break


class ClientSender(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, acc_name, sock):
        self.acc_name = acc_name
        self.sock = sock
        super().__init__()

    def run(self):
        self.print_help()
        while True:
            msg = input(f'=> ')
            command = msg[0:2]

            if command in ['/q', '/й']:
                send_message(self.sock, self.create_service_message(self.acc_name, EXIT))
                print('Завершение работы')
                LOGGER.info('Завершение работы по команде пользователя.')
                sleep(1)
                sys.exit(0)

            elif command in ['/h', '/?']:
                self.print_help()

            elif command in ['! ']:
                _name_len = msg[2:].find(' ')
                if _name_len > 0:
                    dest_name = msg[2:2 + _name_len]
                    self.create_message(self.sock, self.acc_name, dest_name, msg[3 + _name_len:])
                else:
                    print('Для отправки личного сообщения введите "! <имя> <сообщение>"')

            elif command in ['/!']:
                send_message(self.sock, self.create_service_message(self.acc_name, ONLINE))
            else:
                self.create_message(self.sock, self.acc_name, '', msg)

    @log
    def create_message(self, sock, acc_name, dest_name, msg):
        message_dict = {
            ACTION: MESSAGE,
            TIME: time(),
            SENDER: acc_name,
            DESTINATION: dest_name,
            MESSAGE_TEXT: msg
        }
        try:
            send_message(sock, message_dict)
            LOGGER.debug(f'Отправлено сообщение для пользователя {dest_name}')
        except Exception as err:
            LOGGER.error(f'Потеряно соединение с сервером: {err}')
            sys.exit(1)

    @log
    def create_service_message(self, acc_name, mgs_type):
        if mgs_type == PRESENCE:
            LOGGER.debug(f'Сформировано {PRESENCE} сообщение для пользователя {acc_name}')
            return {
                ACTION: PRESENCE,
                TIME: time(),
                USER: {
                    ACCOUNT_NAME: acc_name
                }
            }
        if mgs_type == ONLINE:
            LOGGER.debug(f'Сформировано {ONLINE} сообщение для сервера')
            return {
                ACTION: ONLINE,
                TIME: time(),
                USER: {
                    ACCOUNT_NAME: acc_name
                }
            }
        if mgs_type == EXIT:
            return {
                ACTION: EXIT,
                TIME: time(),
                ACCOUNT_NAME: acc_name
            }

    @log
    def handle_answer(self, msg):
        if RESPONSE in msg:
            if msg[RESPONSE] == 200:
                return True
            elif msg[RESPONSE] == 400:
                LOGGER.error(f'Ошибка соединения: {msg}')
                print(msg[ERROR])
                return False
        LOGGER.error(f'Получен неправильный ответ сервера(отсутствует RESPONSE): {msg}')
        raise ValueError

    def print_help(self):
        print(' Поддерживаемые команды:')
        print('   <сообщение> - отправить сообщение всем')
        print('   ! <имя> <сообщение> - отправить личное сообщение')
        print('   /! - запросить список собеседников')
        print('   /h или /? - вывести подсказки по командам')
        print('   /q или /й - выход из программы')


def main():
    LOGGER.debug('=' * 40 + '[ SERVER LOG START TIME: ' + strftime("%a, %d %b %Y %H:%M:%S ]", localtime()) + '=' * 40)
    try:
        serv_ip, serv_port, acc_name = handle_parameters(ip=DEF_IP, port=DEF_PORT)
        print('*' * 100 + '\n Клиент системы обмена сообщениями. ВЕРСИЯ 015 БУ. ГОСТ 189-27-1956.\n' + '*' * 100)

        try:
            for knock in range(5):
                try:
                    my_sock = socket(AF_INET, SOCK_STREAM)
                    if not acc_name:
                        acc_name = input('Представьтесь: ')
                    LOGGER.debug(f'[{acc_name}]: Попытка соедиения...')
                    my_sock.connect((serv_ip, serv_port))
                    LOGGER.debug(f'Отправляю сообщение о присутствии...')
                    client_sender = ClientSender(acc_name, my_sock)
                    send_message(my_sock, client_sender.create_service_message(acc_name, PRESENCE))
                    LOGGER.debug(f'Жду ответа от сервера...')
                    answer = client_sender.handle_answer(get_message(my_sock))
                    LOGGER.debug(f'Получен ответ сервера: {answer}')
                    if answer:
                        break
                    else:
                        acc_name = ''
                        my_sock.close()
                    if knock == 4:
                        print('К сожалению подключиться не удалось. Попробуйте позже.')
                        sys.exit(0)
                except (ConnectionRefusedError, ConnectionError):
                    LOGGER.debug(f'Сервер не отвечает {serv_ip}:{serv_port}')
                if knock == 4:
                    print('К сожалению подключиться не удалось. Попробуйте позже.')
                    sys.exit(0)
        except (ConnectionRefusedError, ConnectionError):
            LOGGER.info(f'Не удалось подключиться к серверу {serv_ip}:{serv_port}, '
                        f'сервер отверг запрос на подключение.')
        except json.JSONDecodeError:
            LOGGER.error('Не удалось декодировать полученную Json строку.')
            sys.exit(1)
        except ServerError as error:
            LOGGER.error(f'При установке соединения сервер вернул ошибку: {error.text}')
            sys.exit(1)
        except ReqFieldMissingError as missing_error:
            LOGGER.error(f'В ответе сервера отсутствует необходимое поле {missing_error.missing_field}')
            sys.exit(1)
        else:
            print(f' Приветствуем, {acc_name}.\n'
                  f' Напоминаем, что вы несете полную ответственность за свои слова в соответствии с законодательнвом.\n'
                  f' Приятного общения.\n' + '*' * 100)
            LOGGER.info(f'Клиент запущен. Использую SERVER IP:{serv_ip} PORT:{serv_port} NAME:{acc_name}')
            print(f'Соединение установлено')
            thread_receiver = ClientReader(acc_name, my_sock)
            thread_receiver.daemon = True
            thread_receiver.start()
            LOGGER.debug('Запущен процесс получатель')

            thread_sender_ui = ClientSender(acc_name, my_sock)
            thread_sender_ui.daemon = True
            thread_sender_ui.start()
            LOGGER.debug('Запущен процесс интерфейс и отправщик')

            while thread_receiver.is_alive() and thread_sender_ui.is_alive():
                sleep(0.7)

    except KeyboardInterrupt:
        LOGGER.info(f'Завершение работы клиента')
        # my_sock.close()
        LOGGER.info(f'Клиент остановлен')
        sys.exit(1)


if __name__ == '__main__':
    main()
