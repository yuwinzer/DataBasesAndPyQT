"""1. Начать реализацию класса «Хранилище» для серверной стороны.
Хранение необходимо осуществлять в базе данных.
В качестве СУБД использовать sqlite. Для взаимодействия с БД можно применять ORM.
Опорная схема базы данных:
На стороне сервера БД содержит следующие таблицы:
a) клиент:
    * логин;
    * информация.
b) история клиента:
    * время входа;
    * ip-адрес.
c) список активных пользователей :
    * id клиента;
    * адрес:
    * port;
    * login_time."""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime


class ServerDB:
    Base = declarative_base()

    class AllUsers(Base):
        __tablename__ = 'all_users'
        id = Column(Integer, primary_key=True)
        user_name = Column(String, unique=True)
        last_login_time = Column(DateTime)

        def __init__(self, user_name):
            self.user_name = user_name
            self.last_login_time = datetime.now()

    class ActiveUsers(Base):
        __tablename__ = 'active_users'
        id = Column(Integer, primary_key=True)
        user_id = Column(String, ForeignKey('all_users.id'), unique=True)
        ip = Column(String)
        port = Column(Integer)
        login_time = Column(DateTime)

        def __init__(self, user_id, ip, port, login_time):
            self.user_id = user_id
            self.ip = ip
            self.port = port
            self.login_time = login_time

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

    def __init__(self):
        self.engine = create_engine('sqlite:///database/server_base.db3?check_same_thread=False',
                                    echo=False, pool_recycle=7200, encoding='utf-8')
        self.Base.metadata.create_all(self.engine)
        Session = scoped_session(sessionmaker(bind=self.engine))
        self.session = Session()

        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    def user_login(self, user_name, ip, port):
        searchable_user = self.session.query(self.AllUsers).filter_by(user_name=user_name)
        if searchable_user.count():
            user = searchable_user.first()
            user.last_login_time = datetime.now()
        else:
            user = self.AllUsers(user_name)
            self.session.add(user)
            self.session.commit()
        # print(f'{user.user_name=}')
        new_active_user = self.ActiveUsers(user.id, ip, port, datetime.now())
        self.session.add(new_active_user)
        user_history = self.LoginHistory(user.id, ip, port, datetime.now())
        self.session.add(user_history)
        self.session.commit()

    def user_logout(self, user_name):
        user = self.session.query(self.AllUsers).filter_by(user_name=user_name).first()
        # print(f'{user.id=}')
        self.session.query(self.ActiveUsers).filter_by(user_id=user.id).delete()
        self.session.commit()

    def get_all_users_list(self):
        query = self.session.query(self.AllUsers.user_name, self.AllUsers.last_login_time)
        return query.all()

    def get_active_users_list(self):
        query = self.session.query(
            self.AllUsers.user_name,
            self.ActiveUsers.ip,
            self.ActiveUsers.port,
            self.ActiveUsers.login_time
        ).join(self.AllUsers)
        return query.all()

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


# Тест работы
if __name__ == '__main__':
    db = ServerDB()
    db.user_login('client_1', '192.168.1.4', 8888)
    db.user_login('client_2', '192.168.1.5', 7777)
    print(f'{db.get_all_users_list()=}')
    # выводим список кортежей - активных пользователей
    print(f'{db.get_active_users_list()=}')
    # выполянем 'отключение' пользователя
    db.user_logout('client_1')
    print('db.user_logout("client_1")')
    print(f'{db.get_all_users_list()=}')
    # выводим список активных пользователей
    print(f'{db.get_active_users_list()=}')
    db.user_logout('client_2')
    print('db.user_logout("client_2")')
    print(f'{db.get_all_users_list()=}')
    print(f'{db.get_active_users_list()=}')
