from infomentor import model, db, icloudcalendar, config
import logging
import uuid
import os
import re
import dateparser
import datetime
import math
import pushover
from icalendar import Event, vDate, Calendar
cfg = config.load()
pushover.init(cfg['pushover']['apikey'] )

class Informer(object):
    '''The Logic part of the infomentor notifier.
    
    This class offers the methods required to notify a user of new News and Homework items posted on infomentor.'''
    def __init__(self, user, im, logger):
        self.logger = logger or logging.getLogger(__name__)
        self.user = user
        self.im = im

    def send_status_update(self, text):
        '''In case something unexpected happends and the user has activated the feature to get notified about it, this will send out the information'''
        try:
            if self.user.notification.ntype == model.Notification.Types.PUSHOVER:
                pushover.Client(self.user.notification.info).send_message(
                    text,
                    title='Status Infomentor',
                    html=False,
                )
            elif self.user.notification.ntype == model.Notification.Types.EMAIL:
                mail = MIMEText(text)
                mail['Subject'] = f'Status Infomentor'
                mail['From'] = 'infomentor@09a.de'
                mail['To'] = self.user.notification.info
                self._send_mail(mail)
        except:
            mail = MIMEText("Fehler bei Infomentor")
            mail['Subject'] = f'Fehler bei infomentor'
            mail['From'] = 'infomentor@09a.de'
            mail['To'] = 'matthias@bilger.info'
            self._send_mail(mail)

    def update_news(self):
        session = db.get_db()
        newslist = self.im.get_news_list()
        for newsid in newslist:
            news = session.query(model.News).filter(model.News.news_id == newsid).with_parent(self.user, 'news').one_or_none()
            if news is None:
                news = self.im.get_news_article(newsid)
                self._notify_news(news)
                self.user.news.append(news)
                session.commit()

    def _notify_news(self, news):
        if self.user.notification.ntype == model.Notification.Types.PUSHOVER:
            self._notify_news_pushover(news)
        elif self.user.notification.ntype == model.Notification.Types.EMAIL:
            self._notify_news_mail(news)
        elif self.user.notification.ntype == model.Notification.Types.FAKE:
            with open('{}.txt'.format(self.user.name), 'a+') as f:
                f.write('Notification:\n---------8<-------\n{}\n---------8<-------\n\n'.format(news.content))
        else:
            raise Exception('invalid notification')
        pass

    def _notify_news_pushover(self, news):
        text = news.content
        for attachment in news.attachments:
            fid, fname = attachment.localpath.split('/')
            text += '''<br>Attachment {0}: {2}/{1} <br>'''.format(fname, attachment.localpath, cfg['general']['baseurl'])
        parsed_date = dateparser.parse(news.date)
        now = datetime.datetime.now()
        parsed_date += datetime.timedelta(hours=now.hour, minutes=now.minute)
        timestamp = math.floor(parsed_date.timestamp())
        if len(text) > 900:
            url = self._make_site(text)
            shorttext = text[:900]
            text = '{}...\n\nfulltext saved at: {}'.format(shorttext, url)
        text = text.replace('<br>', '\n')
        try:
            self.logger.info(text)
            self.logger.info(news.title)
            if news.imagefile is not None:
                image = open(os.path.join('images', news.imagefile), 'rb')
            else:
                image = None
            pushover.Client(self.user.notification.info).send_message(
                text,
                title=news.title,
                attachment=image,
                html=True,
                timestamp=timestamp
            )
        except pushover.RequestError as e:
            self.logger.error('Sending notification failed', exc_info=e)
        finally:
            if image is not None:
                image.close()

    def _make_site(self, text):
        filename = str(uuid.uuid4())
        fpath = os.path.join('files', filename+'.html')
        urlfinder = re.compile("(https?://[^ \n\t]*)")
        text = urlfinder.sub(r'<a href="\1">\1</a>', text)
        text = '<html> <head> <meta charset="utf-8" /> </head> <body>{}</body></html>'.format(text)
        with open(fpath, 'w+') as f:
            f.write(text)
        return '{}/{}.html'.format(cfg['general']['baseurl'], filename)

    def _notify_news_mail(self, news):
        # Import the email modules we'll need
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        import mimetypes
        import smtplib

        outer = MIMEMultipart()
        text = news.content.replace('<br>', '\n')
        outer.attach(MIMEText(text + '\n\n'))
        outer['Subject'] = f'INFOMENTOR News: {news.title}'
        outer['From'] = 'infomentor@09a.de'
        outer['To'] = self.user.notification.info
        for attachment in news.attachments:
            fid, fname = attachment.localpath.split('/')
            filename = os.path.join('files', attachment.localpath)
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            with open(filename, 'rb') as fp:
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(fp.read())
                encoders.encode_base64(msg)
            msg.add_header('Content-Disposition', 'attachment', filename=fname)
            outer.attach(msg)
        self._send_mail(outer)

    def update_homework(self):
        session = db.get_db()
        homeworklist = self.im.get_homework_list()
        for homeworkid in homeworklist:
            homework = session.query(model.Homework).filter(model.Homework.homework_id == homeworkid).with_parent(self.user, 'homeworks').one_or_none()
            if homework is None:
                homework = self.im.get_homework_info(homeworkid)
                self._notify_hw(homework)
                self.user.homeworks.append(homework)
                session.commit()

    def _notify_hw(self, hw):
        if self.user.notification.ntype == model.Notification.Types.PUSHOVER:
            self._notify_hw_pushover(hw)
        elif self.user.notification.ntype == model.Notification.Types.EMAIL:
            self._notify_hw_mail(hw)
        elif self.user.notification.ntype == model.Notification.Types.FAKE:
            with open('{}.txt'.format(self.user.name), 'a+') as f:
                f.write('Notification:\n---------8<-------\n{}\n---------8<-------\n\n'.format(hw.text))
        else:
            raise Exception('invalid notification')
        pass

    def _notify_hw_pushover(self, hw):
        text = hw.text
        for attachment in hw.attachments:
            fid, fname = attachment.localpath.split('/')
            text += '''<br>Attachment {0}: {2}/{1}<br>'''.format(fname, attachment.localpath, cfg['general']['baseurl'])
        if len(text) > 900:
            url = self._make_site(text)
            shorttext = text[:900]
            text = '{}...\n\nfulltext saved at: {}'.format(shorttext, url)
        text = text.replace('<br>', '\n')
        try:
            self.logger.info(text)
            self.logger.info(hw.subject)
            pushover.Client(self.user.notification.info).send_message(
                text,
                title=f"Homework: {hw.subject}",
                html=True,
            )
        except pushover.RequestError as e:
            self.logger.error('Sending notification failed', exc_info=e)

    def _notify_hw_mail(self, hw):
        # Import the email modules we'll need
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        import mimetypes
        import smtplib

        outer = MIMEMultipart()
        text = hw.text.replace('<br>', '\n')
        outer.attach(MIMEText(text + '\n\n'))
        outer['Subject'] = f'INFOMENTOR Homework: {hw.subject}'
        outer['From'] = 'infomentor@09a.de'
        outer['To'] = self.user.notification.info
        for attachment in hw.attachments:
            fid, fname = attachment.localpath.split('/')
            filename = os.path.join('files', attachment.localpath)
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            with open(filename, 'rb') as fp:
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(fp.read())
                encoders.encode_base64(msg)
            msg.add_header('Content-Disposition', 'attachment', filename=fname)
            outer.attach(msg)
        self._send_mail(outer)

    def _send_mail(self, mail):
        s = smtplib.SMTP_SSL(cfg['smtp']['server'])
        s.login(cfg['smtp']['username'], cfg['smtp']['password'])
        s.send_message(mail)
        s.quit()

    def update_calendar(self):
        session = db.get_db()
        print(self.user.icalendar)
        if self.user.icalendar is None:
            return
        icx = icloudcalendar.iCloudConnector(self.user.icalendar.icloud_user, self.user.icalendar.password)
        cname = self.user.icalendar.calendarname
        cal = icx.get_named_calendar(cname)
        if not cal:
            cal = icx.create_calendar(cname)
        calentries = self.im.get_calendar()
        known_entries = {}
        for calevent in cal.events():
            if calevent.data is None:
                continue
            uid = re.findall('UID:(.*)', calevent.data)[0]
            known_entries[uid] = calevent

        for entry in calentries:
            self.logger.debug(entry)
            uid = 'infomentor_{}'.format(entry['id'])
            event_details = self.im.get_event(entry['id'])
            self.logger.debug(event_details)
            calend = Calendar()
            event = Event()
            event.add('uid', 'infomentor_{}'.format(entry['id']))
            event.add('summary', entry['title'])
            event.add('description', event_details['notes'])
            event.add('dtstart', dateparser.parse(entry['start']))
            event.add('dtend', dateparser.parse(entry['end']))
            calend.add_component(event)
            new_cal_entry = calend.to_ical().decode('utf-8').replace('\r','')
            if uid in known_entries:
                if known_entries[uid].data == new_cal_entry:
                    self.logger.info('no change for calendar entry {}'.format(uid))
                    continue
            self.logger.debug(calend.to_ical())
            cal.add_event(calend.to_ical())

