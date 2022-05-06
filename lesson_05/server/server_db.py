""""""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime


class ServerDB:
    Base = declarative_base()

    # Список всех пользователей
    class AllUsers(Base):
        __tablename__ = 'all_users'
        id = Column(Integer, primary_key=True)
        user_name = Column(String, unique=True)
        last_login_time = Column(DateTime)

        def __init__(self, user_name):
            self.user_name = user_name
            self.last_login_time = datetime.now()

    # Список активных пользователей
    class ActiveUsers(Base):
        __tablename__ = 'active_users'
        id = Column(Integer, primary_key=True)
        user_id = Column(ForeignKey('all_users.id'), unique=True)
        ip = Column(String)
        port = Column(Integer)
        login_time = Column(DateTime)

        def __init__(self, user_id, ip, port, login_time):
            self.user_id = user_id
            self.ip = ip
            self.port = port
            self.login_time = login_time

    # Список контактов каждого пользователя
    class UsersContacts(Base):
        __tablename__ = 'users_contacts'
        id = Column(Integer, primary_key=True)
        user_id = Column(ForeignKey('all_users.id'))
        contact_id = Column(ForeignKey('all_users.id'))

        def __init__(self, user_id, contact_id):
            self.user_id = user_id
            self.contact_id = contact_id

    # Список действий каждого пользователя
    class UsersStats(Base):
        __tablename__ = 'users_stats'
        id = Column(Integer, primary_key=True)
        user_id = Column(ForeignKey('all_users.id'), unique=True)
        sent = Column(Integer)
        received = Column(Integer)

        def __init__(self, user_id):
            self.user_id = user_id
            self.sent = 0
            self.received = 0

    # История входа пользователей
    class LoginHistory(Base):
        __tablename__ = 'login_history'
        id = Column(Integer, primary_key=True)
        user_id = Column(String, ForeignKey('all_users.id'))
        ip = Column(String)
        port = Column(Integer)
        last_login_time = Column(DateTime)

        def __init__(self, user_id, ip, port, last_login_time):
            self.user_id = user_id
            self.ip = ip
            self.port = port
            self.last_login_time = last_login_time

    # Инициализация
    def __init__(self, path):  # client/server_base.db3
        self.engine = create_engine(f'sqlite:///{path}?check_same_thread=False',
                                    echo=False, pool_recycle=7200, encoding='utf-8')
        self.Base.metadata.create_all(self.engine)

        Session = scoped_session(sessionmaker(bind=self.engine))
        self.session = Session()

        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    # Вход пользователя
    def user_login(self, user_name, ip, port):
        searchable_user = self.session.query(self.AllUsers).filter_by(user_name=user_name)
        if searchable_user.count():
            user = searchable_user.first()
            user.last_login_time = datetime.now()
        else:
            user = self.AllUsers(user_name)
            self.session.add(user)
            self.session.commit()
            new_user_stat = self.UsersStats(user.id)
            self.session.add(new_user_stat)

        new_active_user = self.ActiveUsers(user.id, ip, port, datetime.now())
        self.session.add(new_active_user)
        user_history = self.LoginHistory(user.id, ip, port, datetime.now())
        self.session.add(user_history)
        self.session.commit()

    # Выход пользователя
    def user_logout(self, user_name):
        user = self.session.query(self.AllUsers).filter_by(user_name=user_name).first()
        self.session.query(self.ActiveUsers).filter_by(user_id=user.id).delete()
        self.session.commit()

    # Получить список всех пользователей
    def get_all_users_list(self):
        query = self.session.query(self.AllUsers.user_name, self.AllUsers.last_login_time)
        return query.all()

    # Получить список активных пользователей
    def get_active_users_list(self):
        query = self.session.query(
            self.AllUsers.user_name,
            self.ActiveUsers.ip,
            self.ActiveUsers.port,
            self.ActiveUsers.login_time
        ).join(self.AllUsers)
        return query.all()

    # Добавление пользователя в контакты
    def add_contact(self, user_name, contact_name):
        contact = self.session.query(self.AllUsers).filter_by(user_name=contact_name).first()
        if not contact:
            return
        user = self.session.query(self.AllUsers).filter_by(user_name=user_name).first()
        if not user:
            return
        if self.session.query(self.UsersContacts).filter_by(user_id=user.id, contact_id=contact.id).count():
            return
        new_contact = self.UsersContacts(user.id, contact.id)
        self.session.add(new_contact)
        self.session.commit()
        return True

    # Удаляем пользователя из контактов
    def del_contact(self, user_name, contact_name):
        user = self.session.query(self.AllUsers).filter_by(user_name=user_name).first()
        if not user:
            return
        contact = self.session.query(self.AllUsers).filter_by(user_name=contact_name).first()
        if not contact:
            return
        self.session.query(self.UsersContacts).filter_by(user_id=user.id, contact_id=contact.id).delete()
        self.session.commit()
        return True

    # Получить список контактов пользователя
    def get_contacts(self, user_name):
        user = self.session.query(self.AllUsers).filter_by(user_name=user_name).first()
        if not user:
            return
        contact_list = self.session.query(self.UsersContacts, self.AllUsers.user_name). \
            filter_by(user_id=user.id). \
            join(self.AllUsers, self.UsersContacts.contact_id == self.AllUsers.id)
        return [contact_name[1] for contact_name in contact_list.all()]

    # Получить историю входа пользователей
    def get_login_history(self, user_name=None):
        query = self.session.query(
            self.AllUsers.user_name,
            self.LoginHistory.ip,
            self.LoginHistory.port,
            self.LoginHistory.last_login_time
        ).join(self.AllUsers)
        if user_name:
            query = query.filter(self.AllUsers.user_name == user_name)
        return query.all()

    # Функция возвращает количество переданных и полученных сообщений
    def get_user_stat(self, user_name=None):
        query = self.session.query(
            self.AllUsers.user_name,
            self.AllUsers.last_login_time,
            self.UsersStats.sent,
            self.UsersStats.received
        ).join(self.AllUsers)
        if user_name:
            query = query.filter(self.AllUsers.user_name == user_name)
        # Возвращаем список кортежей
        return query.all()

    # Функция фиксирует передачу сообщения и делает соответствующие отметки в БД
    def process_message(self, sender, recipient):
        # Получаем ID отправителя и получателя
        sender = self.session.query(self.AllUsers).filter_by(user_name=sender).first().id
        # Запрашиваем строки из истории и увеличиваем счётчики
        sender_row = self.session.query(self.UsersStats).filter_by(user_id=sender).first()
        sender_row.sent += 1

        # Если указан получатель, иначе для всех активных
        if recipient:
            recipient = self.session.query(self.AllUsers).filter_by(user_name=recipient).first().id
            recipient_row = self.session.query(self.UsersStats).filter_by(user_id=recipient).first()
            recipient_row.received += 1
        else:
            for recipient in self.session.query(self.ActiveUsers).all():
                recipient_row = self.session.query(self.UsersStats).filter_by(user_id=recipient.user_id).first()
                recipient_row.received += 1
        self.session.commit()


# Тест работы
if __name__ == '__main__':
    db = ServerDB('client/server_base.db3')
    db.user_login('Василий', '192.168.1.4', 8888)
    db.user_login('Анатолий', '192.168.1.5', 7778)
    print(f'{db.get_all_users_list()=}')
    # выводим список кортежей - активных пользователей
    print(f'{db.get_active_users_list()=}')
    # выполянем 'отключение' пользователя
    db.user_logout('Василий')
    print('db.user_logout("Василий")')
    print(f'{db.get_all_users_list()=}')
    # выполянем 'отключение' пользователя
    db.add_contact('Василий', 'Анатолий')
    print(f'{db.get_contacts("Василий")=}')
    db.del_contact('Василий', 'Анатолий')
    print(f'{db.get_contacts("Василий")=}')
    # выводим список активных пользователей
    print(f'{db.get_active_users_list()=}')
    db.user_logout('Анатолий')
    print('db.user_logout("Анатолий")')
    print(f'{db.get_all_users_list()=}')
    print(f'{db.get_active_users_list()=}')
