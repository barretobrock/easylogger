import unittest
from unittest import mock
from argparse import Namespace
from easylogger import ArgParse
from tests.mocks.argparse_mocks import MOCK_1, MOCK_2


class TestArgParse(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def test_argparse_1(self):
        """Test that the default arguments are set"""
        defaults = ArgParse(MOCK_1, parse_all=False).parse()
        self.assertTrue(defaults[0].this == 'hello')

    def test_argparse_2(self):
        """Test that the default arguments are set"""
        defaults = ArgParse(MOCK_2, parse_all=True).parse()
        self.assertTrue(defaults.level == 'WARN')


if __name__ == '__main__':
    unittest.main()
