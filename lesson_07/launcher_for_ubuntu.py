"""
It is a launcher for starting subprocesses for server_dist and clients of two types: senders and listeners.
for more information:
https://stackoverflow.com/questions/67348716/kill-process-do-not-kill-the-subprocess-and-do-not-close-a-terminal-window
"""

import os
import signal
import subprocess
import sys
from time import sleep


def main(clients):
    PYTHON_PATH = sys.executable
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

    def get_subprocess(file_with_args):
        sleep(0.4)
        file_full_path = f"{PYTHON_PATH} {BASE_PATH}/{file_with_args}"
        args = ["gnome-terminal", "--disable-factory", "--", "bash", "-c", file_full_path]
        return subprocess.Popen(args, preexec_fn=os.setpgrp)

    process = []
    while True:
        TEXT_FOR_INPUT = "Выберите действие: q - выход, s - запустить сервер и клиенты, x - закрыть все окна: "
        action = input(TEXT_FOR_INPUT)

        if action == "q":
            break
        elif action == "s":
            process.append(get_subprocess("start_server.py"))

            for i in range(clients):
                process.append(get_subprocess(f"start_client.py "
                                              f"-a 127.0.0.1 "
                                              f"-p 7777 "
                                              f"-name test{i + 1} "
                                              f"-pwd 123456"))

        elif action == "x":
            while process:
                victim = process.pop()
                os.killpg(victim.pid, signal.SIGINT)


if __name__ == '__main__':
    main(3)
