"""
1. Начать реализацию класса «Хранилище» для серверной стороны. Хранение необходимо осуществлять в базе данных. В качестве СУБД использовать sqlite. Для взаимодействия с БД можно применять ORM.
"""
# SERVER
import dis
import random
import select
import threading

from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from common.globals import *
from common.utils import get_message, send_message, handle_parameters
from time import time, localtime, strftime
from log.decorator import log
from server_db import ServerDB

LOGGER = logging.getLogger('server')


# Дескриптор
class CheckoutPort:
    def __set_name__(self, owner, name):
        self.port = name

    def __get__(self, instance, owner):
        return instance.__dict__[self.port]

    def __set__(self, instance, value):
        if value:
            if type(value) is not int:
                raise TypeError(f'Параметр PORT должен быть целым числом: {str(type(value))} = {str(value)}')
            elif value < 0:
                raise ValueError(f'Параметр PORT не может быть отрицательным: {str(value)}')
            instance.__dict__[self.port] = value
        else:
            instance.__dict__[self.port] = DEF_PORT


# Метакласс
class ServerVerifier(type):
    def __init__(cls, name, parent, attrs):
        attrs_required = ['SOCK_STREAM', 'AF_INET']
        func_not_allowed = ['connect']
        for attr in attrs:
            try:
                decompiled = dis.get_instructions(attrs[attr])
            except TypeError:
                pass
            else:
                for i in decompiled:
                    if i.opname == 'LOAD_GLOBAL':
                        if i.argval in attrs_required:
                            attrs_required.remove(i.argval)
                        if i.argval in func_not_allowed:
                            raise Exception(f'В классе {name} используется недопустимое: {i.argval}')
        if attrs_required:
            raise Exception(f'В классе {name} отсутствует необходимое: {attrs_required}')
        super().__init__(name, parent, attrs)


class Server(threading.Thread, metaclass=ServerVerifier):
    serv_port = CheckoutPort()

    def __init__(self, database):
        self.serv_ip, self.serv_port, _ = handle_parameters(ip='', port=DEF_PORT)
        self.serv_sock = None
        self.database = database
        self.cli_socks = []
        self.clients = {}
        self.msgs = []
        super().__init__()

    @log
    def handle_connection(self, msg, cli_sock):
        cli_ip, cli_port = cli_sock.getpeername()
        LOGGER.debug(f'Проверка типа сообщения: {msg}')
        # Запрос подключения
        if ACTION in msg:
            if TIME in msg and USER in msg:
                cli_name = msg[USER][ACCOUNT_NAME]
                if msg[ACTION] == PRESENCE:
                    if cli_name in self.clients.keys():
                        LOGGER.info(f'Попытка войти с таким же именем: {cli_ip} {cli_name}')
                        send_message(cli_sock, {
                            RESPONSE: 400,
                            ERROR: f'Пользователь {cli_name} уже подключен'})
                        self.cli_socks.remove(cli_sock)
                        cli_sock.close()
                    else:
                        self.clients[cli_name] = cli_sock
                        self.database.user_login(cli_name, cli_ip, cli_port)
                        LOGGER.info(f'>>>>>> Подключился: {cli_ip} {cli_name}')
                        send_message(cli_sock, {RESPONSE: 200})
                    return
        # Запрос списка пользователей
                elif msg[ACTION] == ONLINE:
                    LOGGER.info(f'Получен запрос списка собеседников от: {cli_ip} {cli_name}')
                    send_message(self.clients[cli_name], {
                        ACTION: MESSAGE,
                        TIME: time(),
                        SENDER: 'SERVER',
                        DESTINATION: cli_name,
                        MESSAGE_TEXT: f'{" ".join(self.clients.keys())}'})
                    return
        # Сообщение
            elif msg[ACTION] == MESSAGE and TIME in msg and \
                    SENDER in msg and DESTINATION in msg and MESSAGE_TEXT in msg:
                if msg[MESSAGE_TEXT]:
                    self.msgs.append(msg)
                    LOGGER.debug(f'Сообщение типа MESSAGE добавлено в обработку: {msg[MESSAGE_TEXT]}')
                return
        # Отключение
            elif msg[ACTION] == EXIT and ACCOUNT_NAME in msg:
                self.del_sock(cli_sock, self.cli_socks)
                self.database.user_logout(msg[ACCOUNT_NAME])
                LOGGER.info(f'<<<<<< Отключился: {cli_ip} {msg[ACCOUNT_NAME]}')
                del self.clients[msg[ACCOUNT_NAME]]
                return
        # Ошибки
        else:
            LOGGER.error(f'Ошибка: Не удается обработать запрос:\n{msg}')
            send_message(cli_sock, {
                RESPONSE: 400,
                ERROR: 'Bad request'})
            return

    @log
    def handle_message(self, msg, send_sock):
        dest_cli, send_cli = msg[DESTINATION], msg[SENDER]
        LOGGER.debug(f'{dest_cli=} {send_cli=}')
        if dest_cli == '':
            for every_cli in send_sock:
                LOGGER.debug(f'Отправляю сообщение ВСЕМ: {msg}')
                send_message(every_cli, msg)
            LOGGER.info(f'{send_cli}: {msg}')
        elif dest_cli in self.clients and self.clients[dest_cli] in send_sock:
                LOGGER.debug(f'Отправляю сообщение {dest_cli}: {msg}')
                send_message(self.clients[dest_cli], msg)
                LOGGER.info(f'{send_cli} => {dest_cli}: {msg}')
        elif dest_cli in self.clients and self.clients[dest_cli] not in send_sock:
            LOGGER.error(f'Ошибка: {dest_cli} Пропал вслед за кораблем')
            raise ConnectionError
        else:
            LOGGER.debug(f'Отправляю {send_cli} сообщение: Пользователь {dest_cli} не найден, '
                         f'неудалось доставить: {msg[MESSAGE_TEXT]}')
            send_message(self.clients[send_cli], {
                ACTION: MESSAGE,
                TIME: time(),
                SENDER: 'SERVER',
                DESTINATION: send_cli,
                MESSAGE_TEXT: f'Пользователь {dest_cli} не найден, неудалось доставить: {msg[MESSAGE_TEXT]}'})
            LOGGER.debug(f'Пользователь {dest_cli} не найден, неудалось доставить: {send_cli} => {dest_cli}: '
                         f'{msg[MESSAGE_TEXT]}')

    @log
    def del_sock(self, sock, sock_list):
        sock_list.remove(sock)
        sock.close()

    @log
    def stop(self):
        LOGGER.info(f'Завершение работы, отключаю {len(self.cli_socks)} клиентов...')
        for client in self.cli_socks:
            self.del_sock(client, self.cli_socks)
        if self.serv_sock:
            self.serv_sock.close()
        LOGGER.info(f'Сервер остановлен')

    def init_socket(self):
        LOGGER.info(
            '=' * 40 + '[ SERVER LOG START TIME: ' + strftime("%a, %d %b %Y %H:%M:%S ]", localtime()) + '=' * 40)

        LOGGER.info(f'Сервер запущен. Слушаю IP:{self.serv_ip if self.serv_ip else "ANY"} '
                    f'PORT:{self.serv_port}')

        self.serv_sock = socket(AF_INET, SOCK_STREAM)
        self.serv_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.serv_sock.bind((self.serv_ip, self.serv_port))
        self.serv_sock.settimeout(0.5)

        self.serv_sock.listen(MAX_CONNECTIONS)

    def run(self):
        self.init_socket()
        # Ловим прерывание работы через Ctrl+C
        try:
            # Основной цикл
            while True:
                # Ждём подключения, если таймаут вышел, ловим исключение.
                try:
                    client_sock, client_address = self.serv_sock.accept()
                except OSError:
                    pass
                else:
                    LOGGER.debug(f'>>> Подключение: {client_address}')
                    self.cli_socks.append(client_sock)

                recv_data_list = []
                send_data_list = []

                # Проверяем на наличие ждущих клиентов
                try:
                    if self.cli_socks:
                        recv_data_list, send_data_list, _ = select.select(self.cli_socks, self.cli_socks, [], 0)
                except OSError:
                    pass

                # принимаем сообщения и если ошибка, исключаем клиента.
                if recv_data_list:
                    for client_with_msg in recv_data_list:
                        try:
                            recvd_msg = get_message(client_with_msg)
                            LOGGER.debug(f'Получено сообщение: {recvd_msg}')
                            if recvd_msg:
                                self.handle_connection(recvd_msg, client_with_msg)
                            else:
                                # Если получаем пустое сообщение после разрыва соединения
                                LOGGER.info(f'<<<<<< Отключился: {client_with_msg.getpeername()}')
                                if client_with_msg in self.cli_socks:
                                    self.cli_socks.remove(client_with_msg)
                        except Exception as err:
                            LOGGER.info(f'{client_with_msg.getpeername()} '
                                        f'отключился (ошибка обработки сообщения: {recvd_msg}): {err}')
                            if client_with_msg in self.cli_socks:
                                self.cli_socks.remove(client_with_msg)

                for m in self.msgs:
                    try:
                        self.handle_message(m, send_data_list)
                    except Exception as e:
                        LOGGER.info(f'{m[DESTINATION]} отключился от сервера: {e}')
                        self.del_sock(self.clients[m[DESTINATION]], self.cli_socks)
                        self.database.user_logout(m[DESTINATION])
                        del self.clients[m[DESTINATION]]
                self.msgs.clear()

        except KeyboardInterrupt:
            self.stop()


def print_help():
    print(' Поддерживаемые команды:')
    print('   u, users - отправить сообщение всем')
    print('   a, active - отправить личное сообщение')
    print('   l, loghist - запросить список собеседников')
    print('   ? или help - вывести подсказки по командам')
    print('   q или quit - выход из программы')


def main():
    database = ServerDB()
    server = Server(database)
    server.daemon = True
    server.start()
    print_help()

    while True:
        command = input('=>')
        if command.lower() in ['u', 'users']:
            for user in sorted(database.get_all_users_list()):
                print(f'Пользователь {user[0]}, последний вход: {user[1]}')
        elif command.lower() in ['a', 'active']:
            for user in sorted(database.get_active_users_list()):
                print(f'Пользователь {user[0]} [{user[1]}:{user[2]}] вошел: {user[3]}')
        elif command.lower() in ['l', 'loghist']:
            name = input('Введите имя конкретного пользователя или нажмите Enter: ')
            for user in sorted(database.get_login_history(name)):
                print(f'Пользователь {user[0]}, последний вход: {user[3]} с [{user[1]}:{user[2]}]')
        elif command.lower() in ['?', 'help']:
            print_help()
        elif command.lower() in ['q', 'quit']:
            server.stop()
            break
        else:
            print(random.choice(
                ['Хватит лохматить бабушку, пиши help', 'Не тыкай!', 'Ананимус нашелся..',
                 'Начинаю форматирование.....', 'Не твое - не трожь', 'Кому сказано, пиши help',
                 'Только для взрослых', 'И кто тебя из клетки выпустил?']))


if __name__ == '__main__':
    main()
