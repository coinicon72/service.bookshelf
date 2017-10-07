import time, threading, random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

# future = None

# executor = ThreadPoolExecutor(max_workers=4)
# if f is None:
#   f = executor.commit(do_work)

def start():
    return do_work()
    # if future is None:
    #     # with ThreadPoolExecutor() as e:
    #     future = executor.submit(do_work)
    # else:
    #     print(future.result())


def do_work():
    print("+++ thread: {} @ {}".format(threading.get_ident(), datetime.now()))
    time.sleep(random.randint(3, 10))
    print("--- thread: {} @ {}".format(threading.get_ident(), datetime.now()))
    return threading.get_ident()

# e = ThreadPoolExecutor(max_workers=4)
# e.submit(start)
# e.submit(start)
# e.submit(start)
# e.submit(start)

with ThreadPoolExecutor() as executor:
    # print(executor.submit(start).result())
    # print(executor.submit(start).result())
    # print(executor.submit(start).result())
    # print(executor.submit(start).result())
    fs = []
    fs.append(executor.submit(start))
    fs.append(executor.submit(start))
    fs.append(executor.submit(start))
    fs.append(executor.submit(start))
    # f2 = executor.submit(start)
    # f3 = executor.submit(start)
    # f4 = executor.submit(start)

    for f in as_completed(fs):
        print("done: {} @ {}".format(f.result(), datetime.now()))
    # print(f1.result())
    # print(f2.result())
    # print(f3.result())
    # print(f4.result())
