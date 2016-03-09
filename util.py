import struct
import socket


def diff(a, b):
    """
        Diffs to arrays without respect to order and duplication

    :param a: source list
    :param b: difference list
    :return: returns list containing elements of `a` not present in `b`
    """
    b = set(b)
    return [aa for aa in a if aa not in b]


def ip2int(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]


def int2ip(addr):
    return socket.inet_ntoa(struct.pack("!I", addr))
