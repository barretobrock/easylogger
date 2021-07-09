import argparse
from typing import List, Dict, Union


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
