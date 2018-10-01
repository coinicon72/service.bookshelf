import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib.request
from urllib.error import HTTPError, URLError

from dao import Book
from utils import URL_COVER_PIC_ROOT, COVER_PIC_DIR


_lock = threading.Lock()
_query_queue = {}
_executor = ThreadPoolExecutor()


def queue_to_get_book_info(isbn):
    '''add a book query request into queue, if a request (same isbn) already exist, wait for it'''
    _lock.acquire()
    if isbn in _query_queue:
        f = _query_queue[isbn]
        _lock.release()
        if f is None:
            return None
        else:
            return f.result()
    else:
        f = _executor.submit(query_book_from_internet, isbn)
        _query_queue[isbn] = f
        _lock.release()

        book = f.result()
        try:
            del _query_queue[isbn]
        except KeyError:
            pass
        return book

def query_book_from_internet(isbn):
    '''try get book info from internet'''
    try:
        response = requests.get('http://api.jisuapi.com/isbn/query?appkey=fcb21d46d079130b&isbn=' \
                    + str(isbn))

        # fake json service
        # response = requests.get('http://jsonplaceholder.typicode.com/users')

        # free weather service
        # response = requests.get('http://api.openweathermap.org/data/2.5/weather?appid=7f22b3079794cc7bb5970bddf8b308ee&units=metric&lang=zh_cn&q=changsha,cn')

        data = response.json()

        if data['status'] == '0':
            # got book info
            r = data['result']

            b = Book(r['isbn'], r['title'], r['author'])
            b.isbn10 = r['isbn10']
            b.subtitle = r['subtitle']
            b.summary = r['summary']
            b.publisher = r['publisher']
            b.pub_date = r['pub_date']
            b.binding = r['binding']
            b.page = r['page']
            b.price = r['price']
            b.org_pic = r['pic']
            b.content = r['class']

            # download pic
            if r['pic'] is not None:
                suffix = '.' + r['pic'].split('.')[-1]
                b.pic = URL_COVER_PIC_ROOT + r['isbn'] + suffix
                downloadCoverPic(r['pic'], COVER_PIC_DIR + r['isbn'] + suffix)

            return b
        else:
            return None
    except Exception as e:
        print(e)
        return None

#function that downloads a file
# def downloadFile(file_url, file_name, file_mode):
def downloadCoverPic(file_url, file_name):
    # Open the url
    try:
        f = urllib.request.urlopen(file_url)
        # print("downloading ", file_url)

        # Open our local file for writing
        local_file = open(file_name, "wb")

        #Write to our local file
        local_file.write(f.read())
        local_file.close()

    #handle errors
    except HTTPError as e:
        print("HTTP Error:", e.code, file_url)
    except URLError as e:
        print("URL Error:", e.reason, file_url)
    except Exception as e:
        print(e)
        