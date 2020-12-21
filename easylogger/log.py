#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General log setup file.
"""
import os
import re
import sys
import time
import logging
import argparse
import traceback
from logging import Logger
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime as dt
from types import TracebackType
from typing import List, Dict, Union, Tuple, Optional


class ArgParse(argparse.ArgumentParser):
    """Custom wrapper for argument parsing"""
    def __init__(self, arg_list: List[Dict[str, Union[dict, List[str]]]], parse_all: bool = True):
        """
        Args:
            arg_list: List of the flags for each argument
                typical setup:
                >>> arg = [
                >>>     {
                >>>         'names': ['-l', '--level'],
                >>>         'other': {  # These are just the additional params available for add_argument
                >>>             'action': 'store',
                >>>             'default': 'INFO'
                >>>         }
                >>>     }
                >>>]
            parse_all: if True, will call parse_args otherwise calls parse_known_args
        """
        super().__init__()
        for arg_n in arg_list:
            args = arg_n.get('names', [])
            other_items = arg_n.get('other', {})
            self.add_argument(*args, **other_items)
        self.args = None
        self.arg_dict = {}
        if parse_all:
            self.parse = self.parse_args
        else:
            self.parse = self.parse_known_args
        self._process_args()

    def _process_args(self):
        """Processes args when using parse_known_args"""
        self.args = self.parse()
        if isinstance(self.args, tuple):
            for arg in self.args:
                if isinstance(arg, argparse.Namespace):
                    # Parse into dict and update
                    self.arg_dict.update(vars(arg))
        else:
            # Hopefully is already Namespace
            self.arg_dict = vars(self.args)


class LogArgParser:
    """Simple class for carrying over standard argparse routines to set log level"""
    def __init__(self, is_debugging: bool = False):
        self.log_level_str = 'INFO'    # Default
        args = [
            {
                'names': ['-lvl', '--level'],
                'other': {
                    'action': 'store',
                    'default': self.log_level_str
                }
            }
        ]
        self.ap = ArgParse(args, parse_all=False)
        if is_debugging:
            print('Bypassing argument parser in test environment')
            self.log_level_str = 'DEBUG'
        else:
            # Not running tests in PyCharm, so take in args
            arg_dict = self.ap.arg_dict
            self.log_level_str = arg_dict.get('level', self.log_level_str)


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


class Log(Logger):
    """Initiates a logging object to record processes and errors"""
    DEFAULT_LOG_LEVEL = 'INFO'

    def __init__(self, log: Union[str, 'Log', Logger] = None, child_name: str = None,
                 log_level_str: str = None, log_to_file: bool = False, log_dir: str = None):
        """
        Args:
            log: display name of the log. If Log object, will extract name from that.
                Typically, this second method is done in the name of assigning a child log a parent.
                If NoneType, will use __name__.
            child_name: str, name of the child log.
                This is used when the log being made is considered a child to the parent log name
            log_to_file: if True, will create a file handler for outputting logs to file.
                The files are incremented in days, with the date appended to the file name.
                Logs older than 20 days will be removed upon instantiation
            log_level_str: str, minimum logging level to write to log (Levels: DEBUG -> INFO -> WARN -> ERROR)
                default: 'INFO'
            log_dir: str, directory to save the log
                default: "~/logs/{log_name}/"
        """
        # If 'Log', it's a parent Log instance. Take the name from the object. Otherwise it's just a string
        if log is None:
            log = __name__
        self.is_child = child_name is not None
        self.log_name = log.name if isinstance(log, (Log, Logger)) else log
        self.log_to_file = log_to_file
        self.log_parent = log if self.is_child else None

        # Determine if log is child of other Log objects (if so, it will be attached to that parent log)
        # Instantiate the log object
        if self.is_child:
            # Attach this instance to the parent log
            suffix = '.'.join([self.log_name, child_name])
            super().__init__(suffix, self.DEFAULT_LOG_LEVEL)
            # Attempt to check for the parent log's log_to_file variable.
            try:
                self.log_to_file = self.log_parent.log_to_file
            except AttributeError:
                pass
        else:
            # Create logger if it hasn't been created
            super().__init__(self.log_name, self.DEFAULT_LOG_LEVEL)

        # Check if debugging in pycharm
        # Checking Methods:
        #   1) checks for whether code run in-console
        #   2) check for script run in debug mode per PyCharm
        sysargs = sys.argv
        self.is_debugging = any(['pydevconsole.py' in sysargs[0], sys.gettrace() is not None])
        # Set the log level (will automatically set to DEBUG if is_debugging)
        self._set_log_level(log_level_str)

        # Set the log handlers
        if self.log_to_file:
            self._build_log_path(log_dir)
        self._set_handlers()
        self.info(f'Logging initiated{" for child instance" if self.is_child else ""}.')

    def _build_log_path(self, log_dir: str):
        """Builds a filepath to the log file"""
        # Set name of file
        self.log_filename = f"{self.log_name}"
        # Set log directory (if none)
        home_dir = os.path.join(os.path.expanduser('~'), 'logs')
        log_dir = os.path.join(home_dir, log_dir if log_dir is not None else self.log_name)
        # Check if logging directory exists
        if not os.path.exists(log_dir):
            # If dir doesn't exist, create
            os.makedirs(log_dir)

        # Path of logfile
        self.log_path = os.path.join(log_dir, self.log_filename)

    def _set_log_level(self, log_level_str: str):
        """Determines the minimum log level to set.
        Logging progression: DEBUG -> INFO -> WARN -> ERROR -> CRITICAL

        Methodology breakdown:
            1. Looks for manually set string
            2. If child, looks at parent's log level
            3. If not, checks for script-level arguments passed in
        """
        if log_level_str is None:
            if self.is_child:
                log_level_str = logging.getLevelName(self.log_parent.log_level_int) \
                    if isinstance(self.log_parent, Log) else self.DEFAULT_LOG_LEVEL
            else:
                # No log level provided. Check if any included as cmd argument
                log_level_str = LogArgParser(self.is_debugging).log_level_str
        self.log_level_str = log_level_str
        self.log_level_int = getattr(logging, log_level_str.upper(), logging.DEBUG)
        # Set minimum logging level
        self.setLevel(self.log_level_int)

    def _set_handlers(self):
        """Sets up file & stream handlers"""
        # Set format of logs
        formatter = logging.Formatter('%(asctime)s - %(name)s_%(process)d - %(levelname)-8s %(message)s')
        # Create streamhandler for log (this sends streams to stdout/stderr for debug help)
        sh = logging.StreamHandler()
        sh.setLevel(self.log_level_int)
        sh.setFormatter(formatter)
        self.addHandler(sh)

        if self.log_to_file:
            # TimedRotating will delete logs older than 30 days
            # fh = TimedRotatingFileHandler(self.log_path, when='h', interval=24, backupCount=30)
            fh = CustomTimedRotatingFileHandler(self.log_path, when='d', interval=1, backup_cnt=30)
            fh.setLevel(self.log_level_int)
            fh.setFormatter(formatter)
            self.addHandler(fh)
        # Intercept exceptions
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type: type, exc_value: BaseException, exc_traceback: TracebackType):
        """Default wrapper for handling exceptions. Can be overwritten by classes that inherit Log class"""
        self._handle_exception(exc_type=exc_type, exc_value=exc_value, exc_traceback=exc_traceback)

    def _handle_exception(self, exc_type: type, exc_value: BaseException, exc_traceback: TracebackType):
        """Intercepts an exception and prints it to log file"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        self.error('Uncaught exception', exc_info=(exc_type, exc_value, exc_traceback))

    def error_from_class(self, err_obj: BaseException, text: str):
        """Default wrapper for extracting exceptions from Exception class.

        Can be overwritten by classes that inherit the Log class"""
        self._error_from_class(err_obj=err_obj, text=text)

    def _error_from_class(self, err_obj: BaseException, text: str):
        """Error logging for exception objects"""
        traceback_msg = '\n'.join(traceback.format_tb(err_obj.__traceback__))
        exception_msg = f'{err_obj.__class__.__name__}: {err_obj}\n{traceback_msg}'
        err_msg = f'{text}\n{exception_msg}'
        self.error(err_msg)

    @staticmethod
    def extract_err() -> Tuple[Optional[type], Optional[BaseException], Optional[TracebackType]]:
        """Calls sys.exec_info() to get error details upon error instance
        Returns:
            (error type, error object, error traceback)
        """
        return sys.exc_info()

    def close(self):
        """Close logger"""
        disconn_msg = 'Log disconnected'
        if self.is_child:
            self.info(f'{disconn_msg} for child instance.')
        else:
            self.info(f'{disconn_msg}.\n' + '-' * 80)
            for handler in self.handlers:
                handler.close()
                self.removeHandler(handler)
