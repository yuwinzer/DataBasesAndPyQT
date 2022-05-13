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
import json
import sys
import threading
import hashlib
import hmac
import binascii
import logging
import log.client_log_config
from PyQt5.QtCore import pyqtSignal, QObject
from time import time, sleep, strftime, localtime
from socket import socket, AF_INET, SOCK_STREAM

from common.globals import *
from common.utils import send_message, get_message, handle_parameters
from common.errors import ReqFieldMissingError, ServerError
from log.decorator import log

LOGGER = logging.getLogger('client')

# Объект блокировки сокета и работы с базой данных
sock_lock = threading.Lock()
database_lock = threading.Lock()


# Метакласс
# class ClientVerifier(type):
#     def __init__(cls, name, parent, attrs):
#         attrs_required = ['get_message', 'send_message', 'accept', 'listen', 'socket']
#         attrs_not_allowed = []
#         required_present = False
#         for attr in attrs:
#             try:
#                 decompiled = dis.get_instructions(attrs[attr])
#             except TypeError:
#                 pass
#             else:
#                 for i in decompiled:
#                     if i.opname == 'LOAD_GLOBAL':
#                         if i.argval in attrs_required:
#                             required_present = True
#                         if i.argval in attrs_not_allowed:
#                             raise Exception(f'В классе {name} используется недопустимое: {i.argval}')
#         if not required_present:
#             raise Exception(f'В классе {name} отсутствует необходимое: {attrs_required}')
#         super().__init__(name, parent, attrs)


class ClientTransport(threading.Thread, QObject):
    # Сигналы новое сообщение и потеря соединения
    new_message = pyqtSignal(str)
    message_205 = pyqtSignal()
    connection_lost = pyqtSignal()
    show_message = pyqtSignal(str)

    def __init__(self, database, acc_name, acc_pwd, serv_ip, serv_port, keys):  # database, acc_name, serv_ip, serv_port
        # Вызываем конструктор предка
        threading.Thread.__init__(self)
        QObject.__init__(self)

        # Класс База данных - работа с базой
        self.database = database
        # Имя пользователя
        self.acc_name = acc_name
        # Пароль
        self.acc_pwd = acc_pwd
        # Сокет для работы с сервером
        self.transport = None
        # Набор ключей для шифрования
        self.keys = keys
        # Устанавливаем соединение:
        self.connection_init(serv_ip, serv_port)
        # Обновляем таблицы известных пользователей и контактов
        try:
            self.update_db_list(USER_LIST)
            self.update_db_list(GET_CONTACTS)
        except OSError as err:
            if err.errno:
                LOGGER.critical(f'Потеряно соединение с сервером.')
                raise ServerError('Потеряно соединение с сервером!')
            LOGGER.error('Timeout соединения при обновлении списков пользователей.')
        except json.JSONDecodeError:
            LOGGER.critical(f'Потеряно соединение с сервером.')
            raise ServerError('Потеряно соединение с сервером!')
        # Флаг продолжения работы транспорта.
        self.running = True

    def connection_init(self, serv_ip, serv_port):

        try:
            self.transport = socket(AF_INET, SOCK_STREAM)
            self.transport.settimeout(5)

            connected = False
            for knock in range(5):
                # Если имя подходит, создаем подключение
                try:
                    LOGGER.debug(f'[{self.acc_name}]: Попытка соедиения...')
                    self.transport.connect((serv_ip, serv_port))
                    LOGGER.debug(f'Соединение установлено.')
                    connected = True
                    break
                except (ConnectionRefusedError, ConnectionError, OSError):
                    LOGGER.debug(f'Сервер не отвечает {serv_ip}:{serv_port}')
                sleep(1)

            # Если не удалось ввести имя или подключиться 5 раз - расходимся
            if not connected:
                LOGGER.debug(f'Сервер не отвечает {serv_ip}:{serv_port}. Завершение работы.')
                sys.exit(0)

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
            LOGGER.info(f'Клиент запущен. Использую SERVER IP:{serv_ip} PORT:{serv_port} NAME:{self.acc_name}')
            # Запускаем процедуру авторизации
            # Получаем хэш пароля
            passwd_bytes = self.acc_pwd.encode('utf-8')
            salt = self.acc_name.lower().encode('utf-8')
            passwd_hash = hashlib.pbkdf2_hmac('sha512', passwd_bytes, salt, 10000)
            passwd_hash_string = binascii.hexlify(passwd_hash)

            LOGGER.debug(f'Passwd hash ready: {passwd_hash_string}')

            # Получаем публичный ключ и декодируем его из байтов
            pubkey = self.keys.publickey().export_key().decode('ascii')

            # Авторизируемся на сервере

            # if self.create_presence_message(self.transport):
            # LOGGER.debug(f'Сервер успешно уведомлен о присутствии')
            with sock_lock:
                presense = {
                    ACTION: PRESENCE,
                    TIME: time(),
                    USER: {
                        ACCOUNT_NAME: self.acc_name,
                        PUBLIC_KEY: pubkey
                    }
                }
                LOGGER.debug(f"Presense message = {presense}")
                # Отправляем серверу приветственное сообщение.
                try:
                    send_message(self.transport, presense)
                    ans = get_message(self.transport)
                    LOGGER.debug(f'Server response = {ans}.')
                    # Если сервер вернул ошибку, бросаем исключение.
                    if RESPONSE in ans:
                        if ans[RESPONSE] == 400:
                            self.show_message.emit(ans[ERROR])
                            raise ServerError(ans[ERROR])
                        elif ans[RESPONSE] == 511:
                            # Если всё нормально, то продолжаем процедуру
                            # авторизации.
                            ans_data = ans[DATA]
                            hash = hmac.new(passwd_hash_string, ans_data.encode('utf-8'), 'MD5')
                            digest = hash.digest()
                            my_ans = RESPONSE_511
                            my_ans[DATA] = binascii.b2a_base64(
                                digest).decode('ascii')
                            send_message(self.transport, my_ans)
                            self.process_server_ans(get_message(self.transport))
                except (OSError, json.JSONDecodeError) as err:
                    LOGGER.debug(f'Connection error.', exc_info=err)
                    raise ServerError('Сбой соединения в процессе авторизации.')

    def run(self):
        while self.running:
            sleep(1)
            with sock_lock:
                try:
                    self.transport.settimeout(0.5)
                    msg = get_message(self.transport)
                except OSError as err:
                    if err.errno:
                        LOGGER.error(f'Потеряно соединение с сервером (таймаут)')
                        self.running = False
                        self.connection_lost.emit()
                except (ConnectionError, ConnectionAbortedError,
                        ConnectionResetError, json.JSONDecodeError, TypeError) as err:
                    LOGGER.error(f'Потеряно соединение с сервером: {err}')
                    self.running = False
                    self.connection_lost.emit()
                else:
                    if msg:
                        #     LOGGER.debug(f'Соединение с сервером разорвано.')
                        if ACTION in msg:
                            if msg[ACTION] == MESSAGE and TIME in msg and SENDER in msg and MESSAGE_TEXT in msg:
                                # if msg[SENDER] != self.acc_name:
                                LOGGER.debug(f'Получено сообщение от {msg[SENDER]}: {msg[MESSAGE_TEXT]}')
                                with database_lock:
                                    try:
                                        self.database.add_message(msg[SENDER], 'i', msg[MESSAGE_TEXT])
                                        self.new_message.emit(msg[SENDER])
                                    except Exception as err:
                                        LOGGER.error(f'Ошибка взаимодействия с базой данных: {err}')
                                # if DESTINATION in msg and msg[DESTINATION] == self.acc_name:
                                #     print(f'ЛИЧНО [{msg[SENDER]}]: {msg[MESSAGE_TEXT]}')
                                # else:
                                #     print(f'[{msg[SENDER]}]: {msg[MESSAGE_TEXT]}')
                                # LOGGER.debug(f'Получено сообщение от пользователя {msg[SENDER]}: {msg[MESSAGE_TEXT]}')
                        elif RESPONSE in msg:
                            self.process_server_ans(msg)
                        else:
                            LOGGER.error(f'Получено некорректное сообщение с сервера: {msg}')
                finally:
                    self.transport.settimeout(5)

    # Exit
    def exit(self):
        self.send_service_message(EXIT)
        LOGGER.info('Завершение работы по команде пользователя.')
        sleep(0.3)

    # Добавляем контакт
    def add_contact(self, contact):
        # LOGGER.debug(f'Отправляю команду "{ADD_CONTACT} {contact}"')
        if self.send_service_message(ADD_CONTACT, contact):
            with database_lock:
                try:
                    self.database.add_contact(contact)
                except Exception as err:
                    LOGGER.error(f'Контакт "{contact}" добавить не удалось: {err}')
                else:
                    return True
        else:
            LOGGER.error(f'Контакт "{contact}" добавить не удалось, ошибка сервера')

    # Удаляем контакт
    def del_contact(self, contact):
        # LOGGER.debug(f'Отправляю команду "{DEL_CONTACT} {contact}"')
        if self.send_service_message(DEL_CONTACT, contact):
            with database_lock:
                try:
                    self.database.del_contact(contact)
                except Exception as err:
                    LOGGER.error(f'Контакт "{contact}" удалить не удалось: {err}')
                else:
                    return True
        else:
            LOGGER.error(f'Контакт "{contact}" удалить не удалось, ошибка сервера')

    # Функция обновления таблицы известных пользователей.
    def update_db_list(self, command):
        LOGGER.debug(f'Запрос списка {command}')
        users_list = self.send_service_message(command)

        if users_list:
            with database_lock:
                if command == USER_LIST:
                    self.database.update_users(users_list)
                elif command == GET_CONTACTS:
                    self.database.update_contacts(users_list)
        # else:
        #     LOGGER.error(f'Не удалось {command}, ответ сервера: EMPTY')

    # Запрашиваем список пользователей из базы
    def get_users_list(self):
        # contact_list = self.send_service_message(self.acc_name, USER_LIST)
        with database_lock:
            try:
                user_list = self.database.get_users()
            except Exception as err:
                LOGGER.error(f'Список пользователей загрузить не удалось: {err}')
            else:
                for user in sorted(user_list):
                    print(f'[{user[0]}]')

    # Запрашиваем список контактов из базы
    def get_contact_list(self):
        # contact_list = self.send_service_message(self.acc_name, GET_CONTACTS)
        with database_lock:
            try:
                contact_list = self.database.get_contacts()
            except Exception as err:
                LOGGER.error(f'Контакты загрузить не удалось: {err}')
            else:
                print(f'Ваш список контактов: {contact_list}')

    # Запрашиваем список сообщений
    # def get_msg_history(self):
    #     name = input('Введите "от <имя>" или "к <имя>" пользователя или нажмите Enter: ')
    #     with database_lock:
    #         name_from, name_to = None, None
    #         if name:
    #             if name[0] == 'о':
    #                 name_from = name[2:].strip()
    #             elif name[0] == 'к':
    #                 name_to = name[1:].strip()
    #         try:
    #             msg_list = self.database.get_messages(from_name=name_from, to_name=name_to)
    #         except Exception as err:
    #             LOGGER.error(f'Список пользователей загрузить не удалось: {err}')
    #         else:
    #             for m in sorted(msg_list):
    #                 print(f'({m[3]}) [{m[0]}] => [{m[1]}]: {m[2]}')

    # Запрашиваем список онлайн пользователей
    # def get_online_list(self):
    #     contact_list = self.send_service_message(self.acc_name, ONLINE)
    #     print(f'Пользователи онлайн: {contact_list}')

    # Запрашиваем помощь
    # elif msg[1] in ('h', '?'):
    #     self.print_help()

    # # Пишем личное сообщение
    # def send_message(self, msg):
    #     dest_name, text = self.get_name_from_msg(msg, 1, get_text=True)
    #     if dest_name:
    #         self.send_text_message(self.sock, dest_name, text)
    #     else:
    #         print('Для отправки личного сообщения введите "! <имя> <сообщение>"')
    #
    # # Пишем сообщение всем
    # def send_message_to_all(self, msg):
    #     LOGGER.debug(f'Подгатавливаю сообщение {msg}')
    #     self.send_text_message(self.sock, '', msg)
    #
    #     def get_name_from_msg(self, msg: str, cmd_len: int, get_text=False):
    #         if len(msg) < cmd_len + 1:
    #             return None, None if get_text else None
    #         name_len = msg[cmd_len:].lstrip().find(' ') if get_text else len(msg[cmd_len:].strip())
    #         if name_len <= 0:
    #             return None, None if get_text else None
    #         # print(f'name={msg[cmd_len + 1:cmd_len + 1 + name_len]=}')
    #         # print(f'text={msg[cmd_len + 1 + name_len:]=}')
    #         if get_text:
    #             return msg[cmd_len + 1:cmd_len + 1 + name_len], msg[cmd_len + 2 + name_len:]
    #         return msg[cmd_len + 1:cmd_len + 1 + name_len]

    @log
    def send_text_message(self, dest_name, msg):
        message_dict = {
            ACTION: MESSAGE,
            TIME: time(),
            SENDER: self.acc_name,
            DESTINATION: dest_name,
            MESSAGE_TEXT: msg
        }
        LOGGER.debug(f'Добавляю сообщение в базу {msg}')
        with database_lock:
            self.database.add_message(dest_name, 'o', msg)

        LOGGER.debug(f'Отправляю сообщение {msg}')
        with sock_lock:
            try:
                send_message(self.transport, message_dict)
                LOGGER.debug(f'Отправлено сообщение {msg} для пользователя {dest_name}')
            except OSError as err:
                if err.errno:
                    LOGGER.critical('Потеряно соединение с сервером.')
                    sys.exit(1)
                else:
                    LOGGER.error('Не удалось передать сообщение. Таймаут соединения')

    # @log
    def send_service_message(self, msg_type, data=None):
        # Формирование простых сообщений USER_LIST, ONLINE, GET_CONTACTS, EXIT
        if msg_type in (USER_LIST, ONLINE, GET_CONTACTS, EXIT):
            LOGGER.debug(f'Сформировано "{msg_type}" сообщение для сервера')
            msg = {
                ACTION: msg_type,
                TIME: time(),
                USER: self.acc_name
            }

            with sock_lock:
                try:
                    send_message(self.transport, msg)
                    if msg_type == EXIT:
                        return
                    ans = get_message(self.transport)
                except OSError as err:
                    if err.errno:
                        print(f'Не удалось доставить сообщение: {err}')
                        LOGGER.error(f'Не удалось доставить сообщение: {err}')
                        return
                else:
                    if ans and RESPONSE in ans:
                        LOGGER.debug(f'Получен ответ "{ans[RESPONSE]}" сообщение от сервера')
                        # Ответ OK
                        if ans[RESPONSE] == 200:
                            pass
                        # Ответ OK со списком
                        elif ans[RESPONSE] == 202 and ALERT in ans:
                            return ans[ALERT]
                        else:
                            self.show_message.emit(ans[ERROR])
                            LOGGER.error(f'Не удалось {msg_type}, ответ сервера: {ans}')

        # Формирование сообщений для добавления/удаления контакта DD_CONTACT, DEL_CONTACT
        if data and msg_type in (ADD_CONTACT, DEL_CONTACT):
            LOGGER.debug(f'Сформировано "{msg_type} {data}" сообщение для сервера')
            msg = {
                ACTION: msg_type,
                TIME: time(),
                USER: self.acc_name,
                ACCOUNT_NAME: data
            }
            with sock_lock:
                try:
                    send_message(self.transport, msg)
                    ans = get_message(self.transport)
                except OSError as err:
                    if err.errno:
                        print(f'Не удалось доставить сообщение: {err}')
                        LOGGER.error(f'Не удалось доставить сообщение: {err}')
                        return
                else:
                    if ans and RESPONSE in ans:
                        LOGGER.debug(f'Получен ответ "{ans[RESPONSE]}" сообщение от сервера')
                        if ans[RESPONSE] == 200:
                            LOGGER.debug(f'Получен ответ сервера: "OK"')
                            return True
                        else:
                            self.show_message.emit(ans[ERROR])
                            LOGGER.debug(f'Не удалось {msg_type}, ответ сервера: {ans}')
                            return False
                    LOGGER.debug(f'Получен неожиданный ответ сервера: "{ans}"')

    # def create_presence_message(self, sock):
    #     # Формирование простых сообщения PRESENCE
    #     LOGGER.debug(f'Сформировано "PRESENCE" сообщение для сервера')
    #     msg = {
    #         ACTION: PRESENCE,
    #         TIME: time(),
    #         USER: {
    #             ACCOUNT_NAME: self.acc_name
    #         }
    #     }
    #     send_message(sock, msg)
    #     ans = get_message(sock)
    #     if RESPONSE in ans and ans[RESPONSE] == 200:
    #         LOGGER.debug(f'Ответ сервера: "OK"')
    #         return True
    #     self.show_message.emit(ans)
    #     LOGGER.error(f'Ответ сервера: {ans}')

    def process_server_ans(self, msg):
        '''Метод обработчик поступающих сообщений с сервера.'''
        LOGGER.debug(f'Разбор сообщения от сервера: {msg}')

        # Если это подтверждение чего-либо
        if RESPONSE in msg:
            if msg[RESPONSE] == 200:
                return
            elif msg[RESPONSE] == 400:
                self.show_message.emit(msg[ERROR])
                raise ServerError(f'{msg[ERROR]}')
            elif msg[RESPONSE] == 205:
                self.update_db_list(USER_LIST)
                self.update_db_list(GET_CONTACTS)
                self.message_205.emit()
            else:
                LOGGER.error(
                    f'Принят неизвестный код подтверждения {msg[RESPONSE]}')

    # def print_help(self):
    #     print(' Поддерживаемые команды:')
    #     print('   <сообщение> - отправить сообщение всем')
    #     print('   ! <имя> <сообщение> - отправить личное сообщение')
    #     print('   /+ <имя> - добавить в список контактов')
    #     print('   /- <имя> - удалить из контактов')
    #     print('   /! - запросить список собеседников')
    #     print('   /a или /all - запросить список всех пользователей')
    #     print('   /c или /cont - запросить список контактов')
    #     print('   /m или /msg - запросить историю сообщений')
    #     print('   /h или /? - вывести подсказки по командам')
    #     print('   /q или /й - выход из программы')


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
#
# def load_database(user_name, database, sock):
#     sender = ClientSender(user_name, database, sock)
#     try:
#         users_list = sender.send_service_message(user_name, USER_LIST)
#     except Exception as err:
#         LOGGER.error(f'Ошибка запроса списка пользователей: {err}')
#     else:
#         if users_list:
#             database.update_users(users_list)
#     try:
#         contacts_list = sender.send_service_message(user_name, GET_CONTACTS)
#     except Exception as err:
#         LOGGER.error(f'Ошибка запроса списка контактов: {err}')
#     else:
#         if contacts_list:
#             for contact in contacts_list:
#                 database.add_contact(contact)
#     LOGGER.debug(f'База успешно загружена с сервера')

