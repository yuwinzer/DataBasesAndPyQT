from PyQt5.QtWidgets import QMainWindow, qApp, QMessageBox, QApplication, QListView, QMenu, QListWidget
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor
from PyQt5.QtCore import pyqtSlot, QEvent, Qt, QObject
import sys
import json
import logging

sys.path.append('../')
from common.globals import *
from client.main_window_ui import Ui_MainWindow
from client.client_db import ClientDB
from client.transport import ClientTransport
from common.errors import ServerError

LOGGER = logging.getLogger('client')


class ClientMainWindow(QMainWindow):
    def __init__(self, database, transport):
        super().__init__()

        # основные переменные
        self.database = database
        self.transport = transport

        # Загружаем конфигурацию окна из дизайнера
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Кнопка "Выход"
        # self.ui.menu_exit.triggered.connect(qApp.exit)

        # Кнопка отправить сообщение
        self.ui.EnterBT.clicked.connect(self.send_message)

        # Панель пользователей и контактов
        # self.ui.usersTab.installEventFilter(self)

        self.ui.UserList.installEventFilter(self)
        self.ui.UpdateUsersBT.clicked.connect(self.update_lists)

        self.ui.ContactList.installEventFilter(self)
        self.ui.UpdateContsBT.clicked.connect(self.update_lists)

        # "добавить контакт"
        # self.ui.add_contact_context = QListWidget()
        # self.ui.add_contact_context.addItem('Добавить контакт')
        # self.ui.UserList.contextMenuEvent.connect(self.add_contact_context)

        # self.ui.UserList.customContextMenuRequested.connect(self.add_contact_context)
        # QObject.connect(self.pushButton, PYQT_SIGNAL("clicked()"), self.add_contact_context)
        # self.ui.btn_add_contact.clicked.connect(self.add_contact_window)
        # self.ui.menu_add_contact.triggered.connect(self.add_contact_window)

        # Удалить контакт

        # self.ui.btn_remove_contact.clicked.connect(self.delete_contact_window)
        # self.ui.menu_del_contact.triggered.connect(self.delete_contact_window)

        # Дополнительные требующиеся атрибуты
        self.contacts_model = None
        self.users_model = None
        self.history_model = None
        self.messages = QMessageBox()
        self.current_chat = None  # Текущий контакт с которым идёт обмен сообщениями
        self.ui.MsgField.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.MsgField.setWordWrap(True)

        # Double click по списку контактов отправляется в обработчик
        self.ui.ContactList.doubleClicked.connect(self.select_active_user)

        self.update_contacts_list()
        self.update_users_list()
        self.set_disabled_input()
        self.show()

    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu:
            # print(source.indexAt(event.pos()))
            if source is self.ui.UserList:
                menu = QMenu()
                menu.addAction('Добавить контакт')
                try:
                    if menu.exec_(event.globalPos()):
                        item = source.indexAt(event.pos())
                        LOGGER.debug(f'Добавляю контакт: {item.data()}')
                        if item and not self.database.check_contact(item.data()):
                            self.ui.usersTab.setCurrentIndex(1)
                            self.transport.add_contact(item.data())
                            self.update_contacts_list()
                    return True
                except Exception as e:
                    LOGGER.error(f'Не удалось добавить контакт: {e}')

            if source is self.ui.ContactList:
                menu = QMenu()
                menu.addAction('Удалить контакт')
                try:
                    if menu.exec_(event.globalPos()):
                        item = source.indexAt(event.pos())
                        LOGGER.debug(f'Удаляю контакт: {item.data()}')
                        if item and self.database.check_contact(item.data()):
                            self.transport.del_contact(item.data())
                            self.update_contacts_list()
                    return True
                except Exception as e:
                    LOGGER.error(f'Не удалось удалить контакт: {e}')
        return super().eventFilter(source, event)

    # Деактивировать поля ввода
    def set_disabled_input(self):
        # Надпись  - получатель.
        self.ui.ContactName.setText('Выберите пользователя')
        self.ui.EnterTE.clear()
        if self.history_model:
            self.history_model.clear()

        # Поле ввода и кнопка отправки неактивны до выбора получателя.
        self.ui.EnterBT.setDisabled(True)
        self.ui.EnterTE.setDisabled(True)

    def update_lists(self):
        if self.ui.usersTab.currentWidget().objectName() == 'Users':
            self.transport.update_db_list(USER_LIST)
            self.update_users_list()
        elif self.ui.usersTab.currentWidget().objectName() == 'Conts':
            self.transport.update_db_list(GET_CONTACTS)
            self.update_contacts_list()
        # print(self.ui.usersTab.currentWidget().objectName())

    # Функция, обновляющая контакт-лист
    def update_contacts_list(self):
        LOGGER.debug('Запрос скиска контактов')
        contacts_list = self.database.get_contacts()
        self.contacts_model = QStandardItemModel()
        for i in sorted(contacts_list):
            item = QStandardItem(i)
            item.setEditable(False)
            self.contacts_model.appendRow(item)
        self.ui.ContactList.setModel(self.contacts_model)

    # Функция, обновляющая лист пользователей
    def update_users_list(self):
        LOGGER.debug('Запрос скиска пользователей')
        users_list = self.database.get_users()
        self.users_model = QStandardItemModel()
        for i in sorted(users_list):
            item = QStandardItem(i)
            item.setEditable(False)
            self.users_model.appendRow(item)
        self.ui.UserList.setModel(self.users_model)

    # Функция обработчик double click по контакту
    def select_active_user(self):
        # Выбранный пользователем контакт находится в выделенном элементе в QListView
        self.current_chat = self.ui.ContactList.currentIndex().data()
        # вызываем основную функцию
        self.set_active_user()

    # Функция, устанавливающая активного собеседника
    def set_active_user(self):
        # Ставим надпись и активируем кнопки
        self.ui.ContactName.setText(self.current_chat)
        self.ui.EnterBT.setDisabled(False)
        self.ui.EnterTE.setDisabled(False)

        # Заполняем окно историю сообщений по требуемому пользователю.
        self.history_list_update()

    # Функция отправки сообщения пользователю.
    def send_message(self):
        # Текст в поле, проверяем что поле не пустое затем забирается сообщение и поле очищается
        msg_text = self.ui.EnterTE.toPlainText()
        self.ui.EnterTE.clear()
        if not msg_text:
            return
        self.transport.send_text_message(self.current_chat, msg_text)
        self.history_list_update()
        # try:
        #     self.transport.send_text_message(self.current_chat, message_text)
        # except ServerError as err:
        #     self.messages.critical(self, 'Ошибка', err.text)
        # except OSError as err:
        #     if err.errno:
        #         self.messages.critical(self, 'Ошибка', 'Потеряно соединение с сервером!')
        #         self.close()
        #     self.messages.critical(self, 'Ошибка', 'Таймаут соединения!')
        # except (ConnectionResetError, ConnectionAbortedError):
        #     self.messages.critical(self, 'Ошибка', 'Потеряно соединение с сервером!')
        #     self.close()
        # else:
        #     self.database.save_message(self.current_chat, 'o', message_text)
        #     LOGGER.debug(f'Отправлено сообщение для {self.current_chat}: {message_text}')
            # self.history_list_update()

    # Заполняем историю сообщений.
    def history_list_update(self):
        # Получаем историю сортированную по дате
        LOGGER.debug(f'Загрузка истории сообщений')
        list_messages = sorted(self.database.get_history(self.current_chat),
                               key=lambda item: item[3])
        # Если модель не создана, создадим.
        if not self.history_model:
            LOGGER.debug(f'Создание модели истории сообщений')
            self.history_model = QStandardItemModel()
            self.ui.MsgField.setModel(self.history_model)
        # Очистим от старых записей
        self.history_model.clear()
        # Берём не более 20 последних записей.
        # LOGGER.debug(f'Выводим последние 20 сообщений')
        length = len(list_messages)
        start_index = 0
        if length > 20:
            start_index = length - 20
        # Заполнение модели записями, так же стоит разделить входящие и исходящие
        # сообщения выравниванием и разным фоном.
        # Записи в обратном порядке, поэтому выбираем их с конца и не более 20
        for i in range(start_index, length):
            item = list_messages[i]
            if item[1] == 'i':
                mess = QStandardItem(f'{self.current_chat} ({item[3].replace(microsecond=0)}):\n {item[2]}')
                mess.setEditable(False)
                mess.setBackground(QBrush(QColor(224, 233, 255)))
                mess.setTextAlignment(Qt.AlignLeft)
                self.history_model.appendRow(mess)
            else:
                mess = QStandardItem(f'{self.transport.acc_name} ({item[3].replace(microsecond=0)}):\n {item[2]}')
                mess.setEditable(False)
                mess.setTextAlignment(Qt.AlignRight)
                mess.setBackground(QBrush(QColor(224, 255, 233)))
                self.history_model.appendRow(mess)
        self.ui.MsgField.scrollToBottom()

    # Слот приёма нового сообщений
    @pyqtSlot(str)
    def message(self, sender):
        if sender == self.current_chat:
            self.history_list_update()
        else:
            # Проверим есть ли такой пользователь у нас в контактах:
            if self.database.check_contact(sender):
                # Если есть, спрашиваем о желании открыть с ним чат и открываем при желании
                if self.messages.question(self, 'Новое сообщение',
                                          f'Получено новое сообщение от {sender}, '
                                          f'открыть чат с ним?', QMessageBox.Yes,
                                          QMessageBox.No) == QMessageBox.Yes:
                    self.current_chat = sender
                    self.set_active_user()
            else:
                # Раз нет, спрашиваем хотим ли добавить юзера в контакты.
                if self.messages.question(self, 'Новое сообщение',
                                          f'Получено новое сообщение от {sender}.\n '
                                          f'Данного пользователя нет в вашем контакт-листе.\n'
                                          f' Добавить в контакты и открыть чат с ним?',
                                          QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
                    self.transport.add_contact(sender)
                    self.current_chat = sender
                    self.update_contacts_list()
                    self.set_active_user()

    # Слот потери соединения
    # Выдаёт сообщение об ошибке и завершает работу приложения
    @pyqtSlot()
    def connection_lost(self):
        self.messages.warning(self, 'Сбой соединения', 'Потеряно соединение с сервером. ')
        self.close()

    def make_connection(self, trans_obj):
        trans_obj.new_message.connect(self.message)
        trans_obj.connection_lost.connect(self.connection_lost)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    from client_db import ClientDB

    database = ClientDB('test1')
    from transport import ClientTransport

    transport = ClientTransport(database, 'test1', '127.0.0.1', 7777)
    window = ClientMainWindow(database, transport)
    sys.exit(app.exec_())
