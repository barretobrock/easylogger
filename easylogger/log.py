#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General log setup file.
"""
import os
import sys
import logging
import argparse
import traceback
from logging import Logger
from logging.handlers import TimedRotatingFileHandler
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


class Log(Logger):
    """Initiates a logging object to record processes and errors"""
    DEFAULT_LOG_LEVEL = 'INFO'

    def __init__(self, log: Union[str, 'Log', Logger] = None, child_name: str = None, log_level_str: str = None,
                 log_to_file: bool = False, log_dir: str = None):
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

        # super().__init__(self.log_name)
        # Determine if log is child of other Log objects (if so, it will be attached to that parent log)
        # Instantiate the log object
        if self.is_child:
            # Attach this instance to the parent log
            suffix = '.'.join([self.log_name, child_name])
            super().__init__(suffix, self.DEFAULT_LOG_LEVEL)
            # self.logger = logging.getLogger(self.log_name).getChild(child_name)
        else:
            # Create logger if it hasn't been created
            super().__init__(self.log_name, self.DEFAULT_LOG_LEVEL)
            # self.logger = logging.getLogger(self.log_name)
        self.parent = log if self.is_child else None

        # Check if debugging in pycharm
        # Checking Methods:
        #   1) checks for whether code run in-console
        #   2) check for script run in debug mode per PyCharm
        sysargs = sys.argv
        self.is_debugging = any(['pydevconsole.py' in sysargs[0], sys.gettrace() is not None])
        # Set the log level (will automatically set to DEBUG if is_debugging)
        self._set_log_level(log_level_str)

        # Set the log handlers
        if not self.is_child:
            # Create file handler for log (children of the object will simply inherit this)
            if log_to_file:
                self._build_log_path(log_dir)
            self._set_handlers(log_to_file)
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
                log_level_str = logging.getLevelName(self.parent.log_level_int) \
                    if isinstance(self.parent, Log) else self.DEFAULT_LOG_LEVEL
            else:
                # No log level provided. Check if any included as cmd argument
                log_level_str = LogArgParser(self.is_debugging).log_level_str
        self.log_level_str = log_level_str
        self.log_level_int = getattr(logging, log_level_str.upper(), logging.DEBUG)
        # Set minimum logging level
        self.setLevel(self.log_level_int)

    def _set_handlers(self, log_to_file: bool):
        """Sets up file & stream handlers"""
        # Set format of logs
        formatter = logging.Formatter('%(asctime)s - %(name)s_%(process)d - %(levelname)-8s %(message)s')
        # Create streamhandler for log (this sends streams to stdout/stderr for debug help)
        sh = logging.StreamHandler()
        sh.setLevel(self.log_level_int)
        sh.setFormatter(formatter)
        self.addHandler(sh)

        if log_to_file and not self.is_debugging:
            # TimedRotating will delete logs older than 30 days
            fh = TimedRotatingFileHandler(self.log_path, when='h', interval=24, backupCount=30)
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

    def _error(self, text: str, incl_info: bool = True):
        """Error-level logging - private to allow for other log
         classes to inherit this plus their additional procedures"""
        self.error(text, exc_info=incl_info)

    def error_from_class(self, err_obj: BaseException, text: str):
        """Default wrapper for extracting exceptions from Exception class.

        Can be overwritten by classes that inherit the Log class"""
        self._error_from_class(err_obj=err_obj, text=text)

    def _error_from_class(self, err_obj: BaseException, text: str):
        """Error logging for exception objects"""
        traceback_msg = '\n'.join(traceback.format_tb(err_obj.__traceback__))
        exception_msg = f'{err_obj.__class__.__name__}: {err_obj}\n{traceback_msg}'
        err_msg = f'{text}\n{exception_msg}'
        self._error(err_msg)

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
