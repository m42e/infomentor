from infomentor import model, db, icloudcalendar, config, icalendar_addons
import logging
import uuid
import os
import re
import dateparser
import hashlib
import datetime
import math
import pushover
import urllib.parse
from icalendar import Event, vDate, Calendar, vCalAddress, vText, vBoolean, Timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import smtplib


cfg = config.load()
pushover.init(cfg["pushover"]["apikey"])


class Informer(object):
    """The Logic part of the infomentor notifier.

    This class offers the methods required to notify a user of new News and Homework items posted on infomentor."""

    def __init__(self, user, im, logger):
        self.logger = logger or logging.getLogger(__name__)
        self.user = user
        self.im = im
        self.cal = None

    def send_status_update(self, text):
        """In case something unexpected happends and the user has activated the feature to get notified about it, this will send out the information"""
        try:
            if self.user.notification.ntype == model.Notification.Types.PUSHOVER:
                pushover.Client(self.user.notification.info).send_message(
                    text, title="Status Infomentor", html=False
                )
            elif self.user.notification.ntype == model.Notification.Types.EMAIL:
                self._send_text_mail(
                    self.user.notification.info, "Status Infomentor", text
                )
        except:
            self._send_text_mail(
                cfg["general"]["adminmail"],
                "Fehler bei infomentor",
                "Fehler bei Infomentor",
            )

    def update_news(self):
        session = db.get_db()
        newslist = self.im.get_news_list()
        for news_entry in newslist:
            self.logger.debug("parsing %s", news_entry["id"])
            news = (
                session.query(model.News)
                .filter(model.News.news_id == news_entry["id"])
                .filter(model.News.date == news_entry["publishedDate"])
                .with_parent(self.user, "news")
                .one_or_none()
            )
            if news is not None:
                self.logger.debug("Skipping news %s", news_entry["id"])
                continue
            news = self.im.get_news_article(news_entry)
            self._notify_news(news)
            self.user.news.append(news)
            session.commit()

    def _notify_news(self, news):
        if self.user.notification is None:
            self.logger.debug("Warn: no notification for user")
            return
        if self.user.notification.ntype == model.Notification.Types.PUSHOVER:
            self._notify_news_pushover(news)
        elif self.user.notification.ntype == model.Notification.Types.EMAIL:
            self._notify_news_mail(news)
        elif self.user.notification.ntype == model.Notification.Types.FAKE:
            with open("{}.txt".format(self.user.name), "a+") as f:
                f.write(
                    "Notification:\n---------8<-------\n{}\n---------8<-------\n\n".format(
                        news.content
                    )
                )
        else:
            raise Exception("invalid notification")
        pass

    def _notify_news_pushover(self, news):
        text = news.content
        for attachment in news.attachments:
            fid, fname = attachment.localpath.split("/")
            text += """<br>Attachment {0}: {2}/{1} <br>""".format(
                fname,
                urllib.parse.quote(attachment.localpath),
                cfg["general"]["baseurl"],
            )
        parsed_date = dateparser.parse(news.date)
        now = datetime.datetime.now()
        parsed_date += datetime.timedelta(hours=now.hour, minutes=now.minute)
        timestamp = math.floor(parsed_date.timestamp())
        if len(text) > 900:
            url = self._make_site(text)
            shorttext = text[:900]
            text = "{}...\n\nfulltext saved at: {}".format(shorttext, url)
        text = text.replace("<br>", "\n")
        try:
            self.logger.info(text)
            self.logger.info(news.title)
            if news.imagefile is not None:
                image = open(os.path.join("images", news.imagefile), "rb")
            else:
                image = None
            pushover.Client(self.user.notification.info).send_message(
                text, title=news.title, attachment=image, html=True, timestamp=timestamp
            )
        except pushover.RequestError as e:
            self.logger.error("Sending notification failed", exc_info=e)
        finally:
            if image is not None:
                image.close()

    def _make_site(self, text):
        filename = str(uuid.uuid4())
        fpath = os.path.join("files", filename + ".html")
        urlfinder = re.compile("(https?://[^ \n\t]*)")
        text = urlfinder.sub(r'<a href="\1">\1</a>', text)
        text = '<html> <head> <meta charset="utf-8" /> </head> <body>{}</body></html>'.format(
            text
        )
        with open(fpath, "w+") as f:
            f.write(text)
        return "{}/{}.html".format(cfg["general"]["baseurl"], filename)

    def _notify_news_mail(self, news):
        self._send_attachment_mail(
            news.content,
            f"INFOMENTOR Homework: {news.title}",
            news.attachments,
            self.user.notification.info,
        )

    def update_homework(self):
        session = db.get_db()
        homeworklist = self.im.get_homework_list()
        for homeworkid in homeworklist:
            homework = (
                session.query(model.Homework)
                .filter(model.Homework.homework_id == homeworkid)
                .with_parent(self.user, "homeworks")
                .one_or_none()
            )
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
            with open("{}.txt".format(self.user.name), "a+") as f:
                f.write(
                    "Notification:\n---------8<-------\n{}\n---------8<-------\n\n".format(
                        hw.text
                    )
                )
        else:
            raise Exception("invalid notification")
        pass

    def _notify_hw_pushover(self, hw):
        text = hw.text
        for attachment in hw.attachments:
            fid, fname = attachment.localpath.split("/")
            text += """<br>Attachment {0}: {2}/{1}<br>""".format(
                fname,
                urllib.parse.quote(attachment.localpath),
                cfg["general"]["baseurl"],
            )
        if len(text) > 900:
            url = self._make_site(text)
            shorttext = text[:900]
            text = "{}...\n\nfulltext saved at: {}".format(shorttext, url)
        text = text.replace("<br>", "\n")
        try:
            self.logger.info(text)
            self.logger.info(hw.subject)
            pushover.Client(self.user.notification.info).send_message(
                text, title=f"Homework: {hw.subject}", html=True
            )
        except pushover.RequestError as e:
            self.logger.error("Sending notification failed", exc_info=e)

    def _notify_hw_mail(self, hw):
        self._send_attachment_mail(
            hw.text,
            f"INFOMENTOR Homework: {hw.subject}",
            hw.attachments,
            self.user.notification.info,
        )

    def _send_attachment_mail(
        self, text, subject, attachments, to, fr="infomentor@09a.de"
    ):
        outer = MIMEMultipart()
        text = text.replace("<br>", "\n")
        outer.attach(MIMEText(text + "\n\n"))
        outer["Subject"] = subject
        outer["From"] = fr
        outer["To"] = to
        for attachment in attachments:
            fid, fname = attachment.localpath.split("/")
            filename = os.path.join("files", attachment.localpath)
            ctype, encoding = mimetypes.guess_type(filename)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            with open(filename, "rb") as fp:
                msg = MIMEBase(maintype, subtype)
                msg.set_payload(fp.read())
                encoders.encode_base64(msg)
            msg.add_header("Content-Disposition", "attachment", filename=fname)
            outer.attach(msg)
        self._send_mail(outer)

    def _send_text_mail(self, to, subject, text, fr="infomentor@09a.de"):
        mail = MIMEText(text)
        mail["Subject"] = subject
        mail["From"] = fr
        mail["To"] = to
        self._send_mail(mail)

    def _send_mail(self, mail):
        s = smtplib.SMTP_SSL(cfg["smtp"]["server"])
        s.login(cfg["smtp"]["username"], cfg["smtp"]["password"])
        s.send_message(mail)
        s.quit()

    def _send_invitation(self, calobj, to, fr="infomentor@09a.de"):
        event = calobj.subcomponents[0]
        eml_body = event["description"]
        eml_body_bin = event["description"]
        msg = MIMEMultipart("mixed")
        msg["Reply-To"] = fr
        msg["Subject"] = event["summary"]
        msg["From"] = fr
        msg["To"] = to

        calobj.add("PRODID", "infomentor_py")
        calobj.add("METHOD", "REQUEST")
        calobj.add("calscale", "GREGORIAN")
        calobj.add("version", "2.0")
        calobj.add_component(icalendar_addons.generate_vtimezone('Europe/Berlin'))
        attendee = vCalAddress(f'MAILTO:{to}')
        attendee.params['cn'] = vText(to)
        attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
        attendee.params['CUTYPE'] = vText('REQ-INDIVIDUAL')
        attendee.params['PARTSTAT'] = vText('ACCEPTED')
        attendee.params['RSVP'] = 'FALSE'
        event.add('attendee', attendee, encode=0)
        event.add("organizer", 'MAILTO:infomentor@09a.de')

        part_email = MIMEText(eml_body, "html")
        part_email_text = MIMEText(eml_body, "plain")
        part_cal = MIMEText(calobj.to_ical().decode("utf-8"), "calendar;method=REQUEST")

        msgAlternative = MIMEMultipart("alternative")
        msg.attach(msgAlternative)

        ical_atch = MIMEBase("application/ics", ' ;name="%s"' % ("invite.ics"))
        ical_atch.set_payload(calobj.to_ical().decode("utf-8"))
        encoders.encode_base64(ical_atch)
        ical_atch.add_header(
            "Content-Disposition", 'attachment; filename="%s"' % ("invite.ics")
        )

        eml_atch = MIMEBase("text/plain", "")
        eml_atch.set_payload("")
        encoders.encode_base64(eml_atch)
        eml_atch.add_header("Content-Transfer-Encoding", "")

        msg.attach(part_email)
        msg.attach(part_email_text)
        msg.attach(part_cal)
        self._send_mail(msg)

    def _setup_icloudconnector(self):
        if self.cal is None:
            try:
                icx = icloudcalendar.iCloudConnector(
                    self.user.icalendar.icloud_user, self.user.icalendar.password
                )
                cname = self.user.icalendar.calendarname
                self.cal = icx.get_named_calendar(cname)
                if not self.cal:
                    self.cal = icx.create_calendar(cname)
                self.logger.warn("using icloud")
            except Exception as e:
                self.logger.exception("using icloud dummy connector")

                class Dummy(object):
                    def add_event(self, *args, **kwargs):
                        pass

                self.cal = Dummy()

    def _write_icalendar(self, calend):
        try:
            self._setup_icloudconnector()
            self.cal.add_event(calend.to_ical())
        except Exception as e:
            self.logger.exception("Calendar failed")

    def update_calendar(self):
        session = db.get_db()
        if self.user.icalendar is None and self.user.invitation is None:
            return
        try:
            calentries = self.im.get_calendar()
            for entry in calentries:
                self.logger.debug(entry)
                uid = str(
                    uuid.uuid5(uuid.NAMESPACE_URL, "infomentor_{}".format(entry["id"]))
                )
                event_details = self.im.get_event(entry["id"])
                calend = Calendar()
                event = Event()
                event.add("uid", uid)
                event.add("summary", entry["title"])
                event.add("dtstamp", datetime.datetime.now())
                if not event_details["allDayEvent"]:
                    event.add("dtstart", dateparser.parse(entry["start"]))
                    event.add("dtend", dateparser.parse(entry["end"]))
                else:
                    event.add("dtstart", dateparser.parse(entry["start"]).date())
                    event.add("dtend", dateparser.parse(entry["end"]).date())

                description = event_details["notes"]
                eventinfo = event_details["info"]
                new_cal_entry = calend.to_ical().replace(b"\r", b"")
                new_cal_hash = hashlib.sha1(new_cal_entry).hexdigest()
                for res in eventinfo["resources"]:
                    f = self.im.download_file(res["url"], directory="files")
                    description += """\nAttachment {0}: {2}/{1}""".format(
                        res["title"], urllib.parse.quote(f), cfg["general"]["baseurl"]
                    )
                event.add("description", description)

                calend.add_component(event)
                new_cal_entry = calend.to_ical().replace(b"\r", b"")
                session = db.get_db()
                storedata = {
                    "calendar_id": uid,
                    "ical": new_cal_entry,
                    "hash": new_cal_hash,
                }
                calendarentry = (
                    session.query(model.CalendarEntry)
                    .filter(model.CalendarEntry.calendar_id == uid)
                    .with_parent(self.user, "calendarentries")
                    .one_or_none()
                )
                if calendarentry is not None:
                    if calendarentry.hash == new_cal_hash:
                        self.logger.info("calendar entry UNCHANGED {}".format(uid))
                        continue
                    else:
                        self.logger.info("calendar entry UPDATED {}".format(uid))
                        for key, value in storedata.items():
                            setattr(calendarentry, key, value)

                else:
                    self.logger.info("calendar entry NEW {}".format(uid))
                    calendarentry = model.CalendarEntry(**storedata)

                self.logger.debug(new_cal_entry.decode("utf-8"))
                if self.user.icalendar is not None:
                    self._write_icalendar(calend)
                if self.user.invitation is not None:
                    self._send_invitation(calend, self.user.invitation.email)
                self.user.calendarentries.append(calendarentry)
                session.commit()
        except Exception as e:
            self.logger.exception("Calendar failed")
