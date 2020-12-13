import unittest
from easylogger import Log


class TestLogger(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def test_child_log(self):
        parent = Log('parent', log_level_str='DEBUG')
        # Regular child - should inherit level
        child_1 = Log(parent, child_name='child_1')
        # Child 2 should have a different log leve
        child_2 = Log(parent, child_name='child_2', log_level_str='WARN')
        # Child of a child test
        child_child = Log(child_1, child_name='child^2')
        self.assertTrue(not parent.is_child)
        self.assertTrue(child_1.log_level_int == parent.log_level_int)
        self.assertTrue(child_2.log_level_int != parent.log_level_int)

    def test_none_log(self):
        log = Log()
        self.assertTrue(isinstance(log.log_name, str))
        self.assertTrue(isinstance(log.name, str))
        log.error('Test')

    def test_orphan(self):
        """Test that handlers are still made in the instance of an orphaned child log"""
        log = Log(None, child_name='child')
        log.info('Test')
        with self.assertRaises(ValueError) as err:
            raise ValueError('Test')

    def test_filehandler(self):
        log = Log('test-filehandler', log_to_file=True)
        log2 = Log(log, child_name='child')
        log.error('Test exception')
        log2.info('test')


if __name__ == '__main__':
    unittest.main()
