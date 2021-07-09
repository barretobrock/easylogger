import os
import sys
import logging
import traceback
from logging import Logger
from types import TracebackType
from typing import Union, Tuple, Optional
from .argparser import LogArgParser
from .handlers import CustomTimedRotatingFileHandler


class Log:
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
        if self.is_child and isinstance(self.log_parent, (Log, Logger)):
            # Attach this instance to the parent log if it's the proper object
            self.log_obj = self.log_parent.log_obj.getChild(child_name)
            # Attempt to check for the parent log's log_to_file variable.
            try:
                self.log_to_file = self.log_parent.log_to_file
            except AttributeError:
                pass
        else:
            # Create logger if it hasn't been created
            self.log_obj = logging.getLogger(self.log_name)
            self.log_obj.setLevel(self.DEFAULT_LOG_LEVEL)

        # Patch some things in for cross-class compatibility
        self.name = self.log_name
        self.debug = self.log_obj.debug
        self.info = self.log_obj.info
        self.warning = self.log_obj.warning
        self.error = self.log_obj.error
        self.getChild = self.log_obj.getChild
        self.setLevel = self.log_obj.setLevel
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
        if not self.is_child and len(self.log_obj.handlers) == 0:
            # We only need a handler for the parent log object
            self._set_handlers()
        self.info(f'Logging initiated{" for child instance" if self.is_child else ""}.')

    def _build_log_path(self, log_dir: str):
        """Builds a filepath to the log file"""
        # First just check if the log is a child of another.
        #   If so, we can bypass the logic below it and use the parent log's file path
        if self.is_child:
            try:
                self.log_path = self.log_parent.log_path
                return
            except AttributeError:
                pass
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
        self.log_obj.setLevel(self.log_level_int)

    def _set_handlers(self):
        """Sets up file & stream handlers"""
        # Set format of logs
        formatter = logging.Formatter('%(asctime)s - %(process)d - %(levelname)-8s - %(name)s - %(message)s')
        # Create streamhandler for log (this sends streams to stdout for debug help)
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(self.log_level_int)
        sh.setFormatter(formatter)
        self.log_obj.addHandler(sh)

        if self.log_to_file:
            # TimedRotating will delete logs older than 30 days
            fh = CustomTimedRotatingFileHandler(self.log_path, when='d', interval=1, backup_cnt=30)
            fh.setLevel(self.log_level_int)
            fh.setFormatter(formatter)
            self.log_obj.addHandler(fh)
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
            for handler in self.log_obj.handlers:
                handler.close()
                self.log_obj.removeHandler(handler)
