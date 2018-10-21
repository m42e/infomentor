import infomentor.flock as flock
import logging
import argparse
import datetime
import sys
import os
from infomentor import db, model, connector, informer


logformat='{asctime} - {name:25s} - {levelname:8s} - {message}'
def logtofile():
    logging.basicConfig(
        level=logging.INFO,
        format=logformat,
        filename='log.txt',
        filemode='a+',
        style='{'
    )
def logtoconsole():
    logging.basicConfig(
        level=logging.DEBUG,
        format=logformat,
        style='{'
    )

def parse_args(arglist):
    parser = argparse.ArgumentParser(description='Infomentor Grabber and Notifier')
    parser.add_argument('--nolog', action='store_true', help='print log instead of logging to file')
    parser.add_argument('--adduser', type=str, help='add user')
    parser.add_argument('--addpushover', type=str, help='add pushover')
    parser.add_argument('--addmail', type=str, help='add mail')
    args = parser.parse_args(arglist)
    return args

def add_user(username):
    session = db.get_db()
    existing_user = session.query(model.User.name == username).one_or_none()
    if existing_user is not None:
        print('user exists, change pw')
    else:
        print(f'Adding user: {username}')

    import getpass
    password = getpass.getpass(prompt='Password: ')
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
        print('user does not exist')
        return
    else:
        print(f'Adding PUSHOVER for user: {username}')
    id = input('PUSHOVER ID: ')
    user.notification = model.Notification(ntype=model.Notification.Types.PUSHOVER, info=id)
    session.commit()

def add_mail(username):
    session = db.get_db()
    user = session.query(model.User).filter(model.User.name == username).one_or_none()
    if user is None:
        print('user does not exist')
        return
    else:
        print(f'Adding MAIL for user: {username}')
    address = input('MAIL ADDRESS: ')
    user.notification = model.Notification(ntype=model.Notification.Types.EMAIL, info=address)
    session.commit()

def notify_users():
    logger = logging.getLogger(__name__)
    session = db.get_db()
    for user in session.query(model.User):
        logger.info('==== USER: %s =====', user.name)
        if user.password == '':
            logger.warning('User %s not enabled', user.name)
            continue
        now = datetime.datetime.now()
        im = connector.Infomentor(user.name)
        im.login(user.password)
        logger.info('User loggedin')
        statusinfo = {'datetime': now, 'ok': False, 'info': '', 'degraded_count':0}
        if user.apistatus is None:
            user.apistatus = model.ApiStatus(**statusinfo)
        logger.info('Former API status: %s', user.apistatus)
        try:
            i = informer.Informer(user, im, logger=logger)
            i.update_news()
            i.update_homework()
            statusinfo['ok'] = True
            statusinfo['degraded'] = False
        except Exception as e:
            inforstr = 'Exception occured:\n{}:{}\n'.format(type(e).__name__, e)
            statusinfo['ok'] = False
            statusinfo['info'] = inforstr
            logger.exception("Something went wrong")
        finally:
            if user.apistatus.ok == True and statusinfo['ok'] == False:
                logger.error('Switching to degraded state %s', user.name)
                statusinfo['degraded_count'] = 1
            if user.apistatus.ok == False and statusinfo['ok'] == False:
                if user.apistatus.degraded_count == 1 and user.wantstatus:
                    send_status_update(user, statusinfo['info'])
                try:
                    statusinfo['degraded_count'] = user.apistatus['degraded_count'] + 1
                except Exception as e:
                    statusinfo['degraded_count'] = 1
            if user.apistatus.ok == False and statusinfo['ok'] == True:
                statusinfo['info'] = 'Works as expected, failed {} times'.format(user.apistatus.degraded_count)
                statusinfo['degraded_count'] = 0
                if user.wantstatus:
                    send_status_update(user, statusinfo['info'])
            user.apistatus.updateobj(statusinfo)
        logger.info('New API status: %s', user.apistatus)
        session.commit()

def send_status_update(user, text):
    pass

def main():
    args = parse_args(sys.argv[1:])
    if args.nolog:
        logtoconsole()
    else:
        logtofile()
    logger = logging.getLogger('Infomentor Notifier')
    logger.info('STARTING-------------------- %s', os.getpid())
    try:
        lock = flock.flock()
        if not lock.aquire():
            logger.info('EXITING - PREVIOUS IS RUNNING')
            raise Exception()
        if args.adduser:
            add_user(args.adduser)
        elif args.addpushover:
            add_pushover(args.addpushover)
        else:
            notify_users()
    except Exception as e:
            logger.info('Exceptional exit')
            logger.exception('Info')
    finally:
        logger.info('EXITING--------------------- %s', os.getpid())

if __name__ == "__main__":
    main()