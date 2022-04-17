"""
2. Реализовать метакласс ServerVerifier, выполняющий базовую проверку класса «Сервер»:
○ отсутствие вызовов connect для сокетов;
○ использование сокетов для работы по TCP.

3. Реализовать дескриптор для класса серверного сокета, а в нем — проверку номера порта. Это
должно быть целое число (>=0). Значение порта по умолчанию равняется 7777. Дескриптор
надо создать в отдельном классе. Его экземпляр добавить в пределах класса серверного
сокета. Номер порта передается в экземпляр дескриптора при запуске сервера.
"""
# SERVER
import dis
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from common.globals import DEF_PORT, ACTION, PRESENCE, TIME, USER, ACCOUNT_NAME, SENDER, DESTINATION, \
    RESPONSE, ERROR, EXIT, ONLINE, MAX_CONNECTIONS, MESSAGE, MESSAGE_TEXT
from common.utils import get_message, send_message, handle_parameters
from time import time, localtime, strftime
import logging
import select
import log.server_log_config
from log.decorator import log

LOGGER = logging.getLogger('server')


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


class Server(metaclass=ServerVerifier):

    listen_port = CheckoutPort()

    @log
    def handle_connection(self, msg, cli_sock, cli_ip, msg_list, clients, cli_socks):
        LOGGER.debug(f'Проверка типа сообщения: {msg}')
        # Запрос подключения
        if ACTION in msg:
            if TIME in msg and USER in msg:
                cli_name = msg[USER][ACCOUNT_NAME]
                if msg[ACTION] == PRESENCE:
                    if cli_name in clients.keys():
                        LOGGER.info(f'Имя занято: {cli_ip} {cli_name}')
                        send_message(cli_sock, {
                            RESPONSE: 400,
                            ERROR: f'Имя {cli_name} уже занято'})
                        cli_socks.remove(cli_sock)
                        cli_sock.close()
                    else:
                        clients[cli_name] = cli_sock
                        LOGGER.info(f'>>>>>> Подключился: {cli_ip} {cli_name}')
                        send_message(cli_sock, {RESPONSE: 200})
                    return
        # Запрос списка пользователей
                elif msg[ACTION] == ONLINE:
                    LOGGER.info(f'Получен запрос списка собеседников от: {cli_ip} {cli_name}')
                    send_message(clients[cli_name], {
                        ACTION: MESSAGE,
                        TIME: time(),
                        SENDER: 'SERVER',
                        DESTINATION: cli_name,
                        MESSAGE_TEXT: f'{" ".join(clients.keys())}'})
                    return
        # Сообщение
            elif msg[ACTION] == MESSAGE and TIME in msg and \
                    SENDER in msg and DESTINATION in msg and MESSAGE_TEXT in msg:
                if msg[MESSAGE_TEXT]:
                    msg_list.append(msg)
                    LOGGER.debug(f'Сообщение типа MESSAGE добавлено в обработку: {msg[MESSAGE_TEXT]}')
                return
        # Отключение
            elif msg[ACTION] == EXIT and ACCOUNT_NAME in msg:
                LOGGER.info(f'<<<<<< Отключился: {cli_ip} {msg[ACCOUNT_NAME]}')
                self.del_sock(cli_sock, cli_socks)
                del clients[msg[ACCOUNT_NAME]]
                return
        # Ошибки
        else:
            LOGGER.error(f'Ошибка: Не удается обработать запрос:\n{msg}')
            send_message(cli_sock, {
                RESPONSE: 400,
                ERROR: 'Bad request'})
            return

    @log
    def del_sock(self, sock, sock_list):
        sock_list.remove(sock)
        sock.close()

    @log
    def handle_message(self, msg, clients, cli_socks):
        dest_cli, send_cli = msg[DESTINATION], msg[SENDER]
        LOGGER.debug(f'{dest_cli=} {send_cli=}')
        if dest_cli == '':
            for every_cli in cli_socks:
                LOGGER.debug(f'Отправляю сообщение ВСЕМ: {msg}')
                send_message(every_cli, msg)
            LOGGER.info(f'{send_cli}: {msg}')
        elif dest_cli in clients and clients[dest_cli] in cli_socks:
                LOGGER.debug(f'Отправляю сообщение {dest_cli}: {msg}')
                send_message(clients[dest_cli], msg)
                LOGGER.info(f'{send_cli} => {dest_cli}: {msg}')
        elif dest_cli in clients and clients[dest_cli] not in cli_socks:
            LOGGER.error(f'Ошибка: {dest_cli} Пропал вслед за кораблем')
            raise ConnectionError
        else:
            LOGGER.debug(f'Отправляю {send_cli} сообщение: Пользователь {dest_cli} не найден, '
                         f'неудалось доставить: {msg[MESSAGE_TEXT]}')
            send_message(clients[send_cli], {
                ACTION: MESSAGE,
                TIME: time(),
                SENDER: 'SERVER',
                DESTINATION: send_cli,
                MESSAGE_TEXT: f'Пользователь {dest_cli} не найден, неудалось доставить: {msg[MESSAGE_TEXT]}'})
            LOGGER.debug(f'Пользователь {dest_cli} не найден, неудалось доставить: {send_cli} => {dest_cli}: '
                         f'{msg[MESSAGE_TEXT]}')

    def main_loop(self):
        LOGGER.debug('=' * 40 + '[ SERVER LOG START TIME: ' + strftime("%a, %d %b %Y %H:%M:%S ]", localtime()) + '=' * 40)
        listen_address, self.listen_port, _ = handle_parameters(ip='', port=DEF_PORT)
        LOGGER.info(f'Сервер запущен. Слушаю IP:{listen_address if listen_address else "ANY"} '
                    f'PORT:{self.listen_port}')

        serv_sock = socket(AF_INET, SOCK_STREAM)
        serv_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        serv_sock.bind((listen_address, self.listen_port))
        serv_sock.settimeout(0.5)
        cli_socks = []
        clients = {}
        msgs = []
        client_address = ''

        serv_sock.listen(MAX_CONNECTIONS)
        try:
            while True:
                # Ждём подключения, если таймаут вышел, ловим исключение.
                try:
                    client_sock, client_address = serv_sock.accept()
                except OSError:
                    pass
                else:
                    LOGGER.debug(f'>>> Подключение: {client_address}')
                    cli_socks.append(client_sock)

                recv_data_list = []
                send_data_list = []

                # Проверяем на наличие ждущих клиентов
                try:
                    if cli_socks:
                        recv_data_list, send_data_list, _ = select.select(cli_socks, cli_socks, [], 0)
                except OSError:
                    pass

                # принимаем сообщения и если ошибка, исключаем клиента.
                if recv_data_list:
                    for client_with_msg in recv_data_list:
                        try:
                            recvd_msg = get_message(client_with_msg)
                            LOGGER.info(f'Получено сообщение: {recvd_msg}')
                            if recvd_msg:
                                self.handle_connection(recvd_msg, client_with_msg, client_address,
                                                  msgs, clients, cli_socks)
                            else:
                                # Если получаем пустое сообщение после разрыва соединения
                                LOGGER.info(f'<<<<<< Отключился: {client_with_msg.getpeername()}')
                                if client_with_msg in cli_socks:
                                    cli_socks.remove(client_with_msg)
                        except Exception as err:
                            LOGGER.info(f'{client_with_msg.getpeername()} '
                                        f'отключился (ошибка обработки сообщения: {recvd_msg}): {err}')
                            if client_with_msg in cli_socks:
                                cli_socks.remove(client_with_msg)

                for m in msgs:
                    try:
                        self.handle_message(m, clients, send_data_list)
                    except Exception as e:
                        LOGGER.info(f'{m[DESTINATION]} отключился от сервера: {e}')
                        self.del_sock(clients[m[DESTINATION]], cli_socks)
                        del clients[m[DESTINATION]]
                msgs.clear()

        except KeyboardInterrupt:
            LOGGER.info(f'Завершение работы, отключаю {len(cli_socks)} клиентов...')
            for client in cli_socks:
                self.del_sock(client, cli_socks)
            serv_sock.close()
            LOGGER.info(f'Сервер остановлен')


def main():
    server = Server()
    server.main_loop()


if __name__ == '__main__':
    main()
