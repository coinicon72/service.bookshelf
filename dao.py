from datetime import timedelta, datetime
from flask_sqlalchemy import SQLAlchemy

from utils import generate_password_hash, check_password_hash, DATETIME_FORMAT


db = SQLAlchemy()


class User(db.Model):
    '''model of user'''
    id = db.Column(db.Integer, nullable=False,
                   autoincrement=True, primary_key=True)
    email = db.Column(db.String, nullable=False, unique=True)
    phone = db.Column(db.String, unique=True)
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
            'register_date': self.register_date.strftime(DATETIME_FORMAT),
        }

    def __repr__(self):
        return '<User {} - {} - {} @ {}>'.format(self.email, self.phone,
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
        self.expire_time = expire_time

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


class UserBook(db.Model):
    rid = db.Column(db.Integer, nullable=False,
                    autoincrement=True, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    book_isbn = db.Column(db.Integer, db.ForeignKey('book.isbn'))
    add_date = db.Column(db.DateTime, nullable=False,
                         default=datetime.utcnow())
    comment = db.Column(db.Text)

    def __init__(self, user_id, book_isbn, comment):
        self.user_id = user_id
        self.book = book_isbn
        self.add_date = datetime.utcnow()
        self.comment = comment

    def toJSON(self):
        return {
            'rid': self.isbn,
            'user_id': self.user_id,
            'book_isbn': self.book_isbn,
            'add_date': self.add_date.strftime(DATETIME_FORMAT),
            'comment': self.comment,
        }


class CheckRecord(db.Model):
    '''model of table check_record'''
    isbn = db.Column(db.Integer, primary_key=True)
    last_check_time = db.Column(db.DateTime)
    check_count = db.Column(db.Integer)

    def __init__(self, isbn):
        self.isbn = isbn
        self.last_check_time = datetime.now()
        self.check_count = 1

    def toJSON(self):
        return {
            'isbn': self.isbn,
            'last_check_time': self.last_check_time.strftime(DATETIME_FORMAT),
            'check_count': self.check_count,
        }

    def __repr__(self):
        return '<CheckRecord %r, last_check_time: %d>' % self.isbn, self.last_check_time
