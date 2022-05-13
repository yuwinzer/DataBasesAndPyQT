import os
import sys
import hashlib
import binascii
import logging
import log.server_log_config
from PyQt5.QtWidgets import QMainWindow, QAction, qApp, QApplication, QLabel, QTableView, QDialog, QPushButton, \
    QLineEdit, QFileDialog, QMessageBox, QMenu
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QEvent, QTimer
from common.utils import is_port_bad, is_ip_bad


LOGGER = logging.getLogger('server')


# GUI - Создание таблицы QModel, для отображения в окне программы.
def create_all_users_model(database):
    list_users = database.get_all_users_list()
    list_table = QStandardItemModel()
    list_table.setHorizontalHeaderLabels(['Имя Клиента', 'Время последнего входа'])
    for row in list_users:
        user, time = row
        user = QStandardItem(user)
        user.setEditable(False)
        # Уберём миллисекунды из строки времени, т.к. такая точность не требуется.
        time = QStandardItem(str(time.replace(microsecond=0)))
        time.setEditable(False)
        list_table.appendRow([user, time])
    return list_table


# GUI - Функция реализующая заполнение таблицы историей сообщений.
def create_stat_model(database):
    # Список записей из базы
    hist_list = database.get_user_stat()

    # Объект модели данных:
    list_table = QStandardItemModel()
    list_table.setHorizontalHeaderLabels(
        ['Имя Клиента', 'Последний раз входил', 'Сообщений отправлено', 'Сообщений получено'])
    for row in hist_list:
        user, last_seen, sent, recvd = row
        user = QStandardItem(user)
        user.setEditable(False)
        last_seen = QStandardItem(str(last_seen.replace(microsecond=0)))
        last_seen.setEditable(False)
        sent = QStandardItem(str(sent))
        sent.setEditable(False)
        recvd = QStandardItem(str(recvd))
        recvd.setEditable(False)
        list_table.appendRow([user, last_seen, sent, recvd])
    return list_table


# Класс основного окна
class MainWindow(QMainWindow):
    def __init__(self, database, server_app, config):
        super().__init__()

        self.database = database
        self.server_thread = server_app
        self.config = config
        self.new_connection = False

        self.init_ui()

    def init_ui(self):
        # Кнопка выхода
        self.exitAction = QAction('Выход', self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(qApp.quit)

        # Кнопка обновить список клиентов
        self.all_users_button = QAction('Все пользователи', self)

        # Кнопка вывести историю сообщений
        self.show_history_button = QAction('История клиентов', self)

        # Кнопка регистрации пользователя
        self.register_btn = QAction('Регистрация пользователя', self)

        # Кнопка настроек сервера
        self.config_btn = QAction('Настройки сервера', self)

        # Статусбар
        # dock widget
        self.statusBar()

        # Тулбар
        self.toolbar = self.addToolBar('MainBar')
        self.toolbar.addAction(self.exitAction)
        self.toolbar.addAction(self.all_users_button)
        self.toolbar.addAction(self.show_history_button)
        self.toolbar.addAction(self.register_btn)
        self.toolbar.addAction(self.config_btn)

        # Настройки геометрии основного окна
        # Поскольку работать с динамическими размерами мы не умеем, и мало времени на изучение, размер окна фиксирован.
        self.setFixedSize(800, 600)
        self.setWindowTitle('Messaging Server alpha release')
        self.statusBar().showMessage('Server Working')

        # Надпись о том, что ниже список подключённых клиентов
        self.label = QLabel('Список подключённых клиентов:', self)
        self.label.setFixedSize(400, 15)
        self.label.move(10, 35)

        # Окно со списком подключённых клиентов.
        self.active_clients_table = QTableView(self)
        self.active_clients_table.move(10, 55)
        self.active_clients_table.setFixedSize(780, 400)

        # Инициализируем обновления таблицы
        self.timer = QTimer()
        self.timer.timeout.connect(self.create_online_model)
        self.timer.start(2000)

        # Связываем кнопки с процедурами
        self.all_users_button.triggered.connect(self.show_all_users)
        self.show_history_button.triggered.connect(self.show_statistics)
        self.register_btn.triggered.connect(self.reg_user)
        self.config_btn.triggered.connect(self.server_config)

        # Последним параметром отображаем окно.
        self.show()

    # Функция, обновляющая список подключённых, проверяет флаг подключения, и
    # если надо обновляет список
    # GUI - Создание таблицы QModel, для отображения в окне программы.
    def create_online_model(self):
        list_users = self.database.get_active_users_list()
        list_table = QStandardItemModel()
        list_table.setHorizontalHeaderLabels(['Имя Клиента', 'IP Адрес', 'Порт', 'Время подключения'])
        for row in list_users:
            user, ip, port, time = row
            user = QStandardItem(user)
            user.setEditable(False)
            ip = QStandardItem(ip)
            ip.setEditable(False)
            port = QStandardItem(str(port))
            port.setEditable(False)
            # Уберём миллисекунды из строки времени, т.к. такая точность не требуется.
            time = QStandardItem(str(time.replace(microsecond=0)))
            time.setEditable(False)
            list_table.appendRow([user, ip, port, time])
        self.active_clients_table.setModel(list_table)
        self.active_clients_table.resizeColumnsToContents()
        self.active_clients_table.resizeRowsToContents()

    # Функция, создающая окно со статистикой клиентов
    def show_statistics(self):
        global stat_window
        stat_window = HistoryWindow()
        stat_window.history_table.setModel(create_stat_model(self.database))
        stat_window.history_table.resizeColumnsToContents()
        stat_window.history_table.resizeRowsToContents()
        # stat_window.show()

    # Функция, создающая окно со статистикой клиентов
    def show_all_users(self):
        global all_users_window
        all_users_window = AllUsersWindow(self.database, self.server_thread)
        all_users_window.all_users_table.setModel(create_all_users_model(self.database))
        all_users_window.all_users_table.resizeColumnsToContents()
        all_users_window.all_users_table.resizeRowsToContents()
        # all_users_window.show()

    # Функция создающяя окно с настройками сервера.
    def server_config(self):
        global config_window
        # Создаём окно и заносим в него текущие параметры
        config_window = ConfigWindow()
        config_window.db_path.insert(self.config['SETTINGS']['database_path'])
        config_window.db_file.insert(self.config['SETTINGS']['database_file'])
        config_window.port.insert(self.config['SETTINGS']['default_port'])
        config_window.ip.insert(self.config['SETTINGS']['listen_address'])
        config_window.save_btn.clicked.connect(config_window.save_server_config)
        # config_window.show()

    def reg_user(self):
        '''Метод создающий окно регистрации пользователя.'''
        global reg_window
        reg_window = RegisterUser(self.database, self.server_thread)
        reg_window.show()


# Класс окна с историей пользователей
class AllUsersWindow(QDialog):
    def __init__(self, database, server):
        super().__init__()
        self.database = database
        self.server = server
        # print(f'{self.server=}')
        self.initUI()

    def initUI(self):
        # Настройки окна:
        self.setWindowTitle('Список всех клиентов')
        self.setFixedSize(600, 700)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Кнопка закрытия окна
        self.close_button = QPushButton('Закрыть', self)
        self.close_button.move(250, 650)
        self.close_button.clicked.connect(self.close)

        # Лист с собственно историей
        self.all_users_table = QTableView(self)
        self.all_users_table.move(10, 10)
        self.all_users_table.setFixedSize(580, 620)
        self.all_users_table.installEventFilter(self)
        self.all_users_table.setSelectionBehavior(1)#setSelectionMode(1)
        # self.all_users_table.clicked.connect(self.delete_user)
        # itemDelegateForRow().mousePressEvent(QMouseEvent=C)

        self.show()

    def eventFilter(self, source, event):
        # if event.type() == QEvent.MouseButtonPress:
        #     print(event.button())
        #     print(event.pos())
        #     print(f'{self.itemAt(event.pos())=}')
        if event.type() == QEvent.ContextMenu:
            if source is self.all_users_table:
                # pos = event.pos()
                # row = source.selectedIndexes()#serowAt(event.pos().y())

                # print(f'{self.itemAt(event.pos())=}')
                # print(pos)
                # user = source.indexAt(event.pos())
                # print(f'{user.data()=}')

                try:
                    row = source.selectedIndexes()
                    if row:
                        user = str(row[0].data())
                        menu = QMenu()
                        menu.addAction('Удалить пользователя')
                        if menu.exec_(event.globalPos()):
                            # print(f'{user=}')
                            # if user in self.server.clients:
                            print(f'deleting: {user=}')
                            global del_popup
                            del_popup = DelUserDialog(self.database, self.server, user)
                        return True
                except Exception as e:
                    LOGGER.error(f'Не удалось удалить пользователя: {e}')
        return super().eventFilter(source, event)


class DelUserDialog(QDialog):
    def __init__(self, database, server, user):
        super().__init__()
        self.database = database
        self.server = server
        self.user = user

        self.setFixedSize(350, 120)
        self.setWindowTitle(f'Удаление пользователя: {user}')
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(True)

        self.selector_label = QLabel(
            f'ВНИМАНИЕ!\nПользователь {self.user} будет УДАЛЕН из базы.\nПодтвердите действие.', self)
        self.selector_label.setFixedSize(330, 50)
        self.selector_label.move(10, 0)

        self.btn_ok = QPushButton('Удалить', self)
        self.btn_ok.setFixedSize(100, 30)
        self.btn_ok.move(50, 70)
        self.btn_ok.clicked.connect(self.remove_user)

        self.btn_cancel = QPushButton('Отмена', self)
        self.btn_cancel.setFixedSize(100, 30)
        self.btn_cancel.move(200, 70)
        self.btn_cancel.clicked.connect(self.close)

        self.show()

    #     self.all_users_fill()
    #
    # def all_users_fill(self):
    #     '''Метод заполняющий список пользователей.'''
    #     self.selector.addItems([item[0]
    #                             for item in self.database.users_list()])

    def remove_user(self):
        '''Метод - обработчик удаления пользователя.'''
        LOGGER.debug(f'Удаляю пользователя: {self.user}')
        self.server.remove_client(self.user)
        self.database.remove_user(self.user)
        # LOGGER.debug(f'Удаляю пользователя2: {self.user}')
        # if self.user in self.server.clients:
        #     LOGGER.debug(f'Удаляю пользователя: {self.user}')
        #     sock = self.server.clients[self.user]
        #     del self.server.clients[self.user]
        #     self.server.remove_client(sock)
        LOGGER.debug(f'Удален. Обновляю списки у клиентов...')
        # Рассылаем клиентам сообщение о необходимости обновить справочники
        self.server.service_update_lists()
        self.close()


# Класс окна с историей пользователей
class HistoryWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Настройки окна:
        self.setWindowTitle('Статистика клиентов')
        self.setFixedSize(600, 700)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Кнопка закрытия окна
        self.close_button = QPushButton('Закрыть', self)
        self.close_button.move(250, 650)
        self.close_button.clicked.connect(self.close)

        # Лист с собственно историей
        self.history_table = QTableView(self)
        self.history_table.move(10, 10)
        self.history_table.setFixedSize(580, 620)

        self.show()


# Класс окна настроек
class ConfigWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Настройки окна
        self.setFixedSize(365, 260)
        self.setWindowTitle('Настройки сервера')

        # Надпись о файле базы данных:
        self.db_path_label = QLabel('Путь до файла базы данных: ', self)
        self.db_path_label.move(10, 10)
        self.db_path_label.setFixedSize(240, 15)

        # Строка с путём базы
        self.db_path = QLineEdit(self)
        self.db_path.setFixedSize(250, 20)
        self.db_path.move(10, 30)
        self.db_path.setReadOnly(True)

        # Кнопка выбора пути.
        self.db_path_select = QPushButton('Обзор...', self)
        self.db_path_select.move(275, 28)

        # Функция обработчик открытия окна выбора папки
        def open_file_dialog():
            global dialog
            dialog = QFileDialog(self)
            path = dialog.getExistingDirectory()
            path = path.replace('/', '\\')
            self.db_path.insert(path)

        self.db_path_select.clicked.connect(open_file_dialog)

        # Метка с именем поля файла базы данных
        self.db_file_label = QLabel('Имя файла базы данных: ', self)
        self.db_file_label.move(10, 68)
        self.db_file_label.setFixedSize(180, 15)

        # Поле для ввода имени файла
        self.db_file = QLineEdit(self)
        self.db_file.move(200, 66)
        self.db_file.setFixedSize(150, 20)

        # Метка с номером порта
        self.port_label = QLabel('Номер порта для соединений:', self)
        self.port_label.move(10, 108)
        self.port_label.setFixedSize(180, 15)

        # Поле для ввода номера порта
        self.port = QLineEdit(self)
        self.port.move(200, 108)
        self.port.setFixedSize(150, 20)

        # Метка с адресом для соединений
        self.ip_label = QLabel('С какого IP принимаем соединения:', self)
        self.ip_label.move(10, 148)
        self.ip_label.setFixedSize(180, 15)

        # Метка с напоминанием о пустом поле.
        self.ip_label_note = QLabel(' оставьте это поле пустым, чтобы\n принимать соединения с любых адресов.', self)
        self.ip_label_note.move(10, 168)
        self.ip_label_note.setFixedSize(500, 30)

        # Поле для ввода ip
        self.ip = QLineEdit(self)
        self.ip.move(200, 148)
        self.ip.setFixedSize(150, 20)

        # Кнопка сохранения настроек
        self.save_btn = QPushButton('Сохранить', self)
        self.save_btn.move(190, 220)

        # Кнопка закрытия окна
        self.close_button = QPushButton('Закрыть', self)
        self.close_button.move(275, 220)
        self.close_button.clicked.connect(self.close)

        self.show()

    # Функция сохранения настроек
    def save_server_config(self):
        global config_window
        info_message = QMessageBox()
        self.config['SETTINGS']['database_path'] = self.db_path.text()
        self.config['SETTINGS']['database_file'] = self.db_file.text()

        port = self.port.text()
        if is_port_bad(port):
            info_message.warning(self, 'Ошибка', f'Полученный PORT: {port} должен быть в пределах 1024-65535')
            return
        ip = self.ip.text()
        if is_ip_bad(ip):
            info_message.warning(self, 'Ошибка', f'Полученный IP: {ip} должен иметь формат: 127.0.0.1 ')
            return

        # Если порт и ip в норме - сохраняем
        self.config['SETTINGS']['listen_address'] = ip
        self.config['SETTINGS']['default_port'] = port
        with open('server.ini', 'w') as conf:
            self.config.write(conf)
            info_message.information(
                self, 'OK', 'Настройки успешно сохранены!')


class RegisterUser(QDialog):
    """ Класс диалог регистрации пользователя на сервере. """

    def __init__(self, database, server):
        super().__init__()

        self.database = database
        self.server = server

        self.setWindowTitle('Регистрация')
        self.setFixedSize(175, 183)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.label_username = QLabel('Введите имя пользователя:', self)
        self.label_username.move(10, 10)
        self.label_username.setFixedSize(150, 15)

        self.client_name = QLineEdit(self)
        self.client_name.setFixedSize(154, 20)
        self.client_name.move(10, 30)

        self.label_passwd = QLabel('Введите пароль:', self)
        self.label_passwd.move(10, 55)
        self.label_passwd.setFixedSize(150, 15)

        self.client_passwd = QLineEdit(self)
        self.client_passwd.setFixedSize(154, 20)
        self.client_passwd.move(10, 75)
        self.client_passwd.setEchoMode(QLineEdit.Password)
        self.label_conf = QLabel('Введите подтверждение:', self)
        self.label_conf.move(10, 100)
        self.label_conf.setFixedSize(150, 15)

        self.client_conf = QLineEdit(self)
        self.client_conf.setFixedSize(154, 20)
        self.client_conf.move(10, 120)
        self.client_conf.setEchoMode(QLineEdit.Password)

        self.btn_ok = QPushButton('Сохранить', self)
        self.btn_ok.move(10, 150)
        self.btn_ok.clicked.connect(self.save_data)

        self.btn_cancel = QPushButton('Выход', self)
        self.btn_cancel.move(90, 150)
        self.btn_cancel.clicked.connect(self.close)

        self.messages = QMessageBox()

        self.show()

    def save_data(self):
        """
        Метод проверки правильности ввода и сохранения в базу нового пользователя.
        """
        if not self.client_name.text():
            self.messages.critical(
                self, 'Ошибка', 'Не указано имя пользователя.')
            return
        elif self.client_passwd.text() != self.client_conf.text():
            self.messages.critical(
                self, 'Ошибка', 'Введённые пароли не совпадают.')
            return
        elif self.database.check_user(self.client_name.text()):
            self.messages.critical(
                self, 'Ошибка', 'Пользователь уже существует.')
            return
        else:
            # Генерируем хэш пароля, в качестве соли будем использовать логин в
            # нижнем регистре.
            passwd_bytes = self.client_passwd.text().encode('utf-8')
            salt = self.client_name.text().lower().encode('utf-8')
            passwd_hash = hashlib.pbkdf2_hmac(
                'sha512', passwd_bytes, salt, 10000)
            self.database.add_user(
                self.client_name.text(),
                binascii.hexlify(passwd_hash))
            self.messages.information(
                self, 'Успех', 'Пользователь успешно зарегистрирован.')
            # Рассылаем клиентам сообщение о необходимости обновить справочники
            self.server.service_update_lists()
            self.close()
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     main_window = MainWindow()
#     main_window.statusBar().showMessage('Test Statusbar Message')
#     test_list = QStandardItemModel(main_window)
#     test_list.setHorizontalHeaderLabels(['Имя Клиента', 'IP Адрес', 'Порт', 'Время подключения'])
#     test_list.appendRow(
#         [QStandardItem('test1'), QStandardItem('192.198.0.5'), QStandardItem('23544'), QStandardItem('16:20:34')])
#     test_list.appendRow(
#         [QStandardItem('test2'), QStandardItem('192.198.0.8'), QStandardItem('33245'), QStandardItem('16:22:11')])
#     main_window.active_clients_table.setModel(test_list)
#     main_window.active_clients_table.resizeColumnsToContents()
#     app.exec_()

    # ----------------------------------------------------------
    # app = QApplication(sys.argv)
    # window = HistoryWindow()
    # test_list = QStandardItemModel(window)
    # test_list.setHorizontalHeaderLabels(
    #     ['Имя Клиента', 'Последний раз входил', 'Отправлено', 'Получено'])
    # test_list.appendRow(
    #     [QStandardItem('test1'), QStandardItem('Fri Dec 12 16:20:34 2020'), QStandardItem('2'), QStandardItem('3')])
    # test_list.appendRow(
    #     [QStandardItem('test2'), QStandardItem('Fri Dec 12 16:23:12 2020'), QStandardItem('8'), QStandardItem('5')])
    # window.history_table.setModel(test_list)
    # window.history_table.resizeColumnsToContents()
    #
    # app.exec_()

    # ----------------------------------------------------------
    # app = QApplication(sys.argv)
    # dial = ConfigWindow()
    #
    # app.exec_()
