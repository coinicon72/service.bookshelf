import os, threading, re, hashlib, json
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.exc import IntegrityError, DatabaseError
from flask import Flask, render_template, request, session, g, \
    redirect, url_for, abort, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import traceback
import requests

import urllib.request
from urllib.error import HTTPError, URLError

# pylint: disable=C0103

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

# email_regex.match()

# m = hashlib.sha256()
# m.update('coin'.encode('utf-8'))
# print(m.hexdigest())

app = Flask(__name__) # create the application instance :)
app.config.from_object(__name__) # load config from this file , flaskr.py

# Load default config and override config from an environment variable
db_full_path = os.path.join(app.root_path, 'bookshelf.db')
app.config.update(dict(
    DATABASE=db_full_path,
    SQLALCHEMY_DATABASE_URI='sqlite:///' + db_full_path,
    SQLALCHEMY_TRACK_MODIFICATIONS='true',
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

db = SQLAlchemy(app)

# def connect_db():
#     """Connects to the specific database."""
#     rv = sqlite3.connect(app.config['DATABASE'])
#     rv.row_factory = sqlite3.Row
#     return rv

# def get_db():
#     """Opens a new database connection if there is none yet for the
#     current application context.
#     """
#     if not hasattr(g, 'sqlite_db'):
#         g.sqlite_db = connect_db()
#     return g.sqlite_db

# @app.teardown_appcontext
# def close_db(error):
#     """Closes the database again at the end of the request."""
#     if hasattr(g, 'sqlite_db'):
#         g.sqlite_db.close()

class User(db.Model):
    '''model of user'''
    id = db.Column(db.Integer, nullable=False, autoincrement=True, primary_key=True)
    email = db.Column(db.String, nullable=False, unique=True)
    phone = db.Column(db.Integer, unique=True)
    name = db.Column(db.String, nullable=False)
    hashed_password = db.Column(db.String, nullable=False)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.hashed_password = generate_password_hash(password)

    register_date = db.Column(db.DateTime, default=datetime.utcnow())

    token = db.relationship('Token', backref='user', lazy='dynamic')
    books = db.relationship('UserBook', backref='belong_to', lazy='dynamic')


    def verify_password(self, password):
        return check_password_hash(self.hashed_password, password)

    def __init__(self, email, phone, name):
        self.email = email
        self.phone = phone
        self.name = name

    def toJSON(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'name': self.name,
            'register_date': self.register_date
        }

    def __repr__(self):
        return '<User {} - {} - {} @ {}>'.format(self.email, self.phone, \
                self.name, self.register_date)


class Token(db.Model):
    '''model of user'''
    token = db.Column(db.String, nullable=False, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    create_time = db.Column(db.DateTime, nullable=False)
    expire_time = db.Column(db.DateTime, nullable=False)

    def __init__(self, token, user_id, create_time, expire_time):
        self.token = token
        self.user_id = user_id
        self.create_time = create_time
        self.expire_time =expire_time

    def is_expired(self):
        '''check if this token is expired'''
        if self.expire_time is None:
            return True

        return datetime.utcnow() > self.expire_time

    def toJSON(self):
        return {
            'token': self.token,
            'user_id': self.user_id,
            'create_time': self.create_time.strftime(DATETIME_FORMAT),
            'expire_time': self.expire_time.strftime(DATETIME_FORMAT)
        }

    def __repr__(self):
        return '<Token {}: {} -> {}>'.format(self.token, self.create_time, self.expire_time)


def generate_password_hash(pwd):
    '''sha256 hash of password'''
    if pwd is None or len(pwd) == 0:
        return None

    m = hashlib.sha256()
    m.update(pwd.encode('utf-8'))
    return m.hexdigest()


def check_password_hash(hashed_pwd, pwd):
    return hashed_pwd == generate_password_hash(pwd)


# user = User('c@d.e', 18974871972, 'kevin')

# try:
#     db.session.add(user)
#     db.session.commit()
# except IntegrityError as e:
#     db.session.rollback()
# except DatabaseError as e:
# # except sqlite3.DatabaseError as e:
#     db.session.rollback()


@app.route("/user", methods=['POST'])
def register_user():
    '''register a new user'''
    if request.content_type == "application/json":
        json_data = request.get_json()
        if json_data is not None:
            _email = json_data.get('email')
            _phone = json_data.get('phone')
            _name = json_data.get('name')
            _pwd = json_data.get('password')
    else:
        _email = request.form.get('email')
        _phone = request.form.get('phone')
        _name = request.form.get('name')
        _pwd = request.form.get('password')

    if _email is None or _name is None or _pwd is None:
        return jsonify({'result':-10, 'msg':'missing required parameter(s)', \
            'required': [{'name': 'email'}, {'name': 'name'}, {'name': 'password'}]})

    if email_regex.match(_email) is None:
        return jsonify({'result':-11, 'msg':'invalid parameter', \
            'reason': 'invalid format', 'parameter(s)': [{'name': 'email', 'value': _email}]})

    if len(_pwd) <= 3:
        return jsonify({'result':-11, 'msg':'invalid parameter', \
            'reason': 'too short', 'parameter(s)': [{'name': 'password'}]})

    user = User(_email, _phone, _name)
    user.password = _pwd

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError as e:
        return jsonify({'result':-21, 'msg':'database integrity error: %s' % e})
    except DatabaseError as e:
        return jsonify({'result':-20, 'msg':'database error: %s' % e})

    return jsonify({'result': 0, 'data': user.toJSON()})


@app.route("/token")
def get_access_token():
    '''get a user access token
    url: /token?email=xxx&password=yyy
    '''
    _email = request.args.get('email')
    _pwd = request.args.get('password')

    if _email is None or _pwd is None:
        return jsonify({'result':-10, 'msg':'missing required parameter(s)', \
            'required': [{'name': 'email'}, {'name': 'password'}]})

    #
    user = User.query.filter_by(email=_email).first()
    if user is None:
        return jsonify({'result':-30, 'msg':'User not found'})

    if not user.verify_password(_pwd):
        return jsonify({'result':-31, 'msg':'Wrong password'})

    try:
        token = Token(generate_token(), user.id, datetime.utcnow(), \
                    datetime.utcnow() + timedelta(days=7))
        db.session.add(token)
        db.session.commit()
    except IntegrityError as e:
        return jsonify({'result':-21, 'msg':'database integrity error: %s' % e})
    except DatabaseError as e:
        return jsonify({'result':-20, 'msg':'database error: %s' % e})

    return jsonify({'result': 0, 'data': token.toJSON()})


def generate_token():
    '''use os.urandom to generate a 16 bytes (32 chars) token'''
    return ''.join('{:02x}'.format(x) for x in os.urandom(16))

class Book(db.Model):
    '''model of table book'''
    isbn = db.Column(db.Integer, primary_key=True)
    isbn10 = db.Column(db.Integer, unique=True)
    title = db.Column(db.String, nullable=False)
    subtitle = db.Column(db.String)
    summary = db.Column(db.Text)
    author = db.Column(db.String, nullable=False)
    publisher = db.Column(db.String)
    pub_date = db.Column(db.String)
    binding = db.Column(db.String)
    page = db.Column(db.Integer)
    price = db.Column(db.Float)
    pic = db.Column(db.String)
    content = db.Column(db.Text)
    org_pic = db.Column(db.String)
    
    belong_to = db.relationship('UserBook', backref="detail", lazy='dynamic')

    def __init__(self, isbn, title, author):
        self.isbn = isbn
        self.title = title
        self.author = author

    def toJSON(self):
        return {
            'isbn': self.isbn,
            'isbn10': self.isbn10,
            'title': self.title,
            'subtitle': self.subtitle,
            'summary': self.summary,
            'author': self.author,
            'publisher': self.publisher,
            'pub_date': self.pub_date,
            'binding': self.binding,
            'page': self.page,
            'price': self.price,
            'pic': self.pic,
            'content': self.content
        }

    def __repr__(self):
        return '<Book {} - {}>'.format(self.isbn, self.title)

# import json
# b = Book('1234567890124', 'test', 'myself')
# print(jsonify(b.__dict__))


class UserBook(db.Model):
    rid = db.Column(db.Integer, nullable=False, autoincrement=True, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    book_isbn = db.Column(db.Integer, db.ForeignKey('book.isbn'))
    add_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow())
    comment = db.Column(db.Text)

    def __init__(self, user_id, book_isbn, comment):
        self.user_id = user_id
        self.book = book_isbn
        self.add_date = datetime.utcnow()
        self.comment = comment

# class DateEncoder(json.JSONEncoder):
# 	def default(self, obj):
# 		if isinstance(obj, datetime):
# 			return obj.__str__()
# 		return json.JSONEncoder.default(self, obj)

class UserBookEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UserBook):
            return {'rid': obj.rid, 'add_date': obj.add_date.strftime('%Y-%m-%dT%H:%M:%S'), \
                        'comment': obj.comment, 'detail': obj.detail.toJSON()}
        return json.JSONEncoder.default(self, obj)

class CheckRecord(db.Model):
    '''model of table check_record'''
    isbn = db.Column(db.Integer, primary_key=True)
    last_check_time = db.Column(db.DateTime)
    check_count = db.Column(db.Integer)

    def __init__(self, isbn):
        self.isbn = isbn
        self.last_check_time = datetime.now()
        self.check_count = 1

    def __repr__(self):
        return '<CheckRecord %r, last_check_time: %d>' % self.isbn, self.last_check_time

# try:
#     b = Book('1234567890124', 'test', 'myself')
#     db.session.add(b)
#     db.session.commit()
# except Exception as e:
#     db.session.rollback()


# set FLASK_DEBUG=1

# export FLASK_APP=hello.py
# flask run

# Externally Visible Server
# flask run --host=0.0.0.0

@app.route("/")
def main():
    '''main view'''
    return render_template('hello.html')


# ================================================
ISBN_LEN = 13
ISBN10_LEN = 10

# exclude
MAX_ISBN = (10 ** ISBN_LEN) - 1
MIN_ISBN = 10 ** (ISBN_LEN - 2)

MAX_ISBN10 = (10 ** ISBN10_LEN) - 1
MIN_ISBN10 = 10 ** (ISBN10_LEN - 1)


@app.route("/isbn/<int:isbn>")
def get_book_by_isbn(isbn):
    '''get book info by isbn
    need token as query parameter, get token first
    url: /isbn/xxxxxx?token=yyyyyyy
    '''

    # check token
    # check_token_result = check_token(request)
    # if check_token_result[1] is not None:
    #     return check_token_result[1]

    # check isbn and/or fix check digit
    isbn = check_and_fix_isbn(isbn)
    if isbn is None:
        return jsonify({'result':-1, 'msg':'invalid isbn'})

    # check local db first
    book = Book.query.filter_by(isbn=isbn).first()
    if book is None:
        # check if this isbn in notfound list
        now = datetime.now()
        do_query = False

        check_record = CheckRecord.query.filter_by(isbn=isbn).first()
        if check_record is None:
            # query book info from internet
            do_query = True
            book = queue_to_get_book_info(isbn) # query_book_from_internet(isbn)
        else:
            delta = now - check_record.last_check_time
            if delta.days >= 1:
                # re-query book info from internet
                do_query = True
                book = queue_to_get_book_info(isbn) # query_book_from_internet(isbn)

        if do_query:
            if book is None:
                # if still can't get book info from internet
                # update count of check record
                if check_record is None:
                    check_record = CheckRecord(isbn)
                else:
                    check_record.last_check_time = datetime.now()
                    check_record.check_count += 1

                try:
                    db.session.add(check_record)
                    db.session.commit()
                except DatabaseError as e:
                    db.session.rollback()

                return jsonify({'result':-404, 'msg':'not found'})
            else:
                try:
                    db.session.add(book)
                    db.session.commit()
                except IntegrityError as e:
                    # ignore this error silently
                    db.session.rollback()
                except DatabaseError as e:
                    return jsonify({'result':-20, 'msg':'database error: %s' % e})

        else:
            return jsonify({'result':-404, 'msg':'not found'})

    else:
        # check and download pic
        suffix = '.' + book.pic.split('.')[-1]
        cover_pic_file_name = COVER_PIC_DIR + str(book.isbn) + suffix
        if not os.path.exists(cover_pic_file_name):
            downloadCoverPic(book.pic, cover_pic_file_name)

    return jsonify({'result': 0, 'data': book.toJSON()})

lock = threading.Lock()
query_queue = {}
executor = ThreadPoolExecutor()


def check_token(_request):
    '''get token from query string and check for expiration'''
    str_token = _request.args.get('token')
    if str_token is None:
        return (None, jsonify({'result':-10, 'msg':'missing required parameter(s)', \
                    'required': [{'name': 'token'}]}))

    token = Token.query.filter_by(token=str_token).first()
    if token is None:
        return (None, jsonify({'result':-30, 'msg':'token not found'}))

    if token.user is None:
        return (None, jsonify({'result':-41, 'msg':'user not exist'}))

    if token.is_expired():
        try:
            db.session.delete(token)
            db.session.commit()
        except DatabaseError as e:
            db.session.rollback()

        return (token.user, jsonify({'result':-31, 'msg':'token expired'}))

    return (token.user, None)


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
    if ll == 13:
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

# i = check_and_fix_isbn(9787535631953)
# print(i)


def queue_to_get_book_info(isbn):
    '''add a book query request into queue, if a request (same isbn) already exist, wait for it'''
    lock.acquire()
    if isbn in query_queue:
        f = query_queue[isbn]
        lock.release()
        if f is None:
            return None
        else:
            return f.result()
    else:
        f = executor.submit(query_book_from_internet, isbn)
        query_queue[isbn] = f
        lock.release()

        book = f.result()
        try:
            del query_queue[isbn]
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




# @app.route("/shelf/count")
# def get_books_number_from_shelf():
#     '''get books number from user's shelf
#     rid: optional parameter, returns books which's rid great then this parameter, or all books

#     url: /shelf/count?token=xxxx&rid=nnn
#     '''

#     #
#     check_token_result = check_token(request)
#     if check_token_result[1] is not None:
#         return check_token_result[1]

#     user = check_token_result[0]

#     #
#     _rid = request.args.get('rid')
#     if _rid is None:
#         _rid = 0

#     rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid).count()

#     return jsonify({'result': 0, 'data': rs})


# @app.route("/user/<int:uid>/shelf")
@app.route("/shelf")
def get_books_from_shelf():
    '''all books from user's shelf
    rid: optional parameter, returns books which's rid great then this parameter, or all books
    page: optional parameter, default=20, how many books this query returns
    url: /shelf?token=xxxx&rid=nnn&page=10
    '''

    #
    check_token_result = check_token(request)
    if check_token_result[1] is not None:
        return check_token_result[1]

    user = check_token_result[0]

    #
    _rid = request.args.get('rid', 0, type=int)

    _page = request.args.get('page', 20, type=int)
    if _page > 20:
        _page = 20

    # if _page is None:
    #     rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid).all()
    #     return jsonify({'result': 0, 'data': json.loads(json.dumps(rs, cls=UserBookEncoder))})
    # else:
    rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid)\
                                .order_by(UserBook.rid).paginate(1, _page)
    # rs = db.Session.query(Book, UserBook).join(UserBook) \
    #         .filter_by(user_id == user.id, rid > _rid).all()
    return jsonify({'result': 0, 'count': rs.total, 'more': rs.has_next, \
                    'per_page': rs.per_page, 'pages': rs.pages, \
                    'data': json.loads(json.dumps(rs.items, cls=UserBookEncoder))})



@app.route("/shelf/book/<int:isbn>", methods=['POST'])
def add_book_to_shelf(isbn):
    '''add a book to user's shelf'''

    # check token
    check_token_result = check_token(request)
    if check_token_result[1] is not None:
        return check_token_result[1]

    user = check_token_result[0]

    #
    book = Book.query.filter_by(isbn=isbn).first()
    if book is None:
        return jsonify({'result':-41, 'msg':'book not found'})

    #
    user_book = UserBook(user.id, book.isbn, None)

    try:
        db.session.add(user_book)
        db.session.commit()
    except IntegrityError as e:
        return jsonify({'result':-21, 'msg':'database integrity error: %s' % e})
    except DatabaseError as e:
        return jsonify({'result':-20, 'msg':'database error: %s' % e})

    return jsonify({'result': 0, 'msg': 'book {}-{} added to shelf'.format(book.isbn, book.title)})


@app.route("/book", methods=['POST'])
def upload_book():
    '''upload a book'''
    if request.content_type == "application/json":
        json_data = request.get_json()
        if json_data is not None:
            _isbn = json_data.get('isbn')
            _isbn10 = json_data.get('isbn10')
            _title = json_data.get('title')
            _subtitle = json_data.get('subtitle')
            _summary = json_data.get('summary')
            _author = json_data.get('author')
            _publisher = json_data.get('publisher')
            _pubd_ate = json_data.get('pub_date')
            _binding = json_data.get('binding')
            _page = json_data.get('page')
            _price = json_data.get('price')
            _pic = json_data.get('pic')
            _content = json_data.get('content')
    else:
        _isbn = request.form.get('isbn')
        _isbn10 = request.form.get('isbn10')
        _title = request.form.get('title')
        _subtitle = request.form.get('subtitle')
        _summary = request.form.get('summary')
        _author = request.form.get('author')
        _publisher = request.form.get('publisher')
        _pub_date = request.form.get('pub_date')
        _binding = request.form.get('binding')
        _page = request.form.get('page')
        _price = request.form.get('price')
        _pic = request.form.get('pic')
        _content = request.form.get('content')

    try:
        book = Book(_isbn, _title, _author)

        book.isbn10 = _isbn10
        book.subtitle = _subtitle
        book.summary = _summary
        book.publisher = _publisher
        book.pub_date = _pub_date
        book.binding = _binding
        book.page = _page
        book.price = _price
        book.pic = _pic
        book.content = _content

        db.session.add(book)
        db.session.commit()

    except IntegrityError as e:
        return jsonify({'result':-21, 'msg':'database integrity error: %s' % e})
    except DatabaseError as e:
        return jsonify({'result':-20, 'msg':'database error: %s' % e})
        
    return jsonify({'result': 0, 'data': book.toJSON()})


if __name__ == "__main__":
    try:
        if not os.path.exists(COVER_PIC_DIR):
            os.makedirs(COVER_PIC_DIR)
    except Exception as e:
        print(e)

    app.run(host='0.0.0.0')
