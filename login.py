import requests
import re
import dataset
import pushover
import http.cookiejar
import time
import math
import dateparser
import logging


db = dataset.connect('sqlite:///infomentor.db')
pushover.init('***REMOVED***')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Infomentor(object):

    BASE_IM1 = 'https://im1.infomentor.de/Germany/Germany/Production'
    BASE_MIM = 'https://mein.infomentor.de'

    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger

        self.session = requests.Session()
        self.session.cookies = http.cookiejar.MozillaCookieJar(filename='im.cookies')
        self.session.cookies.load(ignore_discard=True, ignore_expires=True)
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self._last_result = None

    def login(self, user, password):
        if not self.logged_in():
            self._do_login(user, password)

    def logged_in(self):
        ts = math.floor(time.time())
        url = self._mim_url('authentication/authentication/isauthenticated/?_={}000'.format(ts))
        r = self._do_post(url)
        self.logger.info('loggedin: %s', r.text)
        return r.text == 'true'

    def _get_auth_token(self):
        rem = re.findall(r'name="oauth_token" value="([^"]*)"',
                         self._last_result.text)
        if len(rem) != 1:
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
                raise Exception('Invalid Count of fieldnames')
            values = re.findall('value="([^"]*)"', f)
            if len(values) != 1:
                raise Exception('Invalid Count of values')
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
        url = self._mim_url('News/NewsImage/GetImage?id={}'.format(id))
        r = self._do_get(url)
        if r.status_code != 200:
            return False
        with open('{}.image'.format(id), 'wb+') as f:
            f.write(r.content)
        return True


    def get_calendar(self):
        data = {
            'UTCOffset': '-120',
            'start': '2018-09-01',
            'end': '2019-09-01'
        }
        self.logger.info('fetching calendar')
        r = self._do_post(self._mim_url('Calendar/Calendar/getEntries'), data=data)
        return r.json()

def send_notification(text, title, attachment=None, timestamp=True):
    logger.info('sending notification: %s', title)
    text = text.replace('<br>', '\n')
    pushover.Client('u5w9h8gc7hpzvr5a2kh2xh4m9zpidq').send_message(text, title=title, attachment=attachment, html=True, timestamp=timestamp)



def main():
    im = Infomentor(logger=logger)
    im.login('mbilger', 'jpEWG9hK8vXA8NaJFuKf')
    im_news = im.get_news()
    db_news = db.create_table('news', primary_id='id', primary_type=db.types.integer)
    for news_item in im_news['items']:
        if db_news.find_one(id=news_item['id']) is None:
            newsdata = im.get_article(news_item['id'])
            storenewsdata = {
                'id': newsdata['id'],
                'title': newsdata['title'],
                'content': newsdata['content'],
                'date': newsdata['date'],
            }
            db_news.insert(storenewsdata)
            image = None
            if im.get_newsimage(news_item['id']):
                image = open('{}.image'.format(news_item['id']), 'rb')

            timestamp = math.floor(dateparser.parse(newsdata['date']).timestamp())

            send_notification(newsdata['content'], newsdata['title'], attachment=image, timestamp=timestamp)
            if image is not None:
                image.close()

# init("<token>")
# Client("<user-key>").send_message("Hello!", title="Hello")

if __name__ == "__main__":
    main()
