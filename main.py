import os, threading, re, hashlib, json
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.exc import IntegrityError, DatabaseError
from flask import Flask, render_template, request, session, g, \
    redirect, url_for, abort, flash
from flask_restful import Resource, Api
from flask_sqlalchemy import SQLAlchemy
import traceback
import requests

from dao import *
from auth import TokenCheck, generate_token
from utils import COVER_PIC_DIR, email_regex, check_and_fix_isbn
from ext_book_service import queue_to_get_book_info, downloadCoverPic

# pylint: disable=C0103


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

api = Api(app)

# db = SQLAlchemy(app)
db.init_app(app)


# @app.route("/user", methods=['POST'])
# def register_user():
class UserResource(Resource):
    @TokenCheck
    def get(self, uid, **kwargs):
        user = User.query.filter_by(id=uid).first()
        return user.toJSON()

    @TokenCheck
    def post(self, **kwargs):
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
            return {'result':-10, 'msg':'missing required parameter(s)', 
                'required': [{'name': 'email'}, {'name': 'name'}, {'name': 'password'}]}

        if email_regex.match(_email) is None:
            return {'result':-11, 'msg':'invalid parameter', 
                'reason': 'invalid format', 'parameter(s)': [{'name': 'email', 'value': _email}]}

        if len(_pwd) <= 3:
            return {'result':-11, 'msg':'invalid parameter', 
                'reason': 'too short', 'parameter(s)': [{'name': 'password'}]}

        user = User(_email, _phone, _name)
        user.password = _pwd

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError as e:
            return {'result':-21, 'msg':'database integrity error: %s' % e}
        except DatabaseError as e:
            return {'result':-20, 'msg':'database error: %s' % e}

        return {'result': 0, 'data': user.toJSON()}

api.add_resource(UserResource, "/user", "/user/<int:uid>")


class AccessTokenResource(Resource):
    def post(self):
        '''get a user access token
        url: /token?email=xxx&password=yyy
        curl -u <email>:<password> /token
        '''
        _email = request.args.get('email')
        _pwd = request.args.get('password')

        if request.authorization is not None and _email is None:
            _email = request.authorization.username

        if request.authorization is not None and _pwd is None:
            _pwd = request.authorization.password

        if _email is None or _pwd is None:
            return {'result':-10, 'msg':'missing required parameter(s)', \
                'required': [{'name': 'email'}, {'name': 'password'}]}

        #
        user = User.query.filter_by(email=_email).first()
        if user is None:
            return {'result':-30, 'msg':'User not found'}

        if not user.verify_password(_pwd):
            return {'result':-31, 'msg':'Wrong password'}

        try:
            token = Token(generate_token(), user.id, datetime.utcnow(), \
                        datetime.utcnow() + timedelta(days=7))
            db.session.add(token)
            db.session.commit()
        except IntegrityError as e:
            return {'result':-21, 'msg':'database integrity error: %s' % e}
        except DatabaseError as e:
            return {'result':-20, 'msg':'database error: %s' % e}

        return {'result': 0, 'data': token.toJSON()}

api.add_resource(AccessTokenResource, '/token')

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


@app.route("/")
def main():
    '''main view'''
    return render_template('hello.html')


# @app.route("/isbn/<int:isbn>")
# @TokenCheck
# def get_book_by_isbn(isbn, **kwargs):
#     '''get book info by isbn
#     need token as query parameter, get token first
#     url: /isbn/xxxxxx?token=yyyyyyy
#     '''

#     # check token
#     # check_token_result = check_token(request)
#     # if check_token_result[1] is not None:
#     #     return check_token_result[1]

#     # check isbn and/or fix check digit
#     isbn = check_and_fix_isbn(isbn)
#     if isbn is None:
#         return {'result':-1, 'msg':'invalid isbn'}

#     # check local db first
#     book = Book.query.filter_by(isbn=isbn).first()
#     if book is None:
#         # check if this isbn in notfound list
#         now = datetime.now()
#         do_query = False

#         check_record = CheckRecord.query.filter_by(isbn=isbn).first()
#         if check_record is None:
#             # query book info from internet
#             do_query = True
#             book = queue_to_get_book_info(isbn) # query_book_from_internet(isbn)
#         else:
#             delta = now - check_record.last_check_time
#             if delta.days >= 1:
#                 # re-query book info from internet
#                 do_query = True
#                 book = queue_to_get_book_info(isbn) # query_book_from_internet(isbn)

#         if do_query:
#             if book is None:
#                 # if still can't get book info from internet
#                 # update count of check record
#                 if check_record is None:
#                     check_record = CheckRecord(isbn)
#                 else:
#                     check_record.last_check_time = datetime.now()
#                     check_record.check_count += 1

#                 try:
#                     db.session.add(check_record)
#                     db.session.commit()
#                 except DatabaseError as e:
#                     db.session.rollback()

#                 return {'result':-404, 'msg':'not found'}
#             else:
#                 try:
#                     db.session.add(book)
#                     db.session.commit()
#                 except IntegrityError as e:
#                     # ignore this error silently
#                     db.session.rollback()
#                 except DatabaseError as e:
#                     return {'result':-20, 'msg':'database error: %s' % e}

#         else:
#             return {'result':-404, 'msg':'not found'}

#     else:
#         # check and download pic
#         suffix = '.' + book.pic.split('.')[-1]
#         cover_pic_file_name = COVER_PIC_DIR + str(book.isbn) + suffix
#         if not os.path.exists(cover_pic_file_name):
#             downloadCoverPic(book.pic, cover_pic_file_name)

#     return {'result': 0, 'data': book.toJSON()}

# def check_token(_request):
#     '''get token from query string and check for expiration'''
#     str_token = _request.args.get('token')
#     if str_token is None:
#         return (None, {'result':-10, 'msg':'missing required parameter(s)', 
#                     'required': [{'name': 'token'}]}))

#     token = Token.query.filter_by(token=str_token).first()
#     if token is None:
#         return (None, {'result':-30, 'msg':'token not found'})

#     if token.user is None:
#         return (None, {'result':-41, 'msg':'user not exist'})

#     if token.is_expired():
#         try:
#             db.session.delete(token)
#             db.session.commit()
#         except DatabaseError:
#             db.session.rollback()

#         return (token.user, {'result':-31, 'msg':'token expired'})

#     return (token.user, None)


# i = check_and_fix_isbn(9787535631953)
# print(i)





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

#     return {'result': 0, 'data': rs}


# @app.route("/user/<int:uid>/shelf")
# @app.route("/shelf")
# class Shelf(Resource):
#     @TokenCheck
#     def get(self, user=None):
#         '''all books from user's shelf
#         rid: optional parameter, returns books which's rid great then this parameter, or all books
#         page: optional parameter, default=20, how many books this query returns
#         url: /shelf?token=xxxx&rid=nnn&page=10
#         '''

#         #
#         # check_token_result = check_token(request)
#         # if check_token_result[1] is not None:
#         #     return check_token_result[1]

#         # user = check_token_result[0]

#         #
#         _rid = request.args.get('rid', 0, type=int)

#         _page = request.args.get('page', 20, type=int)
#         if _page > 20:
#             _page = 20

#         # if _page is None:
#         #     rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid).all()
#         #     return {'result': 0, 'data': json.loads(json.dumps(rs, cls=UserBookEncoder))}
#         # else:
#         rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid)\
#                                     .order_by(UserBook.rid).paginate(1, _page)
#         # rs = db.Session.query(Book, UserBook).join(UserBook) \
#         #         .filter_by(user_id == user.id, rid > _rid).all()
#         return {'result': 0, 'count': rs.total, 'more': rs.has_next, 
#                         'per_page': rs.per_page, 'pages': rs.pages, \
#                         'data': json.loads(json.dumps(rs.items, cls=UserBookEncoder))})

# api.add_resource(Shelf, "/shelf", "/user/<int:uid>/shelf")


# @app.route("/shelf/book/<int:isbn>", methods=['POST'])
# def add_book_to_shelf(isbn):
class ShelfBookResource(Resource):
    @TokenCheck
    def get(self, user=None):
        '''all books from user's shelf
        rid: optional parameter, returns books which's rid great then this parameter, or all books
        page: optional parameter, default=20, how many books this query returns
        url: /shelf?token=xxxx&rid=nnn&page=10
        '''

        #
        # check_token_result = check_token(request)
        # if check_token_result[1] is not None:
        #     return check_token_result[1]

        # user = check_token_result[0]

        #
        _rid = request.args.get('rid', 0, type=int)

        _page = request.args.get('page', 20, type=int)
        if _page > 20:
            _page = 20

        # if _page is None:
        #     rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid).all()
        #     return {'result': 0, 'data': json.loads(json.dumps(rs, cls=UserBookEncoder))}
        # else:
        rs = UserBook.query.filter(UserBook.user_id == user.id, UserBook.rid > _rid)\
                                    .order_by(UserBook.rid).paginate(1, _page)
        # rs = db.Session.query(Book, UserBook).join(UserBook) \
        #         .filter_by(user_id == user.id, rid > _rid).all()
        return {'result': 0, 'count': rs.total, 'more': rs.has_next, 
                        'per_page': rs.per_page, 'pages': rs.pages, \
                        'data': json.loads(json.dumps(rs.items, cls=UserBookEncoder))}


    @TokenCheck
    def post(self, isbn, user=None):
        '''add a book to user's shelf'''

        # check token
        # check_token_result = check_token(request)
        # if check_token_result[1] is not None:
        #     return check_token_result[1]

        # user = check_token_result[0]

        #
        book = Book.query.filter_by(isbn=isbn).first()
        if book is None:
            return {'result':-41, 'msg':'book not found'}

        #
        user_book = UserBook(user.id, book.isbn, None)

        try:
            db.session.add(user_book)
            db.session.commit()
        except IntegrityError as e:
            return {'result':-21, 'msg':'database integrity error: %s' % e}
        except DatabaseError as e:
            return {'result':-20, 'msg':'database error: %s' % e}

        return {'result': 0, 'msg': 'book {}-{} added to shelf'.format(book.isbn, book.title)}

api.add_resource(ShelfBookResource, "/shelf/book", "/shelf/book/<int:isbn>")

# @app.route("/book", methods=['POST'])
# def upload_book():
class BookResoure(Resource):
    @TokenCheck
    def get(self, isbn, **kwargs):
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
            return {'result':-1, 'msg':'invalid isbn'}

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

                    return {'result':-404, 'msg':'not found'}
                else:
                    try:
                        db.session.add(book)
                        db.session.commit()
                    except IntegrityError as e:
                        # ignore this error silently
                        db.session.rollback()
                    except DatabaseError as e:
                        return {'result':-20, 'msg':'database error: %s' % e}

            else:
                return {'result':-404, 'msg':'not found'}

        else:
            # check and download pic
            suffix = '.' + book.pic.split('.')[-1]
            cover_pic_file_name = COVER_PIC_DIR + str(book.isbn) + suffix
            if not os.path.exists(cover_pic_file_name):
                downloadCoverPic(book.pic, cover_pic_file_name)

        return {'result': 0, 'data': book.toJSON()}


    @TokenCheck
    def post(self, **kwargs):
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
            return {'result':-21, 'msg':'database integrity error: %s' % e}
        except DatabaseError as e:
            return {'result':-20, 'msg':'database error: %s' % e}
            
        return {'result': 0, 'data': book.toJSON()}

api.add_resource(BookResoure, '/book', '/book/<int:isbn>')


if __name__ == "__main__":
    try:
        if not os.path.exists(COVER_PIC_DIR):
            os.makedirs(COVER_PIC_DIR)
    except Exception as e:
        print(e)

    app.run(host='0.0.0.0')
