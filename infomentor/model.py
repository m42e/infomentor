from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Boolean
from sqlalchemy.orm import relationship
from Crypto.Cipher import AES
import base64
import enum
import hashlib

ModelBase = declarative_base()

_PASSWORD_SECRET_KEY = '***REMOVED***'
BS = 16
def pad(s):
    diff = BS - len(s) % BS
    return (s + (diff) * chr(diff)).encode('utf8')
def unpad(s):
    return s[0:-s[-1]].decode('utf8')

class User(ModelBase):
    '''The infomentor user.'''
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    enc_password = Column(String)
    notification = relationship("Notification", back_populates="user", uselist=False)
    apistatus = relationship("ApiStatus", back_populates="user", uselist=False)
    wantstatus = Column(Boolean)
    homeworks = relationship("Homework",  back_populates="user")
    news = relationship("News",back_populates="user")

    def __init__(self, *args, **kwargs):
        self._setup_cipher()
        super().__init__(*args, **kwargs)

    def _setup_cipher(self):
        if not hasattr(self, 'cipher'):
            aeskey = hashlib.sha256(_PASSWORD_SECRET_KEY.encode()).digest()
            self.cipher = AES.new(aeskey,AES.MODE_ECB)

    @property
    def password(self):
        self._setup_cipher()
        decoded = self.cipher.decrypt(base64.b64decode(self.enc_password))
        return unpad(decoded)

    @password.setter
    def password(self, value):
        self._setup_cipher()
        encoded = base64.b64encode(self.cipher.encrypt(pad(value)))
        self.enc_password = encoded

    def __repr__(self):
        return "<User(name='%s', password='%s')>" % (
            self.name, '*' * len(self.password))


class Notification(ModelBase):
    '''This contains the information about the type of notification and additional the key to reach out to the user'''
    __tablename__ = 'notifications'

    class Types(enum.Enum):
        '''Supported notification types'''
        PUSHOVER = 1
        EMAIL = 2

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    ntype = Column(Enum(Types))
    info = Column(String)
    user = relationship("User", back_populates="notification")

    def __repr__(self):
        return "<Notification(type='{}', info='{}')>".format(
            self.ntype, self.info)


class Attachment(ModelBase):
    '''General attachment type for homework and news'''
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True)
    attachment_id = Column(Integer)
    filetype = Column(String)
    url = Column(String)
    title = Column(String)
    localpath = Column(String)
    news_id = Column(Integer, ForeignKey('news.id'))
    homework_id = Column(Integer, ForeignKey('homework.id'))

    news = relationship("News", back_populates="attachments")
    homework = relationship("Homework", back_populates="attachments")


class News(ModelBase):
    '''A News entry'''
    __tablename__ = 'news'

    id = Column(Integer, primary_key=True)
    news_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String)
    content = Column(String)
    category = Column(String)
    date = Column(String)
    imageUrl = Column(String)
    imagefile = Column(String)
    notified = Column(Boolean, default=False)
    raw = Column(String)
    attachments = relationship("Attachment", order_by=Attachment.id, back_populates="news", uselist=True)
    user = relationship("User", back_populates="news")

    def __repr__(self):
        return "<News(id='%d', title='%s')>" % (
            self.id, self.title)

class Homework(ModelBase):
    '''A homework entry'''
    __tablename__ = 'homework'

    id = Column(Integer, primary_key=True)
    homework_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    subject = Column(String)
    courseElement = Column(String)
    text = Column(String)
    date = Column(String)
    imageUrl = Column(String)
    attachments = relationship("Attachment", order_by=Attachment.id, back_populates="homework")
    user = relationship("User", back_populates="homeworks")

class ApiStatus(ModelBase):
    '''Representing the result of the last trys to access the api, represented as one status'''
    __tablename__ = 'api_status'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    degraded_count  = Column(Integer)
    datetime  = Column(DateTime)
    info = Column(String)
    ok = Column(Boolean)
    user = relationship("User", back_populates="apistatus", uselist=False)

    def updateobj(self, data):
        for key, value in data.items():
            setattr(self, key, value)

    def __repr__(self):
        return "<ApiStatus(ok='%s', NOKs='%d', info='%s')>" % (
            self.ok, self.degraded_count, self.info)

