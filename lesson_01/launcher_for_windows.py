"""Лаунчер"""

import subprocess
from time import sleep

PROCESS = []

while True:
    ACTION = input('Выберите действие: q - выход, '
                   's - запустить сервер и клиенты, x - закрыть все окна: ')

    if ACTION == 'q':
        break
    elif ACTION == 's':
        PROCESS.append(subprocess.Popen('python server.py',
                                        creationflags=subprocess.CREATE_NEW_CONSOLE))
        sleep(1.4)
        for i in range(1):
            PROCESS.append(subprocess.Popen('python client.py -a 127.0.0.1 -n "Олег"',
                                            creationflags=subprocess.CREATE_NEW_CONSOLE))
        for i in range(1):
            PROCESS.append(subprocess.Popen('python client.py -a 127.0.0.1 -n "Никита"',
                                            creationflags=subprocess.CREATE_NEW_CONSOLE))
        for i in range(1):
            PROCESS.append(subprocess.Popen('python client.py -a 127.0.0.1',
                                            creationflags=subprocess.CREATE_NEW_CONSOLE))
    elif ACTION == 'x':
        while PROCESS:
            VICTIM = PROCESS.pop()
            VICTIM.kill()

