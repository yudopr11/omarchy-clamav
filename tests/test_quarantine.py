"""Fixed quarantine setup boundary; no live filesystem or service mutations."""
import contextlib
import os
import stat
import types
import unittest
from unittest.mock import patch

from test_helper import control

POLICY = 'LoadState=loaded\nUser=\nGroup=\nDynamicUser=no\nRootDirectory=\nRootImage=\nExecStart={ path=/usr/bin/clamonacc ; argv[]=/usr/bin/clamonacc -F --move=/root/quarantine ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }\n'

def info(mode, uid=0, gid=0):
    return types.SimpleNamespace(st_mode=mode, st_uid=uid, st_gid=gid)

class QuarantineTests(unittest.TestCase):
    def boundary(self, existing=False):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(control, 'checked', return_value=POLICY))
        self.open = stack.enter_context(patch.object(control.os, 'open', return_value=10))
        self.close = stack.enter_context(patch.object(control.os, 'close'))
        self.fstat = stack.enter_context(patch.object(control.os, 'fstat', return_value=info(stat.S_IFDIR | 0o700)))
        self.stat = stack.enter_context(patch.object(control.os, 'stat', side_effect=None if existing else FileNotFoundError, return_value=info(stat.S_IFDIR | 0o700)))
        self.mkdir = stack.enter_context(patch.object(control.os, 'mkdir'))

    def test_missing_explicit_create_and_existing_no_change(self):
        self.boundary()
        self.assertEqual(control.quarantine()['state'], 'missing')
        self.mkdir.assert_not_called()
        self.stat.side_effect = [FileNotFoundError(), info(stat.S_IFDIR | 0o700)]
        self.assertIn('not started', control.quarantine(True)['message'])
        self.mkdir.assert_called_once_with('quarantine', mode=0o700, dir_fd=10)
        self.stat.side_effect = None
        self.assertEqual(control.quarantine()['state'], 'ready')
        control.quarantine(True)
        self.assertEqual(self.mkdir.call_count, 1)
        self.assertTrue(self.open.call_args_list[0].args[1] & os.O_NOFOLLOW)
        self.assertEqual(self.stat.call_args.kwargs, {'dir_fd': 10, 'follow_symlinks': False})

    def test_local_packaged_command(self):
        self.boundary(True)
        raw = POLICY.replace('/usr/bin/clamonacc', '/usr/sbin/clamonacc').replace('-F --move', '-F --log=/var/log/clamav/clamonacc.log --move').replace('User=\n', 'User=root\n')
        with patch.object(control, 'checked', return_value=raw):
            self.assertEqual(control.quarantine()['state'], 'ready')

    def test_unsafe_parent_and_destination(self):
        self.boundary(True)
        for mode, uid, gid in [(stat.S_IFLNK | 0o700, 0, 0), (stat.S_IFREG | 0o700, 0, 0), (stat.S_IFDIR | 0o777, 0, 0), (stat.S_IFDIR | 0o700, 1000, 0), (stat.S_IFDIR | 0o700, 0, 1000)]:
            self.stat.return_value = info(mode, uid, gid)
            with self.assertRaisesRegex(ValueError, 'Unsafe quarantine'):
                control.quarantine(True)
        self.stat.return_value = info(stat.S_IFDIR | 0o700)
        for mode, uid, gid in [(stat.S_IFDIR | 0o722, 0, 0), (stat.S_IFDIR | 0o700, 1000, 0), (stat.S_IFREG | 0o700, 0, 0)]:
            self.fstat.return_value = info(mode, uid, gid)
            with self.assertRaisesRegex(ValueError, 'Unsafe parent'):
                control.quarantine(True)
        self.mkdir.assert_not_called()

    def test_errors_and_raced_creation_propagate(self):
        self.boundary()
        for error in [PermissionError('denied'), FileExistsError('raced')]:
            self.mkdir.side_effect = error
            with self.assertRaises(type(error)):
                control.quarantine(True)
        self.open.side_effect = PermissionError('denied')
        with self.assertRaises(PermissionError):
            control.quarantine()

    def test_policy_must_match(self):
        self.boundary()
        for raw in ['', POLICY.replace('loaded', 'not-found'), POLICY.replace('/root/quarantine', '/unsupported/quarantine'), POLICY.replace(' -F ', ' --remove --move=/root/quarantine '), POLICY.replace('User=\n', 'User=clamav\n'), POLICY.replace('DynamicUser=no', 'DynamicUser=yes'), POLICY.replace('RootDirectory=\n', 'RootDirectory=/srv\n'), POLICY.replace('RootImage=\n', 'RootImage=/image\n'), POLICY.replace('Group=\n', 'Group=users\n'), POLICY.replace('/usr/bin/clamonacc', '/unsupported/clamonacc'), POLICY.replace(' ; ignore_errors', ' --copy=/unsupported ; ignore_errors')]:
            with self.subTest(raw=raw), patch.object(control, 'checked', return_value=raw), self.assertRaisesRegex(ValueError, 'Unsupported scanner policy'):
                control.quarantine(True)
        self.open.assert_not_called()
        self.mkdir.assert_not_called()

    def test_dispatch_and_status_errors(self):
        with patch.object(control.os, 'geteuid', return_value=0), patch.object(control, 'lock', return_value=contextlib.nullcontext()), patch.object(control, 'quarantine', return_value={'message': 'ok'}) as setup:
            self.assertEqual(control.main(['prepare-quarantine']), {'message': 'ok'})
            setup.assert_called_once_with(True)
            for args in [['prepare-quarantine', '/unsupported'], ['mkdir', '/root/quarantine']]:
                with self.assertRaisesRegex(ValueError, 'Action not allowed'):
                    control.main(args)
        for error in [ValueError('unsupported'), PermissionError('denied')]:
            with patch.object(control, 'quarantine', side_effect=error), patch.object(control, 'checked', return_value=''), patch.object(control, 'read_config', side_effect=PermissionError):
                state = control.status()['quarantine']
                self.assertEqual(state['state'], 'unavailable')
                self.assertIn(str(error), state['message'])
        with patch.object(control, 'quarantine', return_value={'state': 'missing'}), patch.object(control, 'checked', return_value=''), patch.object(control, 'read_config', side_effect=PermissionError):
            self.assertEqual(control.status()['quarantine']['state'], 'missing')
