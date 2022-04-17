""" 1. Написать функцию host_ping(), в которой с помощью утилиты ping будет проверяться
доступность сетевых узлов. Аргументом функции является список, в котором каждый сетевой
узел должен быть представлен именем хоста или ip-адресом. В функции необходимо
перебирать ip-адреса и проверять их доступность с выводом соответствующего сообщения
(«Узел доступен», «Узел недоступен»). При этом ip-адрес сетевого узла должен создаваться с
помощью функции ip_address()"""

from ipaddress import ip_address
from subprocess import Popen, PIPE
import platform
import threading
from pprint import pprint
result = {'Узел доступен': [], 'Узел недоступен': []}
errors = []


def ping(ip):
    try:
        host = ip_address(ip)
    except Exception as e:
        errors.append(str(e))
        host = ip
    param = "-n" if platform.system().lower() == 'windows' else "-c"
    process = Popen(['ping', param, '1', '-w', '1', str(host)], stdout=PIPE)
    if process.wait():
        result['Узел недоступен'].append(str(ip))
    else:
        result['Узел доступен'].append(str(ip))


def host_ping(ip_addresses: list, ret):
    threads = []
    for ip in ip_addresses:
        thread = threading.Thread(target=ping, args=(ip,), daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

    if ret:
        return result
    else:
        pprint(errors)
        print('\n')
        pprint(result)


if __name__ == '__main__':
    host_ping(['google.com', 'apple.com', 'yandex.xxx', 'nasa.gov', '8.8.8.8', '0.0.0.1', '0.0.8.1'], False)
