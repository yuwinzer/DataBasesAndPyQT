"""
1. Реализовать аутентификацию пользователей на сервере.
2. *Реализовать декоратор @login_required,
        проверяющий авторизованность пользователя для выполнения той или иной функции.
3. Реализовать хранение паролей в БД сервера
        (пароли не хранятся в открытом виде — хранится хэш-образ от пароля с добавлением криптографической соли).
4. *Реализовать возможность сквозного шифрования сообщений
        (использовать асимметричный шифр, ключи которого хранятся только у клиентов).
"""
# SERVER
import os
import sys
import dis
import select
import hmac
import binascii
import logging
import threading
import configparser
from time import time, localtime, strftime
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

sys.path.append('../')
import log.server_log_config
from common.globals import *
from common.utils import get_message, send_message, handle_parameters, is_port_bad, is_ip_bad
from log.decorator import log
from server.server_db import ServerDB

# from PyQt5.QtWidgets import QApplication, QMessageBox
# from PyQt5.QtCore import QTimer
# from server.server_gui import MainWindow, AllUsersWindow, create_all_users_model,\
#     gui_create_model, HistoryWindow, create_stat_model, ConfigWindow

# Инициализация логирования сервера.
LOGGER = logging.getLogger('server')

# Флаг, что был подключён новый пользователь, нужен чтобы не мучать BD
# постоянными запросами на обновление
# new_connection = False
conflag_lock = threading.Lock()


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


class Core(threading.Thread, metaclass=ServerVerifier):
    """Класс обработки сообщений и работы с сокетами. Принимает:
    базу данных, ip-адрес сервера, порт сервера
    """
    serv_port = CheckoutPort()

    def __init__(self, database, serv_ip, serv_port):
        self.serv_ip = serv_ip
        self.serv_port = serv_port
        self.serv_sock = None
        self.database = database
        self.cli_socks = []  # Список подключенных сокетов
        self.clients = {}  # Словарь ИМЯ:СОКЕТ подключенных сокетов
        self.msgs = []
        # self.config = config
        # self.server_app = server_app
        # self.main_window = main_window
        # self.new_connection = False
        super().__init__()
        LOGGER.info(
            '=' * 40 + '[ SERVER LOG START TIME: ' + strftime("%a, %d %b %Y %H:%M:%S ]", localtime()) + '=' * 40)

        LOGGER.info(f'Сервер запущен. Слушаю IP:{self.serv_ip if self.serv_ip else "ANY"} '
                    f'PORT:{self.serv_port}')

    @log
    def handle_connection(self, msg, cli_sock):
        """Метод обрабатывает сообщение и отправляет ответы или запускает другие методы. Принимает:
        сообщение, сокет отправитель
        """
        LOGGER.debug(f'Проверка типа сообщения: {msg}')
        if ACTION in msg:
            if TIME in msg and USER in msg:
                cli_ip, cli_port = cli_sock.getpeername()
                cli_name = msg[USER]
                # Запрос подключения
                if msg[ACTION] == PRESENCE:
                    cli_name = cli_name[ACCOUNT_NAME]
                    if cli_name in self.clients.keys():
                        LOGGER.info(f'Попытка войти с таким же именем: {cli_ip} [{cli_name}]')
                        send_message(cli_sock, {
                            RESPONSE: 400,
                            ERROR: f'Пользователь [{cli_name}] уже подключен'})
                        self.remove_client(cli_sock)
                        # cli_sock.close()
                    elif not self.database.check_user(cli_name):
                        send_message(cli_sock, {
                            RESPONSE: 400,
                            ERROR: f'Пользователь [{cli_name}] не зарегистрирован'})
                        self.remove_client(cli_sock)
                    else:
                        LOGGER.debug('Correct username, starting passwd check.')
                        # Иначе отвечаем 511 и проводим процедуру авторизации
                        # Словарь - заготовка
                        message_auth = RESPONSE_511
                        # Набор байтов в hex представлении
                        random_str = binascii.hexlify(os.urandom(64))
                        # В словарь байты нельзя, декодируем (json.dumps -> TypeError)
                        message_auth[DATA] = random_str.decode('ascii')
                        # Создаём хэш пароля и связки с рандомной строкой, сохраняем
                        # серверную версию ключа
                        hash = hmac.new(self.database.get_hash(cli_name), random_str, 'MD5')
                        digest = hash.digest()
                        LOGGER.debug(f'Auth message = {message_auth}')
                        try:
                            # Обмен с клиентом
                            send_message(cli_sock, message_auth)
                            ans = get_message(cli_sock)
                        except OSError as err:
                            LOGGER.debug('Error in auth, data:', exc_info=err)
                            cli_sock.close()
                            return
                        client_digest = binascii.a2b_base64(ans[DATA])
                        # Если ответ клиента корректный, то сохраняем его в список
                        # пользователей.
                        if RESPONSE in ans and ans[RESPONSE] == 511 and \
                                hmac.compare_digest(digest, client_digest):
                            self.clients[cli_name] = cli_sock
                            client_ip, client_port = cli_sock.getpeername()
                            try:
                                send_message(cli_sock, RESPONSE_200)
                            except OSError:
                                self.remove_client(cli_name)
                            # добавляем пользователя в список активных и,
                            # если у него изменился открытый ключ, то сохраняем новый
                            self.database.user_login(
                                cli_name,
                                cli_ip,
                                cli_port,
                                msg[USER][PUBLIC_KEY])
                            LOGGER.info(f'>>>>>> Подключился: {cli_ip} [{cli_name}]')
                        else:
                            response = RESPONSE_400
                            response[ERROR] = 'Неверный пароль.'
                            try:
                                send_message(cli_sock, response)
                            except OSError:
                                pass
                            self.remove_client(cli_sock)
                        # self.clients[cli_name] = cli_sock
                        # self.database.user_login(cli_name, cli_ip, cli_port)
                        # LOGGER.info(f'>>>>>> Подключился: {cli_ip} [{cli_name}]')
                        # send_message(cli_sock, {RESPONSE: 200})
                        # with conflag_lock:
                        #     self.new_connection = True
                    return
                # Запрос списка всех пользователей
                elif msg[ACTION] == USER_LIST:
                    LOGGER.info(f'Получен запрос списка пользователей от: {cli_ip} [{cli_name}]')
                    send_message(cli_sock, {
                        RESPONSE: 202,
                        ALERT: [user[0] for user in self.database.get_all_users_list() if user[0] != cli_name]})
                    return
                # Запрос списка активных пользователей
                elif msg[ACTION] == ONLINE:
                    LOGGER.info(f'Получен запрос списка активных пользователей от: {cli_ip} [{cli_name}]')
                    send_message(cli_sock, {
                        RESPONSE: 202,
                        ALERT: [user[0] for user in self.database.get_active_users_list() if user[0] != cli_name]})
                    # ALERT: list(self.clients.keys())})
                    return
                # Запрос списка контактов
                elif msg[ACTION] == GET_CONTACTS:
                    LOGGER.info(f'Получен запрос списка контактов от: {cli_ip} [{cli_name}]')
                    send_message(cli_sock, {
                        RESPONSE: 202,
                        ALERT: self.database.get_contacts(cli_name)})
                    return
                # Запрос на добавление/удаление контакта
                elif ACCOUNT_NAME in msg:
                    contact_name = msg[ACCOUNT_NAME]
                    if msg[ACTION] == DEL_CONTACT:
                        LOGGER.info(f'Получен запрос: {cli_ip} [{cli_name}] на удаление контакта [{contact_name}]')
                        if self.database.del_contact(cli_name, contact_name):
                            send_message(cli_sock, {RESPONSE: 200})
                        else:
                            send_message(cli_sock, {RESPONSE: 409})
                        return
                    if msg[ACTION] == ADD_CONTACT:
                        LOGGER.info(f'Получен запрос: {cli_ip} [{cli_name}] на добавление контакта [{contact_name}]')
                        if self.database.add_contact(cli_name, contact_name):
                            send_message(cli_sock, {RESPONSE: 200})
                        else:
                            send_message(cli_sock, {RESPONSE: 409})
                        return
                # Отключение
                elif msg[ACTION] == EXIT:
                    self.remove_client(cli_sock)
                    LOGGER.info(f'<<<<<< Отключился: {cli_ip} [{cli_name}]')
                    # with conflag_lock:
                    #     self.new_connection = True
                    return
            # Сообщение
            elif msg[ACTION] == MESSAGE and TIME in msg and \
                    SENDER in msg and DESTINATION in msg and MESSAGE_TEXT in msg:
                if msg[MESSAGE_TEXT]:
                    self.msgs.append(msg)
                    self.database.process_message(
                        msg[SENDER], msg[DESTINATION])
                    LOGGER.debug(f'Сообщение типа MESSAGE добавлено в обработку: {msg[MESSAGE_TEXT]}')
                return
        # Ошибки
        else:
            LOGGER.error(f'Ошибка: Не удается обработать запрос:\n{msg}')
            send_message(cli_sock, {
                RESPONSE: 400,
                ERROR: 'Bad request'})
            return

    @log
    def handle_message(self, msg, send_socks):
        """Метод обрабатывает и перенаправляет текстовое сообщение. Принимает:
        сообщение, сокеты-отправители
        """
        dest_name, in_name = msg[DESTINATION], msg[SENDER]
        LOGGER.debug(f'{dest_name=} {in_name=}')
        # Получатель задан?
        if dest_name == '':
            LOGGER.debug(f'Отправляю сообщение [ВСЕМ]: {msg}')
            for every_cli in send_socks:
                send_message(every_cli, msg)
            LOGGER.info(f'[{in_name}] => [ВСЕМ]: {msg[MESSAGE_TEXT]}')
        # Имя получателя в списке клиентов?
        elif dest_name in self.clients:
            send_message(self.clients[dest_name], msg)
            LOGGER.info(f'[{in_name}] => [{dest_name}]: {msg[MESSAGE_TEXT]}')
            # dest_sock = self.clients[dest_name]
            # # Сокет получателя в списке сокетов? -------------------
            # if dest_sock in send_socks:
            #     # LOGGER.debug(f'Отправляю сообщение [{dest_name}]: {msg}')
            #     send_message(dest_sock, msg)
            #     LOGGER.info(f'[{in_name}] => [{dest_name}]: {msg[MESSAGE_TEXT]}')
            # else:
            #     LOGGER.error(f'Ошибка: [{dest_name}] Пропал вслед за кораблем')
            #     raise ConnectionError
        else:
            LOGGER.debug(f'Отвечаю [{in_name}]: "Пользователь [{dest_name}] не найден, '
                         f'неудалось доставить: {msg[MESSAGE_TEXT]}"')
            send_message(self.clients[in_name], {
                RESPONSE: 400,
                ERROR: f'Пользователь [{dest_name}] не в сети, не удалось доставить: {msg[MESSAGE_TEXT]}'})
            LOGGER.error(f'Ошибка: Пользователь [{dest_name}] не найден, не удалось доставить: '
                         f'[{in_name}] => [{dest_name}]: {msg[MESSAGE_TEXT]}')

    @log
    def remove_client(self, sock_or_name):
        """Метод удаляет из цикла обработки (отключает от сервера) пользователя. Принимает:
        сокет или имя
        """
        # LOGGER.info(f'Отключаю сокет/пользователя: {sock_or_name}')
        if type(sock_or_name) is socket:
            if sock_or_name in self.cli_socks:
                if sock_or_name in self.clients.values():
                    what = list(self.clients.values()).index(sock_or_name)
                    print(f'{what=}')
                    user_name = list(self.clients.keys())[list(self.clients.values()).index(sock_or_name)]
                    # LOGGER.info(f'Отключаю: {user_name=}')
                    if user_name:
                        del self.clients[user_name]
                        self.database.user_logout(user_name)
                    LOGGER.info(f'Отключаю пользователя [{user_name}] и сокет {sock_or_name} удаляются')
                self.cli_socks.remove(sock_or_name)
            sock_or_name.close()
            return
        else:
            for user_name in self.clients:
                if user_name == sock_or_name:
                    user_sock = self.clients[user_name]
                    LOGGER.info(f'Отключаю пользователя [{sock_or_name}] и сокет {user_sock} удаляются')
                    self.cli_socks.remove(user_sock)
                    user_sock.close()
                    self.database.user_logout(user_name)
                    del self.clients[user_name]
                    return
        LOGGER.debug(f'Не удалось отключить: {sock_or_name}, пользователь отключен.')


    @log
    def stop(self):
        """Метод освобождает сокеты и сообщает об остановке сервера"""
        LOGGER.info(f'Завершение работы, отключаю {len(self.cli_socks)} клиентов...')
        for client in self.cli_socks:
            client.close()
        if self.serv_sock:
            self.serv_sock.close()
        LOGGER.info(f'Сервер остановлен')

    def init_socket(self):
        """Метод создает серверный сокет для работы"""
        self.serv_sock = socket(AF_INET, SOCK_STREAM)
        self.serv_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.serv_sock.bind((self.serv_ip, self.serv_port))
        self.serv_sock.settimeout(0.5)

        self.serv_sock.listen(MAX_CONNECTIONS)

    def service_update_lists(self):
        """Метод реализующий отправки сервисного сообщения 205 клиентам"""
        for client in self.clients:
            try:
                send_message(self.clients[client], RESPONSE_205)
            except OSError:
                self.remove_client(self.clients[client])

    def run(self):
        """Метод основного цикла, получает и распределяет сообщения"""
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
                                self.remove_client(client_with_msg)
                        except Exception as err:
                            LOGGER.error(f'{client_with_msg.getpeername()} '
                                         f'отключился (ошибка сервера или обработки сообщения): {err}')
                            self.remove_client(client_with_msg)

                for m in self.msgs:
                    try:
                        self.handle_message(m, send_data_list)
                    except Exception as e:
                        LOGGER.info(f'{m[DESTINATION]} отключился от сервера: {e}')
                        self.remove_client(self.clients[m[DESTINATION]])
                self.msgs.clear()

        except KeyboardInterrupt:
            self.stop()

# def main():
#     # Загрузка файла конфигурации сервера
#     config = configparser.ConfigParser()
#
#     dir_path = os.path.dirname(os.path.realpath(__file__)) + '/server'
#     config.read(f"{dir_path}/{'server.ini'}")
#
#     # Загрузка параметров командной строки, если нет параметров, то задаём
#     # значения по умоланию.
#     listen_ip, listen_port, _ = handle_parameters(
#         config['SETTINGS']['listen_address'], config['SETTINGS']['default_port'])
#
#     # Инициализация базы данных
#     database = ServerDB(
#         os.path.join(
#             config['SETTINGS']['database_path'],
#             config['SETTINGS']['database_file']))
#     # client = ServerDB('client/server_base.db3')
#
#     # Создание экземпляра класса - сервера и его запуск:
#     server = Server(database, listen_ip, listen_port)
#     server.daemon = True
#     server.start()
#
#     # Создаём графическое окружение для сервера:
#     # server_app = QApplication(sys.argv)
#     # main_window = MainWindow()
#
#     # Инициализируем параметры в окна
#     main_window.statusBar().showMessage('Server Working')
#     main_window.active_clients_table.setModel(gui_create_model(database))
#     main_window.active_clients_table.resizeColumnsToContents()
#     main_window.active_clients_table.resizeRowsToContents()
#
#
#
#     # Таймер, обновляющий список клиентов 1 раз в 2 секунд
#     timer = QTimer()
#     timer.timeout.connect(list_update)
#     timer.start(2000)
#
#     # Связываем кнопки с процедурами
#     main_window.all_users_button.triggered.connect(show_all_users)
#     main_window.show_history_button.triggered.connect(show_statistics)
#     main_window.config_btn.triggered.connect(server_config)
#
#     # Запускаем GUI
#     server_app.exec_()

# print_help()
#
# while True:
#     command = input('=>')
#     if command.lower() in ['u', 'users']:
#         for user in sorted(client.get_all_users_list()):
#             print(f'Пользователь [{user[0]}], последний вход: {user[1]}')
#     elif command.lower() in ['a', 'active']:
#         for user in sorted(client.get_active_users_list()):
#             print(f'Пользователь [{user[0]}] [{user[1]}:{user[2]}] вошел: {user[3]}')
#     elif command.lower() in ['l', 'loghist']:
#         name = input('Введите имя конкретного пользователя или нажмите Enter: ')
#         for user in sorted(client.get_login_history(name)):
#             print(f'Пользователь [{user[0]}], последний вход: {user[3]} с [{user[1]}:{user[2]}]')
#     elif command.lower() in ['s', 'stat']:
#         name = input('Введите имя конкретного пользователя или нажмите Enter: ')
#         for data in sorted(client.get_user_stat(name)):
#             print(f'Пользователь [{data[0]}], последний вход: {data[1]} '
#                   f'сообщений отправлено: {data[2]} получено: {data[3]}]')
#     elif command.lower() in ['?', 'help']:
#         print_help()
#     elif command.lower() in ['q', 'quit']:
#         server.stop()
#         break
#     else:
#         print(random.choice(
#             ['Хватит лохматить бабушку, пиши help', 'Не тыкай!', 'Ананимус нашелся..',
#              'Начинаю форматирование.....', 'Не твое - не трожь', 'Кому сказано, пиши help',
#              'Только для взрослых', 'И кто тебя из клетки выпустил?']))
#
#
# if __name__ == '__main__':
#     main()
