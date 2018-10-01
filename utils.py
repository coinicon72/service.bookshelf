import os, hashlib, re


COVER_PIC_DIR = './static/cover/'
URL_COVER_PIC_ROOT = '/static/cover/'

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

email_regex = re.compile("^[a-zA-Z0-9\\+\\.\\_\\%\\-\\+]{1,256}" +\
            "\\@" +\
            "[a-zA-Z0-9][a-zA-Z0-9\\-]{0,64}" +\
            "(" +\
                "\\." +\
                "[a-zA-Z0-9][a-zA-Z0-9\\-]{0,25}" +\
            ")+$"\
        , re.M)


def generate_password_hash(pwd):
    '''sha256 hash of password'''
    if pwd is None or len(pwd) == 0:
        return None

    m = hashlib.sha256()
    m.update(pwd.encode('utf-8'))
    return m.hexdigest()


def check_password_hash(hashed_pwd, pwd):
    return hashed_pwd == generate_password_hash(pwd)


# ================================================
ISBN_LEN = 13
ISBN10_LEN = 10

# exclude
MAX_ISBN = (10 ** ISBN_LEN) - 1
MIN_ISBN = 10 ** (ISBN_LEN - 2)

MAX_ISBN10 = (10 ** ISBN10_LEN) - 1
MIN_ISBN10 = 10 ** (ISBN10_LEN - 1)


def check_and_fix_isbn(isbn):
    '''check_and_fix_isbn'''
    # for a 13-digit ISBN, a prefix element – a GS1 prefix: so far 978 or 979 have been made available by GS1
    # the registration group element, (language-sharing country group, individual country or territory)
    # the registrant element,
    # the publication element,[11] and
    # a checksum character or check digit.[11]

    #     s = 9×1 + 7×3 + 8×1 + 0×3 + 3×1 + 0×3 + 6×1 + 4×3 + 0×1 + 6×3 + 1×1 + 5×3
    #   =   9 +  21 +   8 +   0 +   3 +   0 +   6 +  12 +   0 +  18 +   1 +  15
    #   = 93
    # 93 / 10 = 9 remainder 3
    # 10 –  3 = 7

    # if isbn > MAX_ISBN or isbn < MIN_ISBN:
    #     return None

    l = []
    strisbn = str(isbn)
    for n in strisbn:
        l.append(int(n))

    # check isbn length, allow 12 or 13
    ll = len(l)
    if ll > 14 or ll < 12:
        return None

    # remove check digit
    if ll == ISBN_LEN:
        del l[12]

    # check prefix
    if not (l[0] == 9 and l[1] == 7 and (l[2] == 8 or l[2] == 9)):
        return None

    # calculate check digit
    total = 0
    for i in range(len(l)):
        if i % 2 == 0:
            total += l[i]
        else:
            total += l[i] * 3

    check_digit = 10 - (total % 10)
    l.append(check_digit)

    strisbn = ''.join(str(x) for x in l)
    return int(strisbn)