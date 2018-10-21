from infomentor import model, db
import logging
import uuid
import os
import re
import dateparser
import datetime
import math
import pushover
pushover.init('***REMOVED***')

class Informer(object):
    def __init__(self, user, im, logger):
        self.logger = logger or logging.getLogger(__name__)
        self.user = user
        self.im = im

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
        else:
            raise Exception('invalid notification')
        pass

    def _notify_news_pushover(self, news):
        text = news.content
        for attachment in news.attachments:
            fid, fname = attachment.localpath.split('/')
            text += '''<br>Attachment {0}: https://files.hyttioaoa.de/{1}<br>'''.format(fname, attachment.localpath)
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
        return 'https://files.hyttioaoa.de/{}.html'.format(filename)

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
        s = smtplib.SMTP_SSL('09a.de')
        s.login('infomentor@09a.de', '***REMOVED***')
        s.send_message(outer)
        s.quit()

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
        else:
            raise Exception('invalid notification')
        pass

    def _notify_hw_pushover(self, hw):
        text = hw.text
        for attachment in hw.attachments:
            fid, fname = attachment.localpath.split('/')
            text += '''<br>Attachment {0}: https://files.hyttioaoa.de/{1}<br>'''.format(fname, attachment.localpath)
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
                title=hw.title,
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
        s = smtplib.SMTP_SSL('09a.de')
        s.login('infomentor@09a.de', '***REMOVED***')
        s.send_message(outer)
        s.quit()
