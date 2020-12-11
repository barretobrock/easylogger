import unittest
from unittest import mock
import argparse
from kavalkilu.log import ArgParse
from tests.mocks.argparse_mocks import MOCK_1, MOCK_2


class TestArgParse(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def test_argparse_1(self):
        with mock.patch('argparse.ArgumentParser.parse_args') as mock_request:
            mock_request.return_value = argparse.Namespace(this='something')
            args = ArgParse(MOCK_1, parse_all=False).parse()
        self.assertTrue(args[0].this == 'something')


if __name__ == '__main__':
    unittest.main()
