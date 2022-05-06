"""
1. Реализовать графический интерфейс пользователя на стороне клиента:
        a. Отображение списка контактов;
        b. Выбор чата двойным кликом на элементе списка контактов;
        c. Добавление нового контакта в локальный список контактов;
        d. Отображение сообщений в окне чата;
        e. Набор сообщения в окне ввода сообщения;
        f. Отправка введенного сообщения.
"""

# CLIENT
import dis
import json
import sys
import threading
from PyQt5.QtWidgets import QApplication, QWidget
from time import time, sleep, strftime, localtime
# from socket import socket, AF_INET, SOCK_STREAM
from common.globals import *
from common.utils import send_message, get_message, handle_parameters
# from common.errors import ReqFieldMissingError, ServerError
import logging
from log.decorator import log
from client.client_db import ClientDB
from client.login_dialog import LoginWindow
from client.main_window import ClientMainWindow
from client.transport import ClientTransport
# from client.main_window_ui import Ui_MainWindow

LOGGER = logging.getLogger('client')

# Объект блокировки сокета и работы с базой данных
sock_lock = threading.Lock()
database_lock = threading.Lock()


# @log
# def create_presence_message(sock, acc_name):
#     # Формирование простых сообщения PRESENCE
#     LOGGER.debug(f'Сформировано "PRESENCE" сообщение для сервера')
#     msg = {
#         ACTION: PRESENCE,
#         TIME: time(),
#         USER: {
#             ACCOUNT_NAME: acc_name
#         }
#     }
#     send_message(sock, msg)
#     ans = get_message(sock)
#     if RESPONSE in ans and ans[RESPONSE] == 200:
#         LOGGER.debug(f'Ответ сервера: "OK"')
#         return True
#     LOGGER.error(f'Ответ сервера: {ans}')
#

# def load_database(user_name, database, sock):
#     sender = ClientSender(user_name, database, sock)
#     try:
#         users_list = sender.create_service_message(user_name, USER_LIST)
#     except Exception as err:
#         LOGGER.error(f'Ошибка запроса списка пользователей: {err}')
#     else:
#         if users_list:
#             database.update_users(users_list)
#     try:
#         contacts_list = sender.create_service_message(user_name, GET_CONTACTS)
#     except Exception as err:
#         LOGGER.error(f'Ошибка запроса списка контактов: {err}')
#     else:
#         if contacts_list:
#             for contact in contacts_list:
#                 database.add_contact(contact)
#     LOGGER.debug(f'База успешно загружена с сервера')


if __name__ == '__main__':
    LOGGER.debug('=' * 40 + '[ CLIENT LOG START TIME: ' + strftime("%a, %d %b %Y %H:%M:%S ]", localtime()) + '=' * 40)
    try:
        # Загружаем параметы коммандной строки
        serv_ip, serv_port, acc_name = handle_parameters(ip=DEF_IP, port=DEF_PORT)

        # Создаём клиентокое приложение
        client_app = QApplication(sys.argv)

        knock = 0
        for knock in range(5):

            # Требуем имя
            if not acc_name:
                login_dialog = LoginWindow()
                # login_dialog.setupUi(Ui_UserLoginDialog)
                client_app.exec_()
                # Если пользователь ввёл имя и нажал ОК, то сохраняем ведённое и удаляем объект.
                # Иначе - выходим
                if login_dialog.enter:
                    acc_name = login_dialog.login_window.LoginLE.text()
                    del login_dialog
                else:
                    exit(0)

        # # Если не удалось ввести имя или подключиться 5 раз - расходимся
        # if knock == 4:
        #     print('К сожалению подключиться не удалось. Попробуйте позже.')
        #     LOGGER.debug(f'Сервер не отвечает {serv_ip}:{serv_port}. Завершение работы.')
        #     sys.exit(0)
        # LOGGER.info(f'Клиент запущен. Использую SERVER IP:{serv_ip} PORT:{serv_port} NAME:{acc_name}')

        # Инициализация БД
        db_path = f'client/{acc_name}.db3'
        try:
            database = ClientDB(db_path)
        except Exception as e:
            LOGGER.critical(f'Не удается найти/создать базу "{db_path}" Причина: {e}')
        # load_database(acc_name, database, my_sock)

        try:
            transport = ClientTransport(database, acc_name, serv_ip, serv_port)
        except Exception as err:
            LOGGER.error(f'Ошибка при запуске клиента: {err}')
            exit(1)
        transport.setDaemon(True)
        transport.start()
        sleep(0.2)

        # Создаём GUI
        main_window = ClientMainWindow(database, transport)
        main_window.make_connection(transport)
        main_window.setWindowTitle(f'Чат Программа alpha release - {acc_name}')
        client_app.exec_()

        # Раз графическая оболочка закрылась, закрываем транспорт
        transport.exit()
        transport.join()

        # thread_receiver = ClientReader(acc_name, database, my_sock)
        # thread_receiver.daemon = True
        # thread_receiver.start()
        # LOGGER.debug('Запущен процесс получатель')
        #
        # thread_sender_ui = ClientSender(acc_name, database, my_sock)
        # thread_sender_ui.daemon = True
        # thread_sender_ui.start()
        # LOGGER.debug('Запущен процесс интерфейс и отправщик')
        #
        # while thread_receiver.is_alive() and thread_sender_ui.is_alive():
        #     sleep(1)

    except KeyboardInterrupt:
        LOGGER.info(f'Завершение работы клиента')
        # my_sock.close()
        LOGGER.info(f'Клиент остановлен')
        sys.exit(1)
