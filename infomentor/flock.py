import os

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

