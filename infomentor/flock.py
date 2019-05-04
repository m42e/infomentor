import os

class flock(object):
    '''A simple filelocking mechanism to prevent execution at the same time'''
    filename = '.im.lock'

    def __init__(self):
        '''Creates an object with the current pid'''
        self.pid = os.getpid()

    def aquire(self):
        '''Try to get the lock, if it fails it returns False'''
        if self.is_locked():
            return False
        with open(self.filename, 'w+') as f:
            f.write('{}'.format(self.pid))
        return True

    def release(self):
        '''Release the lock'''
        if self.own_lock():
            os.unlink(self.filename)

    def __del__(self):
        '''Release on delete'''
        self.release()

    def own_lock(self):
        '''Check if the lock is assigned to the current pid'''
        lockinfo = self._get_lockinfo()
        return lockinfo == self.pid

    def is_locked(self):
        '''Check if it is currently locked'''
        lockinfo = self._get_lockinfo()
        if not lockinfo:
            return False
        return self._is_process_active(lockinfo)

    def _is_process_active(self, pid):
        '''Check if the processed having the lock is still running'''
        try:
            os.kill(pid, 0)
            return pid != self.pid
        except Exception as e:
            return False

    def _get_lockinfo(self):
        '''Retrieve the information about the lock'''
        try:
            lock = {}
            with open(self.filename, 'r') as f:
                pid = int(f.read().strip())
            return pid
        except Exception as e:
            return False

