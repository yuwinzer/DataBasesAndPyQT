""" 2. Написать функцию host_range_ping() для перебора ip-адресов из заданного диапазона.
Меняться должен только последний октет каждого адреса. По результатам проверки должно
выводиться соответствующее сообщение"""

from task_1 import host_ping
from ipaddress import ip_address
from pprint import pprint


def host_range_ping(ret):
    while True:
        try:
            ip_start = ip_address(input('Введите начальный ip адрес: '))
            break
        except Exception as e:
            print(e)

    while True:
        try:
            ip_amt_max = 256 - int(str(ip_start).split('.')[3])
            ip_amt = int(input(f'Введите количество адресов (1-{ip_amt_max}): '))
            if not 0 < ip_amt < ip_amt_max + 1:
                raise Exception('Кому диапазон написан?')
            break
        except Exception as e:
            print(e)

    result = host_ping([ip_start + i for i in range(ip_amt-1)], True)
    if ret:
        return result
    else:
        pprint(result)


if __name__ == '__main__':
    host_range_ping(False)
