import os
import re
import time
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime as dt
from typing import List


_MIDNIGHT = 24 * 60 * 60  # number of seconds in a day


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Custom wrapper for TRFH where I can have a bit more control over
    log file names"""
    def __init__(self, filename: str, when: str = 'd', interval: int = 1, backup_cnt: int = 0,
                 encoding: str = None, delay: bool = False, utc: bool = False, postfix: str = '.log',
                 at_time: dt = dt.now().replace(hour=0, minute=0, second=0)):

        self.baseFilename = None
        self.mode = 'a'
        self.stream = None
        self.origFileName = filename
        self.when = when.upper()
        self.interval = interval
        self.backupCount = backup_cnt
        self.utc = utc
        self.postfix = postfix
        self.atTime = at_time

        if self.when == 'S':
            self.interval = 1  # one second
            self.suffix = "%Y-%m-%d_%H-%M-%S"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        elif self.when == 'M':
            self.interval = 60  # one minute
            self.suffix = "%Y-%m-%d_%H-%M"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$"
        elif self.when == 'H':
            self.interval = 60 * 60  # one hour
            self.suffix = "%Y-%m-%d_%H"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}$"
        elif self.when == 'D' or self.when == 'MIDNIGHT':
            self.interval = 60 * 60 * 24  # one day
            self.suffix = "%Y-%m-%d"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}$"
        elif self.when.startswith('W'):
            self.interval = 60 * 60 * 24 * 7  # one week
            if len(self.when) != 2:
                raise ValueError(
                    "You must specify a day for weekly rollover from 0 to 6 (0 is Monday): %s" % self.when)
            if self.when[1] < '0' or self.when[1] > '6':
                raise ValueError("Invalid day specified for weekly rollover: %s" % self.when)
            self.dayOfWeek = int(self.when[1])
            self.suffix = "%Y-%m-%d"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}$"
        else:
            raise ValueError("Invalid rollover interval specified: %s" % self.when)

        current_time = int(time.time())
        super().__init__(filename=self.calculate_filename(current_time), when=when, interval=interval,
                         backupCount=backup_cnt, encoding=encoding, delay=delay, utc=utc)

        self.extMatch = re.compile(self.extMatch)
        self.interval = self.interval * interval  # multiply by units requested

        self.rolloverAt = self.compute_rollover(current_time)

    def compute_rollover(self, current_time: int) -> int:
        """
        Work out the rollover time based on the specified time.
        """
        result = current_time + self.interval
        # If we are rolling over at midnight or weekly, then the interval is already known.
        # What we need to figure out is WHEN the next interval is.  In other words,
        # if you are rolling over at midnight, then your base interval is 1 day,
        # but you want to start that one day clock at midnight, not now.  So, we
        # have to fudge the rolloverAt value in order to trigger the first rollover
        # at the right time.  After that, the regular interval will take care of
        # the rest.  Note that this code doesn't care about leap seconds. :)
        if self.when == 'MIDNIGHT' or self.when.startswith('W'):
            # This could be done with less code, but I wanted it to be clear
            if self.utc:
                t = time.gmtime(current_time)
            else:
                t = time.localtime(current_time)
            cur_hour = t[3]
            cur_min = t[4]
            cur_sec = t[5]
            cur_day = t[6]
            # r is the number of seconds left between now and the next rotation
            if self.atTime is None:
                rotate_ts = _MIDNIGHT
            else:
                rotate_ts = ((self.atTime.hour * 60 + self.atTime.minute) * 60 +
                             self.atTime.second)

            r = rotate_ts - ((cur_hour * 60 + cur_min) * 60 +
                             cur_sec)
            if r < 0:
                # Rotate time is before the current time (for example when
                # self.rotateAt is 13:45 and it now 14:15), rotation is
                # tomorrow.
                r += _MIDNIGHT
                cur_day = (cur_day + 1) % 7
            result = current_time + r
            # If we are rolling over on a certain day, add in the number of days until
            # the next rollover, but offset by 1 since we just calculated the time
            # until the next day starts.  There are three cases:
            # Case 1) The day to rollover is today; in this case, do nothing
            # Case 2) The day to rollover is further in the interval (i.e., today is
            #         day 2 (Wednesday) and rollover is on day 6 (Sunday).  Days to
            #         next rollover is simply 6 - 2 - 1, or 3.
            # Case 3) The day to rollover is behind us in the interval (i.e., today
            #         is day 5 (Saturday) and rollover is on day 3 (Thursday).
            #         Days to rollover is 6 - 5 + 3, or 4.  In this case, it's the
            #         number of days left in the current week (1) plus the number
            #         of days in the next week until the rollover day (3).
            # The calculations described in 2) and 3) above need to have a day added.
            # This is because the above time calculation takes us to midnight on this
            # day, i.e. the start of the next day.
            if self.when.startswith('W'):
                day = cur_day  # 0 is Monday
                if day != self.dayOfWeek:
                    if day < self.dayOfWeek:
                        days_to_wait = self.dayOfWeek - day
                    else:
                        days_to_wait = 6 - day + self.dayOfWeek + 1
                    new_rollover_at = result + (days_to_wait * (60 * 60 * 24))
                    if not self.utc:
                        dst_now = t[-1]
                        dst_at_rollover = time.localtime(new_rollover_at)[-1]
                        if dst_now != dst_at_rollover:
                            if not dst_now:
                                # DST kicks in before next rollover, so we need to deduct an hour
                                addend = -3600
                            else:
                                # DST bows out before next rollover, so we need to add an hour
                                addend = 3600
                            new_rollover_at += addend
                    result = new_rollover_at
        return result

    def calculate_filename(self, current_time: int) -> str:
        if self.utc:
            time_tuple = time.gmtime(current_time)
        else:
            time_tuple = time.localtime(current_time)

        return f'{self.origFileName}.{time.strftime(self.suffix, time_tuple)}{self.postfix}'

    def get_files_to_delete(self, new_filename: str) -> List[str]:
        dir_name, filename = os.path.split(self.origFileName)
        d_name, new_filename = os.path.split(new_filename)

        filenames = os.listdir(dir_name)
        result = []
        prefix = f'{filename}.'
        postfix = self.postfix
        prelen = len(prefix)
        postlen = len(postfix)
        for fname in filenames:
            if fname[:prelen] == prefix and fname[-postlen:] == postfix and len(
                    fname) - postlen > prelen and fname != new_filename:
                suffix = fname[prelen:len(fname) - postlen]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dir_name, fname))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]
        return result

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        cur_time = self.rolloverAt
        new_filename = self.calculate_filename(cur_time)
        new_base_filename = os.path.abspath(new_filename)
        self.baseFilename = new_base_filename
        self.mode = 'a'
        self.stream = self._open()

        if self.backupCount > 0:
            for s in self.get_files_to_delete(new_filename):
                try:
                    os.remove(s)
                except:
                    pass

        new_rollover_at = self.compute_rollover(cur_time)
        while new_rollover_at <= cur_time:
            new_rollover_at = new_rollover_at + self.interval

        # If DST changes and midnight or weekly rollover, adjust for this.
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dst_now = time.localtime(cur_time)[-1]
            dst_at_rollover = time.localtime(new_rollover_at)[-1]
            if dst_now != dst_at_rollover:
                if not dst_now:  # DST kicks in before next rollover, so we need to deduct an hour
                    new_rollover_at = new_rollover_at - 3600
                else:  # DST bows out before next rollover, so we need to add an hour
                    new_rollover_at = new_rollover_at + 3600
        self.rolloverAt = new_rollover_at
