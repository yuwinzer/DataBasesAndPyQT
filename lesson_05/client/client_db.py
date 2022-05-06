from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime


class ClientDB:
    Base = declarative_base()

    # Список всех пользователей
    class AllUsers(Base):
        __tablename__ = 'all_users'
        id = Column(Integer, primary_key=True)
        user_name = Column(String, unique=True)

        def __init__(self, user_name):
            self.user_name = user_name

    # Список контактов пользователя
    class UsersContacts(Base):
        __tablename__ = 'my_contacts'
        id = Column(Integer, primary_key=True)
        contact_name = Column(String, unique=True)

        def __init__(self, contact_name):
            self.contact_name = contact_name

    # Список сообщений
    class MessageHistory(Base):
        __tablename__ = 'my_messages'
        id = Column(Integer, primary_key=True)
        from_name = Column(String)
        to_name = Column(String)
        msg = Column(Text)
        date = Column(DateTime)

        def __init__(self, from_name, to_name, msg):
            self.from_name = from_name
            self.to_name = to_name
            self.msg = msg
            self.date = datetime.now()

    # Инициализация
    def __init__(self, path):  # client/server_base.db3
        self.engine = create_engine(f'sqlite:///{path}?check_same_thread=False',
                                    echo=False, pool_recycle=7200, encoding='utf-8')
        self.Base.metadata.create_all(self.engine)

        Session = scoped_session(sessionmaker(bind=self.engine))
        self.session = Session()

        self.session.query(self.UsersContacts).delete()
        self.session.commit()

    # Добавление пользователя в контакты
    def add_contact(self, contact_name):
        if not self.session.query(self.UsersContacts).filter_by(contact_name=contact_name).count():
            self.session.add(self.UsersContacts(contact_name))
            self.session.commit()

    # Добавление пользователя в контакты
    def del_contact(self, contact_name):
        self.session.query(self.UsersContacts).filter_by(contact_name=contact_name).delete()
        self.session.commit()

    # Пересоздание списка пользователей
    def update_users(self, users_list):
        self.session.query(self.AllUsers).delete()
        for user in users_list:
            self.session.add(self.AllUsers(user))
        self.session.commit()

    # Пересоздание списка пользователей
    def update_contacts(self, contacts_list):
        self.session.query(self.UsersContacts).delete()
        for user in contacts_list:
            self.session.add(self.UsersContacts(user))
        self.session.commit()

    # Добавление сообщения
    def add_message(self, from_name, to_name, msg):
        self.session.add(self.MessageHistory(from_name, to_name, msg))
        self.session.commit()

    # Чтение пользователей
    def get_users(self):
        return [user[0] for user in self.session.query(self.AllUsers.user_name).all()]

    # Чтение контактов
    def get_contacts(self):
        return [contact[0] for contact in self.session.query(self.UsersContacts.contact_name).all()]

    # Чтение сообщений
    def get_history(self, contact):
        query = self.session.query(self.MessageHistory).filter_by(contact=contact)
        return [(m.from_name, m.to_name, m.msg, str(m.date)) for m in query.all()]

    # Чтение сообщений
    # def get_messages(self, from_name=None, to_name=None):
    #     query = self.session.query(self.MessageHistory)
    #     if from_name:
    #         query = query.filter_by(from_name=from_name)
    #     if to_name:
    #         query = query.filter_by(to_name=to_name)
    #     return [(m.from_name, m.to_name, m.msg, str(m.date)) for m in query.all()]

    # Функция проверяет наличие пользователя в таблице Известных Пользователей
    def check_user(self, name):
        if self.session.query(self.AllUsers).filter_by(user_name=name).count():
            return True
        else:
            return False

    # Функция проверяет наличие пользователя в таблице Контактов
    def check_contact(self, contact):
        if self.session.query(self.UsersContacts).filter_by(contact_name=contact).count():
            return True
        else:
            return False


# отладка
if __name__ == '__main__':
    test_db = ClientDB('test1')
    for i in ['test3', 'test4', 'test5']:
        test_db.add_contact(i)
    test_db.add_contact('test4')
    test_db.update_users(['test1', 'test2', 'test3', 'test4', 'test5'])
    test_db.add_message('test1', 'test2', f'Привет! я тестовое сообщение #1')
    test_db.add_message('test2', 'test1', f'Привет! я другое тестовое сообщение #2')
    print(test_db.get_contacts())
    print(test_db.get_users())
    print(test_db.get_messages())
    print(test_db.check_user('test1'))
    print(test_db.check_user('test10'))
    print(test_db.get_messages('test2'))
    print(test_db.get_messages(to_name='test2'))
    print(test_db.get_messages('test3'))
    test_db.del_contact('test4')
    print(test_db.get_contacts())
