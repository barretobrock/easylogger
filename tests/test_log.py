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
        child_child.close()
        child_2.close()
        child_1.close()
        parent.close()

    def test_none_log(self):
        log = Log()
        self.assertTrue(isinstance(log.log_name, str))
        self.assertTrue(isinstance(log.name, str))
        log.error('Test')
        log.close()

    def test_orphan(self):
        """Test that handlers are still made in the instance of an orphaned child log"""
        log = Log(None, child_name='child', log_to_file=True)
        log.info('Test')
        with self.assertRaises(ValueError) as err:
            raise ValueError('Test')
        log.close()

    def test_filehandler(self):
        log = Log('test-filehandler', log_to_file=True)
        log2 = Log(log, child_name='child')
        self.assertTrue(log2.log_to_file)
        self.assertTrue(log.log_path == log2.log_path)
        self.assertTrue(len(log.log_obj.handlers) == 2)
        self.assertTrue(len(log2.log_obj.handlers) == 0)
        log.error('Test exception')
        log2.info('test')
        log3 = Log(log2, child_name='child of child')
        log2.warning('Hello!')
        log3.info('HI!')
        log3.close()
        log2.close()
        log.close()

    def test_nested_logs(self):
        log = Log('main', log_to_file=True)
        c_log = None
        for i in range(10):
            if c_log is None:
                c_log = Log(log, child_name=f'child_{i}')
            else:
                c_log = Log(c_log, child_name=f'child_{i}')


if __name__ == '__main__':
    unittest.main()
