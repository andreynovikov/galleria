def diff(a, b):
    """
    Diffs two arrays without respect to order and duplication

    :param a: source list
    :param b: difference list
    :return: returns list containing elements of `a` not present in `b`
    """
    b = set(b)
    return [aa for aa in a if aa not in b]


def kill_char(string, n):
    begin = string[:n]
    end = string[n+1:]
    return begin + end


def to_list(str):
    return str.split(',') if str else []
