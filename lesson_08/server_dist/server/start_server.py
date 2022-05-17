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
# import dis
# import select
import threading
import configparser
import log.server_log_config

# from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from common.globals import *
from common.utils import handle_parameters
# from time import time, localtime, strftime
from log.decorator import log
from server.server_db import ServerDB
from server.server_core import Core

from PyQt5.QtWidgets import QApplication, QMessageBox
# from PyQt5.QtCore import QTimer
from server.server_gui import MainWindow

# Инициализация логирования сервера.
LOGGER = logging.getLogger('server')

# Флаг, что был подключён новый пользователь, нужен чтобы не мучать BD
# постоянными запросами на обновление
new_connection = False
conflag_lock = threading.Lock()


def main():
    # Загрузка файла конфигурации сервера
    config = configparser.ConfigParser()

    dir_path = os.path.dirname(os.path.realpath(__file__)) + '/server'
    config.read(f"{dir_path}/{'server.ini'}")

    # Загрузка параметров командной строки, если нет параметров, то задаём
    # значения по умоланию.
    if 'SETTINGS' in config:
        pass
    else:
        config.add_section('SETTINGS')
        config.set('SETTINGS', 'listen_port', str(DEF_PORT))
        config.set('SETTINGS', 'listen_ip', '')
        config.set('SETTINGS', 'database_path', 'server/')
        config.set('SETTINGS', 'database_file', 'server.db3')

    listen_ip, listen_port, _, _ = handle_parameters(
        config['SETTINGS']['listen_ip'], config['SETTINGS']['listen_port'])

    # Инициализация базы данных
    database = ServerDB(
        os.path.join(
            config['SETTINGS']['database_path'],
            config['SETTINGS']['database_file']))
    # client = ServerDB('client/server_base.db3')

    # server_app = QApplication(sys.argv)
    # main_window = MainWindow()

    # Создание экземпляра класса - сервера и его запуск:
    server = Core(database, listen_ip, listen_port)
    server.daemon = True
    server.start()

    # Создаём графическое окружение для сервера:
    server_qapp = QApplication(sys.argv)
    main_window = MainWindow(database, server, config)
    # server_app = QApplication(sys.argv)
    # main_window = MainWindow()



    # # Функция, обновляющая список подключённых, проверяет флаг подключения, и
    # # если надо обновляет список
    # def list_update():
    #     global new_connection
    #     if new_connection:
    #         main_window.active_clients_table.setModel(
    #             gui_create_model(database))
    #         main_window.active_clients_table.resizeColumnsToContents()
    #         main_window.active_clients_table.resizeRowsToContents()
    #         with conflag_lock:
    #             new_connection = False
    #
    # # Функция, создающая окно со статистикой клиентов
    # def show_all_users():
    #     global all_users_window
    #     all_users_window = AllUsersWindow()
    #     all_users_window.all_users_table.setModel(create_all_users_model(database))
    #     all_users_window.all_users_table.resizeColumnsToContents()
    #     all_users_window.all_users_table.resizeRowsToContents()
    #     all_users_window.show()
    #
    # # Функция, создающая окно со статистикой клиентов
    # def show_statistics():
    #     global stat_window
    #     stat_window = HistoryWindow()
    #     stat_window.history_table.setModel(create_stat_model(database))
    #     stat_window.history_table.resizeColumnsToContents()
    #     stat_window.history_table.resizeRowsToContents()
    #     stat_window.show()
    #
    # # Функция создающяя окно с настройками сервера.
    # def server_config():
    #     global config_window
    #     # Создаём окно и заносим в него текущие параметры
    #     config_window = ConfigWindow()
    #     config_window.db_path.insert(config['SETTINGS']['database_path'])
    #     config_window.db_file.insert(config['SETTINGS']['database_file'])
    #     config_window.port.insert(config['SETTINGS']['default_port'])
    #     config_window.ip.insert(config['SETTINGS']['listen_address'])
    #     config_window.save_btn.clicked.connect(save_server_config)
    #
    # # Функция сохранения настроек
    # def save_server_config():
    #     global config_window
    #     info_message = QMessageBox()
    #     config['SETTINGS']['database_path'] = config_window.db_path.text()
    #     config['SETTINGS']['database_file'] = config_window.db_file.text()
    #
    #     port = config_window.port.text()
    #     if is_port_bad(port):
    #         info_message.warning(config_window, 'Ошибка', f'Полученный PORT: {port} должен быть в пределах 1024-65535')
    #         return
    #     ip = config_window.ip.text()
    #     if is_ip_bad(ip):
    #         info_message.warning(config_window, 'Ошибка', f'Полученный IP: {ip} должен иметь формат: 127.0.0.1 ')
    #         return
    #
    #     # Если порт и ip в норме - сохраняем
    #     config['SETTINGS']['listen_address'] = ip
    #     config['SETTINGS']['default_port'] = port
    #     with open('server.ini', 'w') as conf:
    #         config.write(conf)
    #         info_message.information(
    #             config_window, 'OK', 'Настройки успешно сохранены!')

    # Таймер, обновляющий список клиентов 1 раз в 2 секунд


    # Запускаем GUI
    server_qapp.exec_()

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
