import infomentor.flock as flock
import logging
import argparse
import datetime
import sys
import os
import requests
from infomentor import db, model, connector, informer, config


logformat = "{asctime} - {name:25s}[{filename:20s}:{lineno:3d}] - {levelname:8s} - {message}"


def logtofile():
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler("log.txt", maxBytes=1024*1024, backupCount=10)
    logging.basicConfig(
        level=logging.INFO, format=logformat, handlers=[handler], style="{"
    )


def logtoconsole():
    logging.basicConfig(level=logging.DEBUG, format=logformat, style="{")


def parse_args(arglist):
    parser = argparse.ArgumentParser(description="Infomentor Grabber and Notifier")
    parser.add_argument(
        "--nolog", action="store_true", help="print log instead of logging to file"
    )
    parser.add_argument("--adduser", action='store_true', help="add user")
    parser.add_argument("--addfake", action='store_true', help="add fake")
    parser.add_argument("--addpushover", action='store_true', help="add pushover")
    parser.add_argument("--addmail", action='store_true', help="add mail")
    parser.add_argument("--addcalendar", action='store_true', help="add icloud calendar")
    parser.add_argument("--addinvitation", action='store_true', help="add calendar invitation")
    parser.add_argument("--test", action="store_true", help="test")
    parser.add_argument("--username", type=str, nargs='?', help="username")
    args = parser.parse_args(arglist)
    return args


def add_user(username):
    session = db.get_db()
    existing_user = (
        session.query(model.User).filter(model.User.name == username).one_or_none()
    )
    if existing_user is not None:
        print("user exists, change pw")
    else:
        print(f"Adding user: {username}")

    import getpass

    password = getpass.getpass(prompt="Password: ")
    if existing_user is not None:
        existing_user.password = password
    else:
        user = model.User(name=username, password=password)
        session.add(user)
    session.commit()


def add_pushover(username):
    session = db.get_db()
    user = session.query(model.User).filter(model.User.name == username).one_or_none()
    if user is None:
        print("user does not exist")
        return
    else:
        print(f"Adding PUSHOVER for user: {username}")
    id = input("PUSHOVER ID: ")
    user.notification = model.Notification(
        ntype=model.Notification.Types.PUSHOVER, info=id
    )
    session.commit()


def add_fake(username):
    session = db.get_db()
    user = session.query(model.User).filter(model.User.name == username).one_or_none()
    if user is None:
        print("user does not exist")
        return
    else:
        print(f"Adding FAKE for user: {username}")
    user.notification = model.Notification(ntype=model.Notification.Types.FAKE, info="")
    session.commit()


def add_calendar(username):
    session = db.get_db()
    user = session.query(model.User).filter(model.User.name == username).one_or_none()
    if user is None:
        print("user does not exist")
        return
    else:
        print(f"Adding icloud calendar for user: {username}")
    id = input("Apple ID: ")
    import getpass

    password = getpass.getpass(prompt="iCloud Password: ")
    calendar = input("Calendar: ")
    user.icalendar = model.ICloudCalendar(
        icloud_user=id, password=password, calendarname=calendar
    )
    session.commit()

def add_invitation(username):
    session = db.get_db()
    user = session.query(model.User).filter(model.User.name == username).one_or_none()
    if user is None:
        print("user does not exist")
        return
    else:
        print(f"Adding Mail for calendar invitation for user: {username}")
    mail = input("Mail: ")
    user.invitation = model.Invitation(email=mail)
    session.commit()


def add_mail(username):
    session = db.get_db()
    user = session.query(model.User).filter(model.User.name == username).one_or_none()
    if user is None:
        print("user does not exist")
        return
    else:
        print(f"Adding MAIL for user: {username}")
    address = input("MAIL ADDRESS: ")
    user.notification = model.Notification(
        ntype=model.Notification.Types.EMAIL, info=address
    )
    session.commit()


def notify_users():
    logger = logging.getLogger(__name__)
    session = db.get_db()
    cfg = config.load()
    if cfg["healthchecks"]["url"] != "":
        requests.get(cfg["healthchecks"]["url"] + '/start')

    for user in session.query(model.User):
        logger.info("==== USER: %s =====", user.name)
        if user.password == "":
            logger.warning("User %s not enabled", user.name)
            continue
        now = datetime.datetime.now()
        im = connector.Infomentor(user.name)
        im.login(user.password)
        logger.info("User loggedin")
        statusinfo = {"datetime": now, "ok": False, "info": "", "degraded_count": 0}
        if user.apistatus is None:
            user.apistatus = model.ApiStatus(**statusinfo)
        logger.info("Former API status: %s", user.apistatus)
        try:
            i = informer.Informer(user, im, logger=logger)
            i.update_news()
            i.update_homework()
            i.update_calendar()
            statusinfo["ok"] = True
            statusinfo["degraded"] = False
        except Exception as e:
            inforstr = "Exception occured:\n{}:{}\n".format(type(e).__name__, e)
            statusinfo["ok"] = False
            statusinfo["info"] = inforstr
            logger.exception("Something went wrong")
        finally:
            if user.apistatus.ok == True and statusinfo["ok"] == False:
                logger.error("Switching to degraded state %s", user.name)
                statusinfo["degraded_count"] = 1
            if user.apistatus.ok == False and statusinfo["ok"] == False:
                if user.apistatus.degraded_count == 1 and user.wantstatus:
                    im.send_status_update(statusinfo["info"])
                try:
                    statusinfo["degraded_count"] = user.apistatus["degraded_count"] + 1
                except Exception as e:
                    statusinfo["degraded_count"] = 1
            if user.apistatus.ok == False and statusinfo["ok"] == True:
                statusinfo["info"] = "Works as expected, failed {} times".format(
                    user.apistatus.degraded_count
                )
                statusinfo["degraded_count"] = 0
                if user.wantstatus:
                    im.send_status_update(statusinfo["info"])
            user.apistatus.updateobj(statusinfo)
        logger.info("New API status: %s", user.apistatus)
        session.commit()

    if cfg["healthchecks"]["url"] != "":
        requests.get(cfg["healthchecks"]["url"])


def main():
    args = parse_args(sys.argv[1:])
    if args.test:
        return
    if args.nolog:
        logtoconsole()
    else:
        logtofile()
    logger = logging.getLogger("Infomentor Notifier")
    logger.info("STARTING-------------------- %s", os.getpid())
    try:
        lock = flock.flock()
        if not lock.aquire():
            logger.info("EXITING - PREVIOUS IS RUNNING")
            raise Exception()
        if args.addfake:
            add_fake(args.username)
        elif args.adduser:
            add_user(args.username)
        elif args.addpushover:
            add_pushover(args.username)
        elif args.addmail:
            add_mail(args.username)
        elif args.addcalendar:
            add_calendar(args.username)
        elif args.addinvitation:
            add_invitation(args.username)
        else:
            notify_users()
    except Exception as e:
        logger.info("Exceptional exit")
        logger.exception("Info")
    finally:
        logger.info("EXITING--------------------- %s", os.getpid())

def run_notify():
    run_without_args(notify_users)

def run_adduser():
    run_with_args(add_user)

def run_addfake():
    run_with_args(add_fake)

def run_addpushover():
    run_with_args(add_pushover)

def run_addmail():
    run_with_args(add_mail)

def run_addcalendar():
    run_with_args(add_calendar)

def run_addinvitation():
    run_with_args(add_invitation)


def run_with_args(fct):
    args = parse_args(sys.argv[1:])
    logtofile()
    logger = logging.getLogger("Infomentor Notifier")
    logger.info("STARTING-------------------- %s", os.getpid())
    lock = flock.flock()
    try:
        if not lock.aquire():
            logger.info("EXITING - PREVIOUS IS RUNNING")
            raise Exception()
        if args.username is None:
            print('Provide Username using --username')
            raise Exception('No username provided')
        fct(args.username)
    except Exception as e:
        logger.info("Exceptional exit")
        logger.exception("Info")
    finally:
        logger.info("EXITING--------------------- %s", os.getpid())

def run_without_args(fct):
    args = parse_args(sys.argv[1:])
    logtofile()
    logger = logging.getLogger("Infomentor Notifier")
    logger.info("STARTING-------------------- %s", os.getpid())
    try:
        lock = flock.flock()
        if not lock.aquire():
            logger.info("EXITING - PREVIOUS IS RUNNING")
            raise Exception()
        fct()
    except Exception as e:
        logger.info("Exceptional exit")
        logger.exception("Info")
    finally:
        logger.info("EXITING--------------------- %s", os.getpid())

if __name__ == "__main__":
    main()
