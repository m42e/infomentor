import requests
import re
import json
import os
import http.cookiejar
import time
import math
import datetime
import contextlib
import logging
import urllib.parse
import uuid
from infomentor import model

class InfomentorFile(object):
    def __init__(self, directory, filename):
        if directory is None:
            raise Exception('directory is required')
        self.filename = filename
        self.randomid = str(uuid.uuid4())
        self.directory = directory

    @property
    def targetfile(self):
        return os.path.join(self.directory, self.fullfilename)

    @property
    def targetdir(self):
        return os.path.join(self.directory, self.randomid)

    @property
    def fullfilename(self):
        if self.filename is None:
            raise Exception('no filename set')
        return os.path.join(self.randomid, self.filename)

    def save_file(self, content):
        os.makedirs(self.targetdir, exist_ok=True)
        with open(self.targetfile, 'wb+') as f:
            f.write(content)


class Infomentor(object):
    '''Basic object for handling infomentor site login and fetching of data'''

    BASE_IM1 = 'https://im1.infomentor.de/Germany/Germany/Production'
    BASE_MIM = 'https://mein.infomentor.de'

    def __init__(self, user, logger=None):
        '''Create informentor object for username'''
        self.logger = logger or logging.getLogger(__name__)
        self._last_result = None
        self.user = user
        self._create_session()

    def _create_session(self):
        '''Create the session for handling all further requests'''
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self._load_cookies()

    def _load_cookies(self):
        '''Setup the cookie requests'''
        os.makedirs('cookiejars', exist_ok=True)
        self.session.cookies = http.cookiejar.MozillaCookieJar(
            filename='cookiejars/{}.cookies'.format(self.user)
        )
        with contextlib.suppress(FileNotFoundError):
            self.session.cookies.load(ignore_discard=True, ignore_expires=True)

    def login(self, password):
        '''Login using the given password'''
        if self.logged_in(self.user):
            return True
        self._do_login(self.user, password)
        return self.logged_in(self.user)

    def logged_in(self, username):
        '''Check if user is logged in (with cookies)'''
        ts = math.floor(time.time())
        auth_check_url = 'authentication/authentication/' + \
            'isauthenticated/?_={}000'.format(ts)
        url = self._mim_url(auth_check_url)
        r = self._do_post(url)
        self.logger.info('%s loggedin: %s', username, r.text)
        return r.text.lower() == 'true'

    def _do_login(self, user, password):
        self._do_request_initial_token()
        self._perform_login(password)
        self._finalize_login()

    def _do_request_initial_token(self):
        '''Request initial oauth_token'''
        # Get the initial oauth token
        self._do_get(self._mim_url())
        self._oauth_token = self._get_auth_token()
        # This request is performed by the browser, the reason is unclear
        login_url = self._mim_url(
            'Authentication/Authentication/Login?ReturnUrl=%2F')
        self._do_get(login_url)

    def _get_auth_token(self):
        '''Reading oauth_token from response text'''
        token_re = r'name="oauth_token" value="([^"]*)"'
        tokens = re.findall(token_re, self._last_result.text)
        if len(tokens) != 1:
            self.logger.error('OAUTH_TOKEN not found')
            raise Exception('Invalid Count of tokens')
        return tokens[0]

    def _perform_login(self, password):
        self._do_post(
            self._im1_url('mentor/'),
            data={'oauth_token': self._oauth_token}
        )
        # Extract the hidden fields content
        payload = self._get_hidden_fields()
        # update with the missing and the login parameters
        payload.update({
            'login_ascx$txtNotandanafn': self.user,
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

    def _extract_hidden_fields(self):
        hidden_re = '<input type="hidden"(.*?) />'
        hiddenfields = re.findall(hidden_re, self._last_result.text)
        return hiddenfields

    def _finalize_login(self):
        # Read the oauth token which is the final token for the login
        oauth_token = self._get_auth_token()
        # authenticate
        self._do_post(
            self._im1_url('mentor/'),
            data={'oauth_token': oauth_token}
        )
        self._do_get(self._mim_url())

    def _do_post(self, url, **kwargs):
        '''Post request for session'''
        self.logger.info('post to: %s', url)
        if 'data' in kwargs:
            self.logger.info('data: %s', json.dumps(kwargs['data']))
        self._last_result = self.session.post(url, **kwargs)
        self.logger.info('result: %d', self._last_result.status_code)
        self._save_cookies()
        return self._last_result

    def _do_get(self, url, **kwargs):
        '''get request for session'''
        self.logger.info('get: %s', url)
        self._last_result = self.session.get(url, **kwargs)
        self.logger.info('result: %d', self._last_result.status_code)
        self._save_cookies()
        if self._last_result.status_code != 200:
            raise Exception('Got response with code {}'.format(
                self._last_result.status_code
            ))
        return self._last_result

    def _save_cookies(self):
        '''Save cookies'''
        self.session.cookies.save(ignore_discard=True, ignore_expires=True)

    def download_file(self, url, filename=None, directory=None):
        '''download a file with given name or provided filename'''
        self.logger.info('fetching download: %s', url)
        if filename is not None or directory is not None:
            return self._download_file(url, directory, filename)
        else:
            self.logger.error('fetching download requires filename or folder')
            raise Exception('Download Failed')

    def _get_filename_from_cd(self):
        '''determine filename from headers or random uuid'''
        cd = self._last_result.headers.get('content-disposition')
        if cd:
            filename_re = r'''
                .* # Anything
                (?:
                    filename=(?P<native>.+) # normal filename
                    |
                    filename\*=(?P<extended>.+) # extended filename
                ) # The filename
                (?:$|;.*) # End or more
            '''
            fname = re.match(filename_re, cd, flags=re.VERBOSE)
            filename = fname.group('native')
            if filename is not None and len(filename) != 0:
                return filename
            filename = fname.group('extended')
            if filename is not None and len(filename) != 0:
                encoding, string = filename.split("''")
                return urllib.parse.unquote(string, encoding)
        filename = str(uuid.uuid4())
        self.logger.warning(
            'no filename detected in %s: using random filename %s',
            cd, filename)
        return filename

    def _download_file(self, url, directory, filename=None):
        '''download a file with  provided filename'''
        file = InfomentorFile(directory, filename)
        self.logger.info('to (randomized) directory %s', file.targetdir)
        url = self._mim_url(url)
        self._do_get(url)
        if filename is None:
            self.logger.info('determine filename from headers')
            filename = self._get_filename_from_cd()
            self.logger.info('determined filename: %s', filename)
        file.filename = filename
        self.logger.info('full filename: %s', file.fullfilename)
        file.save_file(self._last_result.content)
        return file.fullfilename

    def _build_url(self, path='', base=BASE_IM1):
        return '{}/{}'.format(base, path)

    def _mim_url(self, path=''):
        return self._build_url(path, base=self.BASE_MIM)

    def _im1_url(self, path=''):
        return self._build_url(path, base=self.BASE_IM1)

    def get_news_list(self):
        self.logger.info('fetching news')
        self._do_post(self._mim_url('News/news/GetArticleList'))
        news_json = self.get_json_return()
        return [str(i['id']) for i in news_json['items']]

    def parse_news(self, news_json):
        idlist = [str(i['id']) for i in im_news['items']]
        self.logger.info('Parsing %d news (%s)', im_news['totalItems'], ', '.join(idlist))
        for news_item in reversed(im_news['items']):
                newsdata = self.im.get_article(news_item['id'])

    def get_news_article(self, id):
        article_json = self.get_article(id)
        storenewsdata = {
            k: article_json[k] for k in ('title', 'content', 'date')
        }
        storenewsdata['news_id'] = article_json['id']
        storenewsdata['raw'] = json.dumps(article_json)
        storenewsdata['attachments'] = []
        for attachment in article_json['attachments']:
            self.logger.info('found attachment %s', attachment['title'])
            att_id = re.findall('Download/([0-9]+)?', attachment['url'])[0]
            f = self.download_file(attachment['url'], directory='files')
            try:
                storenewsdata['attachments'].append(model.Attachment(attachment_id=att_id, url=attachment['url'], localpath=f, title=attachment['title']))
            except Exception as e:
                self.logger.exception('failed to store attachment')
        news = model.News(**storenewsdata)
        with contextlib.suppress(Exception):
            news.imagefile = self.get_newsimage(id)
        return news

    def get_article(self, id):
        self.logger.info('fetching article: %s', id)
        self._do_post(
            self._mim_url('News/news/GetArticle'),
            data={'id': id}
        )
        return self.get_json_return()

    def get_newsimage(self, id):
        self.logger.info('fetching article image: %s', id)
        filename = '{}.image'.format(id)
        url = self._mim_url('News/NewsImage/GetImage?id={}'.format(id))
        return self.download_file(url, directory='images', filename=filename)

    def get_calendar(self, offset=0, weeks=1):
        self.logger.info('fetching calendar')
        data = self._get_week_dates(offset=offset, weeks=weeks)
        self._do_post(
            self._mim_url('Calendar/Calendar/getEntries'),
            data=data
        )
        return self.get_json_return()

    def get_homework(self, offset=0):
        self.logger.info('fetching homework')
        startofweek = self._get_start_of_week(offset)
        timestamp = startofweek.strftime('%Y-%m-%dT00:00:00.000Z')
        data = {
            'date': timestamp,
            'isWeek': True,
        }
        self._do_post(
            self._mim_url('Homework/homework/GetHomework'),
            data=data
        )
        return self.get_json_return()

    def get_homework_list(self):
        self._homework = {}
        homeworklist = []
        homework = []
        homework.extend(self.get_homework())
        homework.extend(self.get_homework(1))
        for dategroup in homework:
            for hw in dategroup['items']:
                if hw['id'] == 0:
                    continue
                else:
                    self._homework[hw['id']] = hw
                    homeworklist.append(hw['id'])
        return homeworklist

    def get_homework_info(self, id):
        hw = self._homework[id]
        storehw = {
            k: hw[k] for k in ('subject', 'courseElement')
        }
        storehw['homework_id'] = hw['id']
        storehw['text'] = hw['homeworkText']
        storehw['attachments'] = []
        for attachment in hw['attachments']:
            self.logger.info('found attachment %s', attachment['title'])
            att_id = re.findall('Download/([0-9]+)?', attachment['url'])[0]
            f = self.download_file(attachment['url'], directory='files')
            try:
                storehw['attachments'].append(model.Attachment(attachment_id=att_id, url=attachment['url'], localpath=f, title=attachment['title']))
            except Exception as e:
                self.logger.exception('failed to store attachment')
        hw = model.Homework(**storehw)
        return hw

    def get_timetable(self, offset=0):
        self.logger.info('fetching timetable')
        data = self._get_week_dates(offset)
        self._do_post(
            self._mim_url('timetable/timetable/gettimetablelist'),
            data=data
        )
        return self.get_json_return()

    def get_json_return(self):
        try:
            return self._last_result.json()
        except json.JSONDecodeError as jse:
            self.logger.exception('JSON coudl not be decoded')
            self.logger.info('status code: %d', self._last_result.status_code)
            self.logger.info('response was: %s', self._last_result.text)
            raise

    def _get_week_dates(self, offset=0, weeks=1):
        weekoffset = datetime.timedelta(days=7*offset)

        startofweek = self._get_start_of_weekdays()
        endofweek = startofweek + datetime.timedelta(days=5+7*(weeks-1))

        startofweek += weekoffset
        endofweek += weekoffset

        now = datetime.datetime.now()
        utctime = datetime.datetime.utcnow()
        utcoffset = (now.tm_hour - utctime.tm_hour)*60

        data = {
            'UTCOffset': utcoffset,
            'start': startofweek.strftime('%Y-%m-%d'),
            'end': endofweek.strftime('%Y-%m-%d'),
        }
        return data

    def _get_start_of_week(self, offset=0):
        now = datetime.datetime.now()
        dayofweek = now.weekday()
        startofweek = now - datetime.timedelta(days=dayofweek)
        startofweek -= datetime.timedelta(days=offset*7)
        return startofweek

