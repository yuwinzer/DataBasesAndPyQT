"""
1. Начать реализацию класса «Хранилище» для серверной стороны. Хранение необходимо осуществлять в базе данных. В качестве СУБД использовать sqlite. Для взаимодействия с БД можно применять ORM.
"""
# SERVER
import os
import sys
import dis
import select
import threading
import configparser
import log.server_log_config

from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from common.globals import *
from common.utils import get_message, send_message, handle_parameters, is_port_bad, is_ip_bad
from time import time, localtime, strftime
from log.decorator import log
from server.server_db import ServerDB

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
from server.server_gui import MainWindow, AllUsersWindow, create_all_users_model,\
    gui_create_model, HistoryWindow, create_stat_model, ConfigWindow

# Инициализация логирования сервера.
LOGGER = logging.getLogger('server')

# Флаг, что был подключён новый пользователь, нужен чтобы не мучать BD
# постоянными запросами на обновление
new_connection = False
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


class Server(threading.Thread, metaclass=ServerVerifier):
    serv_port = CheckoutPort()

    def __init__(self, database, serv_ip, serv_port):
        self.serv_ip = serv_ip
        self.serv_port = serv_port
        self.serv_sock = None
        self.database = database
        self.cli_socks = []  # Список подключенных сокетов
        self.clients = {}  # Словарь ИМЯ:СОКЕТ подключенных сокетов
        self.msgs = []
        super().__init__()

    @log
    def handle_connection(self, msg, cli_sock):
        global new_connection
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
                        self.cli_socks.remove(cli_sock)
                        cli_sock.close()
                    else:
                        self.clients[cli_name] = cli_sock
                        self.database.user_login(cli_name, cli_ip, cli_port)
                        LOGGER.info(f'>>>>>> Подключился: {cli_ip} [{cli_name}]')
                        send_message(cli_sock, {RESPONSE: 200})
                        with conflag_lock:
                            new_connection = True
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
                    self.del_sock(cli_sock, self.cli_socks)
                    self.database.user_logout(cli_name)
                    LOGGER.info(f'<<<<<< Отключился: {cli_ip} [{cli_name}]')
                    del self.clients[cli_name]
                    with conflag_lock:
                        new_connection = True
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
    def handle_message(self, msg, send_sock):
        dest_cli, send_cli = msg[DESTINATION], msg[SENDER]
        LOGGER.debug(f'{dest_cli=} {send_cli=}')
        if dest_cli == '':
            LOGGER.debug(f'Отправляю сообщение [ВСЕМ]: {msg}')
            for every_cli in send_sock:
                send_message(every_cli, msg)
            LOGGER.info(f'[{send_cli}] => [ВСЕМ]: {msg[MESSAGE_TEXT]}')
        elif dest_cli in self.clients and self.clients[dest_cli] in send_sock:
            LOGGER.debug(f'Отправляю сообщение [{dest_cli}]: {msg}')
            send_message(self.clients[dest_cli], msg)
            LOGGER.info(f'[{send_cli}] => [{dest_cli}]: {msg[MESSAGE_TEXT]}')
        elif dest_cli in self.clients and self.clients[dest_cli] not in send_sock:
            LOGGER.error(f'Ошибка: [{dest_cli}] Пропал вслед за кораблем')
            raise ConnectionError
        else:
            LOGGER.debug(f'Отправляю [{send_cli}] сообщение: "Пользователь [{dest_cli}] не найден, '
                         f'неудалось доставить: {msg[MESSAGE_TEXT]}"')
            send_message(self.clients[send_cli], {
                ACTION: MESSAGE,
                TIME: time(),
                SENDER: 'SERVER',
                DESTINATION: send_cli,
                MESSAGE_TEXT: f'Пользователь [{dest_cli}] не найден, неудалось доставить: {msg[MESSAGE_TEXT]}'})
            LOGGER.debug(f'Пользователь [{dest_cli}] не найден, неудалось доставить: [{send_cli}] => [{dest_cli}]: '
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
                                    user_name = list(self.clients.keys())[
                                        list(self.clients.values()).index(client_with_msg)]
                                    del self.clients[user_name]
                                    self.database.user_logout(user_name)
                                    self.cli_socks.remove(client_with_msg)
                        except Exception as err:
                            LOGGER.error(f'{client_with_msg.getpeername()} '
                                        f'отключился (ошибка обработки сообщения: {recvd_msg}): {err}')
                            if client_with_msg in self.cli_socks:
                                user_name = list(self.clients.keys())[
                                    list(self.clients.values()).index(client_with_msg)]
                                del self.clients[user_name]
                                self.database.user_logout(user_name)
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
    print('   s, stat - запросить статистику сообщений собеседников')
    print('   ? или help - вывести подсказки по командам')
    print('   q или quit - выход из программы')


def main():
    # Загрузка файла конфигурации сервера
    config = configparser.ConfigParser()

    dir_path = os.path.dirname(os.path.realpath(__file__)) + '/server'
    config.read(f"{dir_path}/{'server.ini'}")

    # Загрузка параметров командной строки, если нет параметров, то задаём
    # значения по умоланию.
    listen_ip, listen_port, _ = handle_parameters(
        config['SETTINGS']['listen_address'], config['SETTINGS']['default_port'])

    # Инициализация базы данных
    database = ServerDB(
        os.path.join(
            config['SETTINGS']['database_path'],
            config['SETTINGS']['database_file']))
    # client = ServerDB('client/server_base.db3')

    # Создание экземпляра класса - сервера и его запуск:
    server = Server(database, listen_ip, listen_port)
    server.daemon = True
    server.start()

    # Создаём графическое окружение для сервера:
    server_app = QApplication(sys.argv)
    main_window = MainWindow()

    # Инициализируем параметры в окна
    main_window.statusBar().showMessage('Server Working')
    main_window.active_clients_table.setModel(gui_create_model(database))
    main_window.active_clients_table.resizeColumnsToContents()
    main_window.active_clients_table.resizeRowsToContents()

    # Функция, обновляющая список подключённых, проверяет флаг подключения, и
    # если надо обновляет список
    def list_update():
        global new_connection
        if new_connection:
            main_window.active_clients_table.setModel(
                gui_create_model(database))
            main_window.active_clients_table.resizeColumnsToContents()
            main_window.active_clients_table.resizeRowsToContents()
            with conflag_lock:
                new_connection = False

    # Функция, создающая окно со статистикой клиентов
    def show_all_users():
        global all_users_window
        all_users_window = AllUsersWindow()
        all_users_window.all_users_table.setModel(create_all_users_model(database))
        all_users_window.all_users_table.resizeColumnsToContents()
        all_users_window.all_users_table.resizeRowsToContents()
        all_users_window.show()

    # Функция, создающая окно со статистикой клиентов
    def show_statistics():
        global stat_window
        stat_window = HistoryWindow()
        stat_window.history_table.setModel(create_stat_model(database))
        stat_window.history_table.resizeColumnsToContents()
        stat_window.history_table.resizeRowsToContents()
        stat_window.show()

    # Функция создающяя окно с настройками сервера.
    def server_config():
        global config_window
        # Создаём окно и заносим в него текущие параметры
        config_window = ConfigWindow()
        config_window.db_path.insert(config['SETTINGS']['database_path'])
        config_window.db_file.insert(config['SETTINGS']['database_file'])
        config_window.port.insert(config['SETTINGS']['default_port'])
        config_window.ip.insert(config['SETTINGS']['listen_address'])
        config_window.save_btn.clicked.connect(save_server_config)

    # Функция сохранения настроек
    def save_server_config():
        global config_window
        info_message = QMessageBox()
        config['SETTINGS']['database_path'] = config_window.db_path.text()
        config['SETTINGS']['database_file'] = config_window.db_file.text()

        port = config_window.port.text()
        if is_port_bad(port):
            info_message.warning(config_window, 'Ошибка', f'Полученный PORT: {port} должен быть в пределах 1024-65535')
            return
        ip = config_window.ip.text()
        if is_ip_bad(ip):
            info_message.warning(config_window, 'Ошибка', f'Полученный IP: {ip} должен иметь формат: 127.0.0.1 ')
            return

        # Если порт и ip в норме - сохраняем
        config['SETTINGS']['listen_address'] = ip
        config['SETTINGS']['default_port'] = port
        with open('server.ini', 'w') as conf:
            config.write(conf)
            info_message.information(
                config_window, 'OK', 'Настройки успешно сохранены!')

    # Таймер, обновляющий список клиентов 1 раз в 2 секунд
    timer = QTimer()
    timer.timeout.connect(list_update)
    timer.start(2000)

    # Связываем кнопки с процедурами
    main_window.all_users_button.triggered.connect(show_all_users)
    main_window.show_history_button.triggered.connect(show_statistics)
    main_window.config_btn.triggered.connect(server_config)

    # Запускаем GUI
    server_app.exec_()

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


if __name__ == '__main__':
    main()
