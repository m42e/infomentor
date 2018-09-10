import requests
import re
import os
import copy
import dataset
import pushover
import http.cookiejar
import time
import math
import dateparser
import datetime
import contextlib
import logging
import hashlib
import urllib.parse


db = dataset.connect('sqlite:///infomentor.db')
pushover.init('***REMOVED***')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)8s - %(message)s',
    filename='log.txt',
    filemode='a+'
)
logger = logging.getLogger('Infomentor Notifier')


class NewsInformer(object):
    def __init__(self, username, password, pushover, logger=None):
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger
        self.username = username
        self.password = password
        self.pushover = pushover
        self._setup_db()
        self.im = Infomentor(logger=logger)
        res = self.im.login(self.username, self.password)
        if not res:
            self.logger.error('Login not successfull')
            raise Exception('Login failed')

    def _setup_db(self):
        self.db_news = db.create_table(
            'news',
            primary_id='id',
            primary_type=db.types.integer
        )
        self.db_notification = db.create_table(
            'news_notification',
            primary_id=False,
        )
        self.db_news_attachments = db.create_table(
            'news_attachments',
            primary_id=False,
        )
        self.db_attachments = db.create_table(
            'attachments',
            primary_id='id',
            primary_type=db.types.integer
        )
        self.db_timetable = db.create_table(
            'timetable',
            primary_id='id',
            primary_type=db.types.string
        )
        self.db_ttnotification = db.create_table(
            'timetable_notification',
            primary_id=False,
        )
        self.db_news = db.create_table(
            'access_status',
            primary_id='id',
            primary_type=db.types.integer
        )

    def send_notification(
            self, news_id, text, title, attachment=None, timestamp=True):
        self.logger.info('sending notification: %s', title)
        text = text.replace('<br>', '\n')
        try:
            pushover.Client(self.pushover).send_message(
                text,
                title=title,
                attachment=attachment,
                html=True,
                timestamp=timestamp
            )
            self.db_notification.insert(
                {'id': news_id, 'username': self.username}
            )
        except pushover.RequestError as e:
            self.logger.error('Sending notification failed', exc_info=e)

    def _notification_sent(self, news_id):
        entry = self.db_notification.find_one(
            id=news_id, username=self.username)
        return entry is not None

    def notify_timetable(self):
        tt = self.im.get_timetable()
        changed = []
        for item in tt:
            parsed_item = copy.deepcopy(item)
            start = datetime.datetime.strptime(parsed_item['start'], '%Y-%m-%dT%H:%M:%S')
            parsed_item['wday'] = start.weekday()
            key = '{wday}-{startTime}/{endTime}-{title}-{notes[roomInfo]}'.format(**parsed_item)
            parsed_item['id'] = key
            entry = self.db_timetable.find_one(id=key)
            if entry is None:
                changed.append(parsed_item)

    def appSetup(self):
        print(self.im.appsetup())


    def notify_news(self):
        im_news = self.im.get_news()
        self.logger.info('Parsing %d news', im_news['totalItems'])
        for news_item in im_news['items']:
            self.db_news.delete(id=14370)
            storenewsdata = self.db_news.find_one(id=news_item['id'])
            if storenewsdata is None:
                self.logger.info('NEW article found %s', news_item['title'])
                newsdata = self.im.get_article(news_item['id'])
                storenewsdata = {
                    k: newsdata[k] for k in ('id', 'title', 'content', 'date')
                }
                for attachment in newsdata['attachments']:
                    att_id = re.findall('Download/([0-9]+)?', attachment['url'])[0]
                    f = self.im.download(attachment['url'], directory='files')
                    self.db_attachments.insert(
                        {'id': att_id, 'filename':f}
                    );
                    self.db_news_attachments.insert({'att_id': att_id, 'news_id':newsdata['id']})
                self.db_news.insert(storenewsdata)
            if not self._notification_sent(news_item['id']):
                self.logger.info('Notify %s about %s',
                            self.username, news_item['title'])
                image = None
                image_filename = self.im.get_newsimage(news_item['id'])
                if image_filename:
                    image = open(image_filename, 'rb')

                parsed_date = dateparser.parse(storenewsdata['date'])
                timestamp = math.floor(parsed_date.timestamp())
                self.send_notification(
                    news_item['id'],
                    storenewsdata['content'],
                    storenewsdata['title'],
                    attachment=image,
                    timestamp=timestamp
                )
                if image is not None:
                    image.close()


def get_filename_from_cd(cd):
    if not cd:
        return None
    fname = re.match('.*(?:filename=(?P<native>.+)|filename\*=(?P<extended>.+))(?:$|;.*)', cd)
    filename = fname.group('native')
    if filename is not None and len(filename) != 0:
        return filename
    filename = fname.group('extended')
    if filename is not None and len(filename) != 0:
        encoding, string = filename.split("''")
        return urllib.parse.unquote(string, encoding)
    import uuid
    filename = str(uuid.uuid4())
    logger.warning('no filename detected in %s: using random filename %s', cd, filename)
    return filename


class Infomentor(object):

    BASE_IM1 = 'https://im1.infomentor.de/Germany/Germany/Production'
    BASE_MIM = 'https://mein.infomentor.de'

    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger

        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self._last_result = None

    def login(self, user, password):
        os.makedirs('cookiejars', exist_ok=True)
        self.session.cookies = http.cookiejar.MozillaCookieJar(
            filename='cookiejars/{}.cookies'.format(user)
        )
        with contextlib.suppress(FileNotFoundError):
            self.session.cookies.load(ignore_discard=True, ignore_expires=True)
        if self.logged_in(user):
            return True
        self._do_login(user, password)
        self._do_get(self._mim_url())
        return self.logged_in(user)

    def logged_in(self, username):
        ts = math.floor(time.time())
        url = self._mim_url(
            'authentication/authentication/isauthenticated/?_={}000'.format(ts)
        )
        r = self._do_post(url)
        self.logger.info('%s loggedin: %s', username, r.text)
        return r.text == 'true'

    def _get_auth_token(self):
        rem = re.findall(r'name="oauth_token" value="([^"]*)"',
                         self._last_result.text)
        if len(rem) != 1:
            self.logger.error('OAUTH_TOKEN not found')
            raise Exception('Invalid Count of tokens')
        oauth_token = rem[0]
        return oauth_token

    def _do_post(self, url, **kwargs):
        self.logger.info('post to: %s', url)
        self._last_result = self.session.post(url, **kwargs)
        self.logger.info('result: %d', self._last_result.status_code)
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return self._last_result

    def _do_get(self, url, **kwargs):
        self.logger.info('get: %s', url)
        self._last_result = self.session.get(url, **kwargs)
        self.logger.info('result: %d', self._last_result.status_code)
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return self._last_result

    def download(self, url, filename=None, directory=None, overwrite=False):
        self.logger.info('fetching download: %s', url)
        if filename is not None:
            self.logger.info('using given filename %s', filename)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            if os.path.isfile(filename) and not overwrite:
                self.logger.info('file %s already downloaded', filename)
                return filename
        elif directory is not None:
            self.logger.info('to directory %s', directory)
            os.makedirs(directory, exist_ok=True)
        else:
            self.logger.error('fetching download requires filename or folder')
            return False

        url = self._mim_url(url)
        r = self._do_get(url)
        if r.status_code != 200:
            return False
        if filename is None:
            self.logger.info('determine filename from headers')
            print(r.headers)
            filename = get_filename_from_cd(r.headers.get('content-disposition'))
            filename = os.path.join(directory, filename)
            self.logger.info('determined filename: %s', filename)
            if os.path.isfile(filename) and not overwrite:
                self.logger.info('file %s already downloaded', filename)
                filename, extension = os.path.splitext(filename)
                now = datetime.datetime.now()
                timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
                filename = '{}_{}{}'.format(filename, timestamp, extension)
                self.logger.info('using %s as filename', filename)

        with open(filename, 'wb+') as f:
            f.write(r.content)
        return filename

    def _extract_hidden_fields(self):
        hiddenfields = re.findall('<input type="hidden"(.*?) />',
                                  self._last_result.text)
        return hiddenfields

    def _build_url(self, path='', base=None):
        if base is None:
            base = self.BASE_IM1
        return '{}/{}'.format(base, path)

    def _mim_url(self, path=''):
        return self._build_url(path, base=self.BASE_MIM)

    def _im1_url(self, path=''):
        return self._build_url(path, base=self.BASE_IM1)

    def _get_hidden_fields(self):
        hiddenfields = self._extract_hidden_fields()
        field_values = {}
        for f in hiddenfields:
            names = re.findall('name="([^"]*)"', f)
            if len(names) != 1:
                self.logger.error('Could not parse hidden field (fieldname)')
                continue
            values = re.findall('value="([^"]*)"', f)
            if len(values) != 1:
                self.logger.error('Could not parse hidden field (value)')
                continue
            field_values[names[0]] = values[0]
        return field_values

    def _do_request_initial_token(self):
        # Get the initial oauth token
        self._do_get(self._mim_url())
        self._oauth_token = self._get_auth_token()
        # This request is performed by the browser, the reason is unclear
        login_url = self._mim_url(
            'Authentication/Authentication/Login?ReturnUrl=%2F')
        self._do_get(login_url)

    def _perform_login(self, user, password):
        self._do_post(
            self._im1_url('mentor/'),
            data={'oauth_token': self._oauth_token}
        )
        # Extract the hidden fields content
        payload = self._get_hidden_fields()
        # update with the missing and the login parameters
        payload.update({
            'login_ascx$txtNotandanafn': user,
            'login_ascx$txtLykilord': password,
            '__EVENTTARGET': 'login_ascx$btnLogin',
            '__EVENTARGUMENT': ''
        })

        # perform the login
        self._do_post(
            self._im1_url('mentor/'),
            data=payload,
            headers={
                'Referer': self._im1_url('mentor/'),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )

    def _finalize_login(self):
        # Read the oauth token which is the final token for the login
        oauth_token = self._get_auth_token()
        # autenticate
        self._do_post(
            self._im1_url('mentor/'),
            data={'oauth_token': oauth_token}
        )

    def _do_login(self, user, password):
        self._do_request_initial_token()
        self._perform_login(user, password)
        self._finalize_login()

    def get_news(self):
        self.logger.info('fetching news')
        r = self._do_post(self._mim_url('News/news/GetArticleList'))
        return r.json()

    def get_article(self, id):
        self.logger.info('fetching article: %s', id)
        r = self._do_post(self._mim_url('News/news/GetArticle'),
                          data={'id': id})
        return r.json()


    def appsetup(self):
        self.logger.info('appsetup')
        r = self._do_get(self._mim_url('account/PairedDevices/PairedDevices'))
        print(r.content)
        return r.json()

    def get_newsimage(self, id):
        self.logger.info('fetching article image: %s', id)
        os.makedirs('images', exist_ok=True)
        filename = 'images/{}.image'.format(id)
        if os.path.isfile(filename):
            self.logger.info('image %s already downloaded', filename)
            return filename
        url = self._mim_url('News/NewsImage/GetImage?id={}'.format(id))
        r = self._do_get(url)
        if r.status_code != 200:
            return False
        with open(filename, 'wb+') as f:
            f.write(r.content)
        return filename

    def get_calendar(self):
        data = {
            'UTCOffset': '-120',
            'start': '2018-09-01',
            'end': '2019-09-01'
        }
        self.logger.info('fetching calendar')
        r = self._do_post(
            self._mim_url('Calendar/Calendar/getEntries'),
            data=data
        )
        return r.json()

    def get_homework(self):
        now = datetime.datetime.now()
        dayofweek = now.weekday()
        startofweek = now - datetime.timedelta(days=dayofweek)
        timestamp = startofweek.strftime('%Y-%m-%dT00:00:00.000Z')
        data = {
            'date': timestamp,
            'isWeek': True,
        }
        r = self._do_post(
            self._mim_url('Homework/homework/GetHomework'),
            data=data
        )
        return r.json()

    def get_timetable(self):
        now = datetime.datetime.now()
        dayofweek = now.weekday()
        startofweek = now - datetime.timedelta(days=dayofweek)
        endofweek = now + datetime.timedelta(days=(5-dayofweek)+7)
        start = startofweek.strftime('%Y-%m-%d')
        end = endofweek.strftime('%Y-%m-%d')
        data = {
            'UTCOffset': '-120',
            'start': start,
            'end': end
        }
        self.logger.info('fetching timetable')
        r = self._do_post(
            self._mim_url('timetable/timetable/gettimetablelist'),
            data=data
        )
        return r.json()


def send_status_update(client, info):
    pushover.Client(client).send_message(
        info,
        title='Statusinfo',
        html=False,
        timestamp=True
    )


class flock(object):
    filename = '.im.lock'

    def __init__(self):
        self.pid = os.getpid()

    def aquire(self):
        if self.is_locked():
            return False
        with open(self.filename, 'w+') as f:
            f.write('{}'.format(self.pid))
        return True

    def release(self):
        if self.own_lock():
            os.unlink(self.filename)

    def __del__(self):
        self.release()

    def own_lock(self):
        lockinfo = self._get_lockinfo()
        return lockinfo == self.pid

    def is_locked(self):
        lockinfo = self._get_lockinfo()
        if not lockinfo:
            return False
        return self._is_process_active(lockinfo)

    def _is_process_active(self, pid):
        try:
            os.kill(pid, 0)
            return pid != self.pid
        except Exception as e:
            return False

    def _get_lockinfo(self):
        try:
            lock = {}
            with open(self.filename, 'r') as f:
                pid = int(f.read().strip())
            return pid
        except Exception as e:
            return False




def main():
    logger.info('STARTING-------------------- {}'.format(os.getpid()))
    lock = flock()
    if not lock.aquire():
        logger.info('EXITING - PREVIOUS IS RUNNING')
        logger.info('ENDING--------------------- {}'.format(os.getpid()))
        return

    db_users = db.create_table(
        'user',
        primary_id='username',
        primary_type=db.types.string
    )
    db_api_status = db.create_table(
        'api_status',
        primary_id='username',
        primary_type=db.types.string
    )
    users = [ u['username'] for u in db_users ]
    for user in users:
        user = db_users.find_one(username=user)
        logger.info('==== USER: {} ====='.format(user['username']))
        if user['password'] == '':
            logger.warning('User %s not enabled', user['username'])
            continue
        now = datetime.datetime.now()
        ni = NewsInformer(**user, logger=logger)
        statusinfo = {'username': user['username'],
                      'date': now, 'ok': False, 'info': ''}
        try:
            ni.notify_news()
            statusinfo['ok'] = True
            statusinfo['degraded'] = False
            statusinfo['info'] = 'Works as expected'
        except Exception as e:
            inforstr = 'Exception occured:\n{}:{}\n'.format(type(e).__name__, e)
            statusinfo['ok'] = False
            statusinfo['info'] = inforstr
        finally:
            previous_status = db_api_status.find_one(username=user['username'])
            if previous_status is not None:
                if previous_status['ok'] != statusinfo['ok']:
                    if previous_status['degraded'] == True:
                        send_status_update(user['pushover'], statusinfo['info'])
                    else:
                        logger.error('Switching to degraded state %s', user['username'])
                        statusinfo['degraded'] = True

            db_api_status.upsert(statusinfo, ['username'])
    logger.info('ENDING--------------------- {}'.format(os.getpid()))

def test():
    logger.info('STARTING-------------------- {}'.format(os.getpid()))
    lock = flock()
    if not lock.aquire():
        logger.info('EXITING - PREVIOUS IS RUNNING')
        logger.info('ENDING--------------------- {}'.format(os.getpid()))
        return

    db_users = db.create_table(
        'user',
        primary_id='username',
        primary_type=db.types.string
    )
    db_api_status = db.create_table(
        'api_status',
        primary_id='username',
        primary_type=db.types.string
    )
    for user in db_users:
        logger.info('==== USER: {} ====='.format(user['username']))
        if user['password'] == '':
            logger.warning('User %s not enabled', user['username'])
            continue
        now = datetime.datetime.now()
        ni = NewsInformer(**user, logger=logger)
        #ni.notify_timetable()
        #ni.notify_news()
        ni.appSetup()

if __name__ == "__main__":
    main()

