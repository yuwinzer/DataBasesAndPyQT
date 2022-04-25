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
from common.globals import *
from common.utils import send_message, get_message, handle_parameters
from common.errors import ReqFieldMissingError, ServerError
import logging
import log.client_log_config
from log.decorator import log
from client_db import ClientDB

LOGGER = logging.getLogger('client')

# Объект блокировки сокета и работы с базой данных
sock_lock = threading.Lock()
database_lock = threading.Lock()


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
    def __init__(self, acc_name, database, sock):
        self.acc_name = acc_name
        self.sock = sock
        self.database = database
        super().__init__()

    def run(self):
        while True:
            sleep(1)
            with sock_lock:
                try:
                    msg = get_message(self.sock)
                # except Exception as err:
                #     LOGGER.error(f'Не удалось декодировать полученное сообщение: {err}')
                # break
                except OSError as err:
                    if err.errno:
                        LOGGER.error(f'Потеряно соединение с сервером (таймаут): {err}')
                        break
                except (ConnectionError, ConnectionAbortedError,
                        ConnectionResetError, json.JSONDecodeError) as err:
                    LOGGER.error(f'Потеряно соединение с сервером: {err}')
                    break
                else:
                    if not msg:
                        LOGGER.debug(f'Соединение с сервером разорвано.')
                        # sys.exit(0)
                    elif ACTION in msg and msg[ACTION] == MESSAGE and TIME in msg and \
                            SENDER in msg and MESSAGE_TEXT in msg:
                        if msg[SENDER] != self.acc_name:
                            with database_lock:
                                try:
                                    self.database.add_message(msg[SENDER],
                                                              msg[DESTINATION],
                                                              msg[MESSAGE_TEXT])
                                except Exception as err:
                                    LOGGER.error(f'Ошибка взаимодействия с базой данных: {err}')
                        if DESTINATION in msg and msg[DESTINATION] == self.acc_name:
                            print(f'ЛИЧНО [{msg[SENDER]}]: {msg[MESSAGE_TEXT]}')
                        else:
                            print(f'[{msg[SENDER]}]: {msg[MESSAGE_TEXT]}')
                        LOGGER.debug(f'Получено сообщение от пользователя {msg[SENDER]}: {msg[MESSAGE_TEXT]}')
                    else:
                        LOGGER.error(f'Получено некорректное сообщение с сервера: {msg}')


class ClientSender(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, acc_name, database, sock):
        self.acc_name = acc_name
        self.sock = sock
        self.database = database
        super().__init__()

    def run(self):
        self.print_help()
        while True:
            msg = input(f'')
            if len(msg) >= 1:

                # Сообщение является командой
                if len(msg) >= 2 and msg[0] == '/':
                    if msg[1] in ('q', 'й'):
                        self.create_service_message(self.acc_name, EXIT)
                        status_exit = True
                        print('Завершение работы')
                        LOGGER.info('Завершение работы по команде пользователя.')
                        sleep(0.2)
                        sys.exit(0)

                    # Добавляем контакт
                    elif msg[1] == '+':
                        dest_name = self.get_name_from_msg(msg, 2)
                        print(f'{dest_name=}')
                        if dest_name:
                            LOGGER.debug(f'Отправляю команду "{ADD_CONTACT} {dest_name}"')
                            if self.create_service_message(self.acc_name, ADD_CONTACT, dest_name):
                                with database_lock:
                                    try:
                                        self.database.add_contact(dest_name)
                                    except Exception as err:
                                        LOGGER.error(f'Контакт "{dest_name}" добавить не удалось: {err}')
                                    else:
                                        print(f'Контакт "{dest_name}" добавлен')
                            else:
                                LOGGER.error(f'Контакт "{dest_name}" добавить не удалось, ошибка сервера')
                        else:
                            print('Для добавления пользователя введите "/+ <имя>"')

                    # Удаляем контакт
                    elif msg[1] == '-':
                        dest_name = self.get_name_from_msg(msg, 2)
                        if dest_name:
                            LOGGER.debug(f'Отправляю команду "{DEL_CONTACT} {dest_name}"')
                            if self.create_service_message(self.acc_name, DEL_CONTACT, dest_name):
                                with database_lock:
                                    try:
                                        self.database.del_contact(dest_name)
                                    except Exception as err:
                                        LOGGER.error(f'Контакт "{dest_name}" удалить не удалось: {err}')
                                    else:
                                        print(f'Контакт "{dest_name}" удален')
                            else:
                                print(f'Контакт "{dest_name}" удалить не удалось, ошибка сервера')
                        else:
                            print('Для добавления пользователя введите "/- <имя>"')

                    # Запрашиваем список пользователей
                    elif msg[1:] in ('a', 'all'):
                        # contact_list = self.create_service_message(self.acc_name, USER_LIST)
                        with database_lock:
                            try:
                                user_list = self.database.get_users()
                            except Exception as err:
                                LOGGER.error(f'Список пользователей загрузить не удалось: {err}')
                            else:
                                for user in sorted(user_list):
                                    print(f'[{user[0]}]')

                    # Запрашиваем список контактов
                    elif msg[1:] in ('c', 'cont'):
                        # contact_list = self.create_service_message(self.acc_name, GET_CONTACTS)
                        with database_lock:
                            try:
                                contact_list = self.database.get_contacts()
                            except Exception as err:
                                LOGGER.error(f'Контакты загрузить не удалось: {err}')
                            else:
                                print(f'Ваш список контактов: {contact_list}')

                    # Запрашиваем список сообщений
                    elif msg[1:] in ('m', 'msg'):
                        # contact_list = self.create_service_message(self.acc_name, USER_LIST)
                        name = input('Введите "от <имя>" или "к <имя>" пользователя или нажмите Enter: ')
                        with database_lock:
                            name_from, name_to = None, None
                            if name:
                                if name[0] == 'о':
                                    name_from = name[2:].strip()
                                elif name[0] == 'к':
                                    name_to = name[1:].strip()
                            try:
                                msg_list = self.database.get_messages(from_name=name_from, to_name=name_to)
                            except Exception as err:
                                LOGGER.error(f'Список пользователей загрузить не удалось: {err}')
                            else:
                                for m in sorted(msg_list):
                                    print(f'({m[3]}) [{m[0]}] => [{m[1]}]: {m[2]}')

                    # Запрашиваем список онлайн пользователей
                    elif msg[1] == '!':
                        contact_list = self.create_service_message(self.acc_name, ONLINE)
                        print(f'Пользователи онлайн: {contact_list}')

                    # Запрашиваем помощь
                    elif msg[1] in ('h', '?'):
                        self.print_help()

                # Пишем личное сообщение
                elif len(msg) > 2 and msg[0] == '!':
                    dest_name, text = self.get_name_from_msg(msg, 1, get_text=True)
                    if dest_name:
                        self.create_text_message(self.sock, dest_name, text)
                    else:
                        print('Для отправки личного сообщения введите "! <имя> <сообщение>"')

                # Пишем сообщение всем
                else:
                    LOGGER.debug(f'Подгатавливаю сообщение {msg}')
                    self.create_text_message(self.sock, '', msg)

    def get_name_from_msg(self, msg: str, cmd_len: int, get_text=False):
        if len(msg) < cmd_len + 1:
            return None, None if get_text else None
        name_len = msg[cmd_len:].lstrip().find(' ') if get_text else len(msg[cmd_len:].strip())
        if name_len <= 0:
            return None, None if get_text else None
        # print(f'name={msg[cmd_len + 1:cmd_len + 1 + name_len]=}')
        # print(f'text={msg[cmd_len + 1 + name_len:]=}')
        if get_text:
            return msg[cmd_len + 1:cmd_len + 1 + name_len], msg[cmd_len + 2 + name_len:]
        return msg[cmd_len + 1:cmd_len + 1 + name_len]

    @log
    def create_text_message(self, sock, dest_name, msg):
        message_dict = {
            ACTION: MESSAGE,
            TIME: time(),
            SENDER: self.acc_name,
            DESTINATION: dest_name,
            MESSAGE_TEXT: msg
        }
        LOGGER.debug(f'Добавляю сообщение в базу {msg}')
        with database_lock:
            self.database.add_message(self.acc_name, dest_name, msg)

        LOGGER.debug(f'Отправляю сообщение {msg}')
        with sock_lock:
            try:
                send_message(sock, message_dict)
                LOGGER.debug(f'Отправлено сообщение {msg} для пользователя {dest_name}')
            except OSError as err:
                if err.errno:
                    LOGGER.critical('Потеряно соединение с сервером.')
                    sys.exit(1)
                else:
                    LOGGER.error('Не удалось передать сообщение. Таймаут соединения')

    # @log
    def create_service_message(self, acc_name, msg_type, data=False):
        # Формирование простых сообщений USER_LIST, ONLINE, GET_CONTACTS, EXIT
        if msg_type in (USER_LIST, ONLINE, GET_CONTACTS, EXIT):
            LOGGER.debug(f'Сформировано "{msg_type}" сообщение для сервера')
            msg = {
                ACTION: msg_type,
                TIME: time(),
                USER: acc_name
            }

            with sock_lock:
                try:
                    send_message(self.sock, msg)
                    ans = get_message(self.sock)
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
                        elif ans[RESPONSE] == 202:
                            return ans[ALERT]
                        else:
                            LOGGER.error(f'Не удалось {msg_type}, ответ сервера: {ans}')

        # Формирование сообщений для добавления/удаления контакта DD_CONTACT, DEL_CONTACT
        if data and msg_type in (ADD_CONTACT, DEL_CONTACT):
            LOGGER.debug(f'Сформировано "{msg_type} {data}" сообщение для сервера')
            msg = {
                ACTION: msg_type,
                TIME: time(),
                USER: acc_name,
                ACCOUNT_NAME: data
            }
            with sock_lock:
                try:
                    send_message(self.sock, msg)
                    ans = get_message(self.sock)
                except OSError as err:
                    if err.errno:
                        print(f'Не удалось доставить сообщение: {err}')
                        LOGGER.error(f'Не удалось доставить сообщение: {err}')
                        return
                else:
                    if ans and RESPONSE in ans:
                        if ans[RESPONSE] == 200:
                            LOGGER.debug(f'Получен ответ сервера: "OK"')
                            return True
                        else:
                            LOGGER.debug(f'Не удалось {msg_type}, ответ сервера: {ans}')
                            return False
                    LOGGER.debug(f'Получен неожиданный ответ сервера: "{ans}"')

    def print_help(self):
        print(' Поддерживаемые команды:')
        print('   <сообщение> - отправить сообщение всем')
        print('   ! <имя> <сообщение> - отправить личное сообщение')
        print('   /+ <имя> - добавить в список контактов')
        print('   /- <имя> - удалить из контактов')
        print('   /! - запросить список собеседников')
        print('   /a или /all - запросить список всех пользователей')
        print('   /c или /cont - запросить список контактов')
        print('   /m или /msg - запросить историю сообщений')
        print('   /h или /? - вывести подсказки по командам')
        print('   /q или /й - выход из программы')


# @log
def create_presence_message(sock, acc_name):
    # Формирование простых сообщения PRESENCE
    LOGGER.debug(f'Сформировано "PRESENCE" сообщение для сервера')
    msg = {
        ACTION: PRESENCE,
        TIME: time(),
        USER: {
            ACCOUNT_NAME: acc_name
        }
    }
    send_message(sock, msg)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        LOGGER.debug(f'Ответ сервера: "OK"')
        return True
    LOGGER.error(f'Ответ сервера: {ans}')


def load_database(user_name, database, sock):
    sender = ClientSender(user_name, database, sock)
    try:
        users_list = sender.create_service_message(user_name, USER_LIST)
    except Exception as err:
        LOGGER.error(f'Ошибка запроса списка пользователей: {err}')
    else:
        if users_list:
            database.update_users(users_list)
    try:
        contacts_list = sender.create_service_message(user_name, GET_CONTACTS)
    except Exception as err:
        LOGGER.error(f'Ошибка запроса списка контактов: {err}')
    else:
        if contacts_list:
            for contact in contacts_list:
                database.add_contact(contact)
    LOGGER.debug(f'База успешно загружена с сервера')


def main():
    LOGGER.debug('=' * 40 + '[ CLIENT LOG START TIME: ' + strftime("%a, %d %b %Y %H:%M:%S ]", localtime()) + '=' * 40)
    try:
        serv_ip, serv_port, acc_name = handle_parameters(ip=DEF_IP, port=DEF_PORT)
        print('*' * 100 + '\n Клиент системы обмена сообщениями. ВЕРСИЯ 016 БУ. ГОСТ 189-27-1956.\n' + '*' * 100)
        knock = 0
        try:
            for knock in range(5):
                # Требуем имя
                acc_name = input('Представьтесь: ')
                if acc_name.strip() == '' or '/' in acc_name:
                    continue

                # Если имя подходит, создаем подключение
                try:
                    my_sock = socket(AF_INET, SOCK_STREAM)
                    my_sock.settimeout(1)  # Таймаут 1 секунда, необходим для освобождения сокета.
                    # Когда отсутствие одной строки стоит многих нервных клеток

                    LOGGER.debug(f'[{acc_name}]: Попытка соедиения...')
                    my_sock.connect((serv_ip, serv_port))

                    LOGGER.debug(f'Отправляю сообщение о присутствии...')
                    if create_presence_message(my_sock, acc_name):
                        break
                except (ConnectionRefusedError, ConnectionError):
                    LOGGER.debug(f'Сервер не отвечает {serv_ip}:{serv_port}')

            # Если не удалось ввести имя или подключиться 5 раз - расходимся
            if knock == 4:
                print('К сожалению подключиться не удалось. Попробуйте позже.')
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
            print(f' Приветствуем, {acc_name}.\n'
                  f' Напоминаем, что вы несете полную ответственность за свои слова в соответствии с законодательнвом.\n'
                  f' Приятного общения.\n' + '*' * 100)
            LOGGER.info(f'Клиент запущен. Использую SERVER IP:{serv_ip} PORT:{serv_port} NAME:{acc_name}')
            print(f'Соединение установлено')

            # Инициализация БД
            database = ClientDB(f'database/client_{acc_name}.db3')
            load_database(acc_name, database, my_sock)

            thread_receiver = ClientReader(acc_name, database, my_sock)
            thread_receiver.daemon = True
            thread_receiver.start()
            LOGGER.debug('Запущен процесс получатель')

            thread_sender_ui = ClientSender(acc_name, database, my_sock)
            thread_sender_ui.daemon = True
            thread_sender_ui.start()
            LOGGER.debug('Запущен процесс интерфейс и отправщик')

            while thread_receiver.is_alive() and thread_sender_ui.is_alive():
                sleep(1)

    except KeyboardInterrupt:
        LOGGER.info(f'Завершение работы клиента')
        # my_sock.close()
        LOGGER.info(f'Клиент остановлен')
        sys.exit(1)


if __name__ == '__main__':
    main()
