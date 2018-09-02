import requests
import re
import os
import dataset
import pushover
import http.cookiejar
import time
import math
import dateparser
import contextlib
import logging


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
            logger = logging.getLogger(__name__)
        self.username = username
        self.password = password
        self.pushover = pushover
        self._setup_db()
        self.im = Infomentor(logger=logger)

    def _setup_db(self):
        self.db_news = db.create_table(
            'news',
            primary_id='id',
            primary_type=db.types.integer
        )
        self.db_notification = db.create_table(
            'news_notification',
            primary_id='id',
            primary_type=db.types.integer
        )

    def send_notification(self, news_id, text, title, attachment=None, timestamp=True):
        logger.info('sending notification: %s', title)
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
        entry = self.db_notification.find_one(id=news_id, username=self.username)
        return entry is not None

    def notify_news(self):
        im = Infomentor(logger=logger)
        im.login(self.username, self.password)
        im_news = im.get_news()
        logger.info('Parsing %d news', im_news['totalItems'])
        for news_item in im_news['items']:
            storenewsdata = self.db_news.find_one(id=news_item['id'])
            if storenewsdata is None:
                logger.info('NEW article found %s', news_item['title'])
                newsdata = im.get_article(news_item['id'])
                storenewsdata = {
                    k: newsdata[k] for k in ('id', 'title', 'content', 'date')
                }
                self.db_news.insert(storenewsdata)
            if not self._notification_sent(news_item['id']):
                logger.info('Notify %s about %s', self.username, news_item['title'])
                image = None
                image_filename = im.get_newsimage(news_item['id'])
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
        if not self.logged_in():
            self._do_login(user, password)

    def logged_in(self):
        ts = math.floor(time.time())
        url = self._mim_url(
            'authentication/authentication/isauthenticated/?_={}000'.format(ts)
        )
        r = self._do_post(url)
        self.logger.info('loggedin: %s', r.text)
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
        self.logger.debug('post to: %s', url)
        self._last_result = self.session.post(url, **kwargs)
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return self._last_result

    def _do_get(self, url, **kwargs):
        self.logger.debug('get: %s', url)
        self._last_result = self.session.get(url, **kwargs)
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        return self._last_result

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

    def get_newsimage(self, id):
        self.logger.info('fetching article image: %s', id)
        os.makedirs('images', exist_ok=True)
        filename = 'images/{}.image'.format(id)
        if os.path.isfile(filename):
            return True
        url = self._mim_url('News/NewsImage/GetImage?id={}'.format(id))
        r = self._do_get(url)
        if r.status_code != 200:
            return False
        with open(filename, 'wb+') as f:
            f.write(r.content)
        return True

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


def main():
    db_users = db.create_table(
        'user',
        primary_id='username',
        primary_type=db.types.string
    )
    for user in db_users:
        if user['password'] == '':
            logger.warning('User %s not enabled', user['username'])
            continue;
        ni = NewsInformer(**user)
        ni.notify_news()


if __name__ == "__main__":
    main()

