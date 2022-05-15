"""Лаунчер. Если не работает, запускайте через start_server.bat и start_client_***.bat
Для корректного подключения клиентов на сервере дожны быть зарегистрированы пользователи:
test1, test1, test3 с паролем 123456
"""
import subprocess
from time import sleep


def main(clients):
    process = []

    while True:
        action = input('Выберите действие: q - выход, s - запустить сервер и клиенты, x - закрыть все окна: ')

        if action == 'q':
            break
        elif action == 's':

            # Запуск сервера
            process.append(subprocess.Popen('python start_server.py', creationflags=subprocess.CREATE_NEW_CONSOLE))
            sleep(1)

            # Запуск клиентов
            for i in range(clients):
                process.append(subprocess.Popen(f'python start_client.py '
                                                f'-a 127.0.0.1 '
                                                f'-p 7777 '
                                                f'-name test{i+1} '
                                                f'-pwd 123456',
                                                creationflags=subprocess.CREATE_NEW_CONSOLE))
        elif action == 'x':
            while process:
                process.pop().kill()


if __name__ == '__main__':
    main(3)
