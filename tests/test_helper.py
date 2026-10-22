import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('control', str(ROOT / 'scripts/omarchy-clamav-control'))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
control = importlib.util.module_from_spec(spec)
loader.exec_module(control)


def completed(code=0, stdout='', stderr=''):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.scanner = (ROOT / 'tests/fixtures/clamd.conf').read_text() + 'OnAccessExcludeUname clamav\n'
        self.updater = (ROOT / 'tests/fixtures/freshclam.conf').read_text()
        (self.folder / 'clamd.conf').write_text(self.scanner)
        (self.folder / 'freshclam.conf').write_text(self.updater)
        self.data = {'include': [str(self.folder)], 'exclude': [], 'maxSize': '20M'}

    def test_first_setup_and_exclusion_preservation(self):
        account = types.SimpleNamespace(pw_uid=64)
        with patch.object(control.pwd, 'getpwnam', return_value=account):
            for text in ['', 'User clamav\n', 'User antivirus\n']:
                with self.subTest(text=text):
                    changes = control.scanner_setup(text)
                    expected = {'OnAccessExcludeUname': [control.directives(text).get('User', ['clamav'])[0]]}
                    if not text:
                        expected['User'] = ['clamav']
                    self.assertEqual(changes, expected)
            for exclusion in ['OnAccessExcludeUID 64', 'OnAccessExcludeUname clamav']:
                self.assertEqual(control.scanner_setup(exclusion + '\nUser clamav\n'), {})
                self.assertEqual(control.scanner_setup(exclusion + '\n'), {'User': ['clamav']})
            for exclusion in ['OnAccessExcludeUID 123', 'OnAccessExcludeUname other', 'OnAccessExcludeRootUID yes']:
                changes = control.scanner_setup(exclusion + '\nUser clamav\n')
                self.assertEqual(changes['OnAccessExcludeUname'][-1], 'clamav')
                output = control.render(exclusion + '\nUser clamav\n', changes)
                self.assertIn(exclusion + '\n', output)
                self.assertEqual(control.scanner_setup(output), {})
        for text in ['User root\n', 'User bad/name\n', 'User clamav\nUser other\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                control.scanner_setup(text)
        for uid in [0, 1000]:
            with patch.object(control.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=uid)), self.assertRaises(ValueError):
                control.scanner_setup('User clamav\n')
        with patch.object(control.pwd, 'getpwnam', side_effect=KeyError), self.assertRaisesRegex(ValueError, 'account'):
            control.scanner_setup('')
        with patch.object(control.pwd, 'getpwnam', return_value=account):
            self.assertEqual(control.scanner_setup('OnAccessExcludeRootUID no\n'), {'OnAccessExcludeUname': ['clamav'], 'User': ['clamav']})

    def test_pristine_apply_adds_exclusion_without_starting_services(self):
        path = self.folder / 'clamd.conf'
        text = '# packaged defaults\nLocalSocket /run/clamav/clamd.ctl\n'
        path.write_text(text)
        with patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate'), patch.object(control.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=64)), patch.object(control, 'run') as run:
            control.apply_config('scanner', self.data, control.revision(text))
            run.assert_not_called()
        parsed = control.directives(path.read_text())
        self.assertEqual(parsed['OnAccessExcludeUname'], ['clamav'])
        self.assertEqual(parsed['User'], ['clamav'])
        self.assertEqual(parsed['OnAccessIncludePath'], self.data['include'])
        self.assertEqual(parsed['LocalSocket'], ['/run/clamav/clamd.ctl'])

    def test_start_is_accepted_not_claimed_healthy_after_immediate_exit(self):
        with patch.object(control, 'run', return_value=completed()):
            self.assertIn('accepted', control.service('scanner', 'start')['message'])
        raw = 'LoadState=loaded\nActiveState=failed\nResult=exit-code\nExecMainStatus=2\n'
        with patch.object(control, 'checked', return_value=raw), patch.object(control, 'read_config', side_effect=PermissionError):
            state = control.status()['services']['scanner']
        self.assertEqual(state['active'], 'failed')
        self.assertIn('exit-code', state['diagnostic'])
        self.assertIn('2', state['diagnostic'])

    def test_status_setup_prerequisites_and_blockers(self):
        for text, expected in [
                ('Example\n', 'Package Example'),
                ('User missing\n', 'account does not exist'),
                ('User clamav\n', 'Apply will add daemon exclusion: clamav'),
                ('OnAccessExcludeUID 64\n', 'set missing User to clamav'),
                ('OnAccessExcludeUname clamav\nUser clamav\n', 'Existing user exclusions:')]:
            with self.subTest(text=text), patch.object(control, 'checked', return_value=''), patch.object(control, 'read_config', return_value=(text, None)), patch.object(control.pwd, 'getpwnam', side_effect=KeyError if 'missing' in text else None, return_value=types.SimpleNamespace(pw_uid=64)):
                setup = control.status()['configs']['scanner']['setup']
                self.assertTrue(any(expected in line for line in setup), setup)
                self.assertTrue(any('watched directory' in line for line in setup))

    def test_nonstart_service_message(self):
        with patch.object(control, 'run', return_value=completed()):
            self.assertIn('Completed stop', control.service('updater', 'stop')['message'])

    def test_parse_repeated_and_comments(self):
        parsed = control.directives(self.scanner)
        self.assertEqual(parsed['OnAccessIncludePath'], ['/home', '/srv'])
        self.assertEqual(parsed['OnAccessDenyOnError'], ['yes'])

    def test_render_preserves_unrelated_comments_and_replaces_all_paths(self):
        changes = control.replacements('scanner', self.data)
        output = control.render(self.scanner, changes)
        self.assertIn('OnAccessDenyOnError yes\n', output)
        self.assertIn('# OnAccessIncludePath /commented\n', output)
        self.assertIn('LogFile /var/log/clamav/clamd.log\n', output)
        self.assertEqual(control.directives(output)['OnAccessIncludePath'], [str(self.folder)])
        self.assertNotIn('OnAccessExcludePath', control.directives(output))
        self.assertEqual(output, control.render(output, changes))

    def test_updater_preserves_mirror_and_notify(self):
        output = control.render(self.updater, control.replacements('updater', {'checks': 24}))
        self.assertIn('DatabaseMirror database.clamav.net\n', output)
        self.assertIn('NotifyClamd /etc/clamav/clamd.conf\n', output)
        self.assertEqual(control.directives(output)['Checks'], ['24'])

    def test_paths_reject_injection_nonexistent_relative_duplicates(self):
        for paths in [['relative'], ['/not/a/real/clamav/test/path'], ['/home\nChecks 1'],
                      ['/home#comment'], ['/home/../etc'], ['//etc'], ['/tmp', '/tmp'], ['/home\\x'], 'bad']:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                control.paths(paths)
        self.assertEqual(control.paths([str(self.folder)]), [str(self.folder)])

    def test_value_and_action_restrictions(self):
        for value in [0, 51, True, '12', 1.5, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                control.replacements('updater', {'checks': value})
        for size in ['0', '0M', '5G', '-1', '1M\nLogFile /tmp/x', 'ten', '1.5M']:
            with self.subTest(size=size), self.assertRaises(ValueError):
                control.replacements('scanner', dict(self.data, maxSize=size))
        for data in [dict(self.data, include=[]), dict(self.data, exclude=self.data['include']),
                     dict(self.data, LogFile='/tmp/x')]:
            with self.assertRaises(ValueError):
                control.replacements('scanner', data)
        with patch.object(control, 'run') as run:
            for kind, action in [('ssh', 'start'), ('socket', 'stop'), ('daemon', 'restart'), ('updater', '--help')]:
                with self.assertRaises(ValueError):
                    control.service(kind, action)
            run.assert_not_called()

    def test_service_dependencies_socket_and_boot_separation(self):
        with patch.object(control, 'run', return_value=completed()) as run:
            control.service('daemon', 'stop')
            self.assertEqual(run.call_args.args[0], ['/usr/bin/systemctl', 'stop', 'clamav-clamonacc.service', 'clamav-daemon.socket', 'clamav-daemon.service'])
            control.service('scanner', 'enable')
            self.assertEqual(run.call_args.args[0], ['/usr/bin/systemctl', 'enable', 'clamav-daemon.socket', 'clamav-daemon.service', 'clamav-clamonacc.service'])
            self.assertNotIn('--now', run.call_args.args[0])
            control.service('daemon', 'disable')
            self.assertIn('clamav-daemon.socket', run.call_args.args[0])
            self.assertIn('clamav-clamonacc.service', run.call_args.args[0])

    def test_service_failure_and_timeout_propagate(self):
        with patch.object(control, 'run', return_value=completed(1, stderr='Missing database')):
            with self.assertRaisesRegex(ValueError, 'Missing database'):
                control.service('scanner', 'start')
        with patch.object(control, 'run', side_effect=subprocess.TimeoutExpired('systemctl', 45)):
            with self.assertRaises(subprocess.TimeoutExpired):
                control.service('updater', 'start')

    def config_read(self, path):
        # Ownership checks are tested separately; fixture edits never need root.
        return path.read_text(), path.stat()

    def test_backup_atomic_write_and_revision(self):
        with patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate'):
            result = control.apply_config('scanner', self.data, control.revision(self.scanner))
            self.assertEqual(Path(result['backup']).read_text(), self.scanner)
            self.assertEqual(Path(result['backup']).stat().st_mode & 0o777, 0o600)
            self.assertEqual(control.directives((self.folder / 'clamd.conf').read_text())['OnAccessMaxFileSize'], ['20M'])
            self.assertEqual((self.folder / 'freshclam.conf').read_text(), self.updater)
            with self.assertRaisesRegex(ValueError, 'changed since'):
                control.apply_config('scanner', self.data, control.revision(self.scanner))

    def test_validation_and_atomic_replace_failure_leave_original(self):
        for failure in ['validation', 'replace']:
            with self.subTest(failure=failure), patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate', side_effect=ValueError('invalid') if failure == 'validation' else None), patch.object(control.os, 'replace', side_effect=OSError('disk error')):
                with self.assertRaises((ValueError, OSError)):
                    control.apply_config('scanner', self.data, control.revision(self.scanner))
                self.assertEqual((self.folder / 'clamd.conf').read_text(), self.scanner)
                self.assertEqual(list(self.folder.glob('.omarchy-*')), [])

    def test_external_edit_during_fsync_is_not_overwritten(self):
        path = self.folder / 'clamd.conf'
        changed = self.scanner + '# External administrator edit\n'
        calls = 0
        def fsync(_fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_text(changed)
        with patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate'), patch.object(control.os, 'fsync', side_effect=fsync), patch.object(control.os, 'replace') as replace:
            with self.assertRaisesRegex(ValueError, 'before replacement'):
                control.apply_config('scanner', self.data, control.revision(self.scanner))
            replace.assert_not_called()
        self.assertEqual(path.read_text(), changed)
        self.assertEqual(list(self.folder.glob('.omarchy-*')), [])

    def test_backup_failure_leaves_original(self):
        with patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate'), patch.object(control.os, 'open', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                control.apply_config('scanner', self.data, control.revision(self.scanner))
            self.assertEqual((self.folder / 'clamd.conf').read_text(), self.scanner)

    def test_parse_diagnostics_not_directive_names(self):
        # Keep temporary validation files inside this project during tests.
        temporary_directory = tempfile.TemporaryDirectory
        def local_temp(**kwargs):
            return temporary_directory(dir=self.folder, **kwargs)
        with patch.object(control.tempfile, 'TemporaryDirectory', side_effect=local_temp):
            with patch.object(control, 'run', return_value=completed(stdout='OnAccessDenyOnError disabled\nOnErrorExecute disabled\n')):
                control.validate_candidate('clamd.conf', self.scanner)
                control.validate_candidate('freshclam.conf', self.updater)
            with patch.object(control, 'run', return_value=completed(stderr='ERROR: Parse error at candidate:2')):
                with self.assertRaisesRegex(ValueError, 'rejected'):
                    control.validate_candidate('clamd.conf', 'bad')

    @unittest.skipUnless(Path('/usr/bin/clamconf').exists(), 'clamconf not installed')
    def test_real_clamconf_fixture_validation(self):
        temporary_directory = tempfile.TemporaryDirectory
        def local_temp(**kwargs):
            return temporary_directory(dir=self.folder, **kwargs)
        with patch.object(control.tempfile, 'TemporaryDirectory', side_effect=local_temp):
            control.validate_candidate('clamd.conf', self.scanner)
            control.validate_candidate('freshclam.conf', self.updater)
            invalid = (ROOT / 'tests/fixtures/invalid/clamd.conf').read_text()
            with self.assertRaisesRegex(ValueError, 'rejected'):
                control.validate_candidate('clamd.conf', invalid)

    def test_example_config_removed_only_on_explicit_apply(self):
        path = self.folder / 'clamd.conf'
        text = self.scanner + 'Example\n'
        path.write_text(text)
        with patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate'):
            result = control.apply_config('scanner', self.data, control.revision(text))
        self.assertNotIn('Example', control.directives(path.read_text()))
        self.assertEqual(Path(result['backup']).read_text(), text)

    def test_read_config_rejects_untrusted_owner_symlink_fifo(self):
        # No root required: mock only the parent ownership to reach file checks.
        parent_stat = types.SimpleNamespace(st_uid=0, st_mode=0o40755)
        with patch.object(Path, 'stat', return_value=parent_stat):
            if os.geteuid() != 0:
                with self.assertRaisesRegex(ValueError, 'root-owned'):
                    control.read_config(self.folder / 'clamd.conf')
            link = self.folder / 'link'
            link.symlink_to(self.folder / 'clamd.conf')
            with self.assertRaises(OSError):
                control.read_config(link)
            fifo = self.folder / 'fifo'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                control.read_config(fifo)

    def test_status_missing_units_and_unreadable_config_are_unknown(self):
        with patch.object(control, 'run', return_value=completed(stdout='LoadState=not-found\nActiveState=inactive\n')), patch.object(control, 'read_config', side_effect=PermissionError('denied')):
            result = control.status()
            self.assertEqual(result['services']['scanner']['active'], 'unknown')
            self.assertEqual(result['configs'], {})
            self.assertEqual(len(result['errors']), 2)
        with patch.object(control, 'run', side_effect=OSError('unavailable')), patch.object(control, 'read_config', side_effect=PermissionError('denied')):
            self.assertEqual(control.status()['services']['socket']['active'], 'unknown')

    def test_read_config_safe_and_oversized_files(self):
        parent = types.SimpleNamespace(st_uid=0, st_mode=0o40755)
        info = types.SimpleNamespace(st_uid=0, st_mode=0o100644)
        path = self.folder / 'clamd.conf'
        with patch.object(Path, 'stat', return_value=parent), patch.object(control.os, 'fstat', return_value=info):
            self.assertEqual(control.read_config(path), (self.scanner, info))
            path.write_text('x' * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, 'too large'):
                control.read_config(path)
        for parent in [types.SimpleNamespace(st_uid=1000, st_mode=0o40755),
                       types.SimpleNamespace(st_uid=0, st_mode=0o40777)]:
            with patch.object(Path, 'stat', return_value=parent):
                with self.assertRaisesRegex(ValueError, 'Unsafe config directory'):
                    control.read_config(path)

    def test_render_missing_newline_and_unknown_operation(self):
        self.assertEqual(control.render('Keep yes', {'Checks': ['3']}), 'Keep yes\nChecks 3\n')
        with self.assertRaisesRegex(ValueError, 'Unknown configuration'):
            control.replacements('updater', {'unexpected': 12})

    def test_apply_no_change_does_not_validate_or_backup(self):
        text = control.render(self.updater, {'Checks': ['24']})
        (self.folder / 'freshclam.conf').write_text(text)
        with patch.object(control, 'CONFIG', self.folder), patch.object(control, 'read_config', side_effect=self.config_read), patch.object(control, 'validate_candidate') as validate:
            self.assertEqual(control.apply_config('updater', {'checks': 24}, control.revision(text)), {'message': 'No changes'})
            validate.assert_not_called()
        self.assertEqual(list(self.folder.glob('*.bak')), [])

    def test_status_loaded_units_and_config_defaults(self):
        raw = 'LoadState=loaded\nActiveState=active\nUnitFileState=enabled\nExecStart=scan --move=/quarantine\nignored\n'
        with patch.object(control, 'checked', return_value=raw), patch.object(control, 'read_config', return_value=('', None)):
            result = control.status()
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['services']['scanner'], {'active': 'active', 'boot': 'enabled', 'policy': 'scan --move=/quarantine', 'diagnostic': 'Result: unknown; exit status: unknown'})
        self.assertEqual(result['services']['daemon']['policy'], '')
        self.assertEqual(result['configs']['scanner']['values'], {'include': [], 'exclude': [], 'maxSize': '5M'})
        self.assertEqual(result['configs']['updater']['values'], {'checks': '12'})
        with patch.object(control, 'checked', return_value=raw), patch.object(control, 'read_config', side_effect=[(self.scanner, None), (self.updater, None)]):
            result = control.status()
        self.assertEqual(result['configs']['scanner']['values']['include'], ['/home', '/srv'])
        self.assertEqual(result['configs']['updater']['revision'], control.revision(self.updater))

    def test_lock_validation_contention_and_cleanup(self):
        for mode, uid, failure in [(0o100600, 0, None), (0o100622, 0, ValueError),
                                   (0o100600, 1000, ValueError), (0o010600, 0, ValueError)]:
            with self.subTest(mode=mode, uid=uid), patch.object(control.os, 'open', return_value=77) as opened, patch.object(control.os, 'fstat', return_value=types.SimpleNamespace(st_mode=mode, st_uid=uid)), patch.object(control.os, 'close') as close, patch.object(control.fcntl, 'flock') as flock:
                if failure:
                    with self.assertRaisesRegex(failure, 'Unsafe control lock'), control.lock():
                        self.fail('unsafe lock entered')
                    flock.assert_not_called()
                else:
                    with control.lock():
                        flock.assert_called_once_with(77, control.fcntl.LOCK_EX | control.fcntl.LOCK_NB)
                opened.assert_called_once_with('/run/omarchy-clamav-control.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                close.assert_called_once_with(77)
        with patch.object(control.os, 'open', return_value=77), patch.object(control.os, 'fstat', return_value=types.SimpleNamespace(st_mode=0o100600, st_uid=0)), patch.object(control.os, 'close') as close, patch.object(control.fcntl, 'flock', side_effect=BlockingIOError('busy')):
            with self.assertRaises(BlockingIOError), control.lock():
                self.fail('busy lock entered')
            close.assert_called_once_with(77)

    def test_main_dispatch_and_request_limits(self):
        with patch.object(control, 'status', return_value={'services': {}}) as status, patch.object(control.os, 'geteuid') as uid:
            self.assertEqual(control.main(['status']), {'services': {}})
            status.assert_called_once_with()
            uid.assert_not_called()
        with patch.object(control.os, 'geteuid', return_value=0), patch.object(control, 'lock'), patch.object(control, 'service', return_value={'message': 'ok'}) as service, patch.object(control, 'apply_config', return_value={'message': 'saved'}) as apply:
            self.assertEqual(control.main(['service', 'scanner', 'stop']), {'message': 'ok'})
            service.assert_called_once_with('scanner', 'stop')
            self.assertEqual(control.main(['apply', 'updater', 'revision', '{"checks": 24}']), {'message': 'saved'})
            apply.assert_called_once_with('updater', {'checks': 24}, 'revision')
            for payload, error in [(' ' * 131073, 'Request too large'), ('[]', 'Expected a JSON object'), ('{', 'Expecting property')]:
                with self.subTest(payload=payload[:20]), self.assertRaisesRegex(ValueError, error):
                    control.main(['apply', 'updater', 'revision', payload])
            self.assertEqual(apply.call_count, 1)

    def test_privilege_and_main_allowlist(self):
        with patch.object(control.os, 'geteuid', return_value=1000), patch.object(control, 'service') as service:
            with self.assertRaisesRegex(ValueError, 'authentication'):
                control.main(['service', 'scanner', 'start'])
            service.assert_not_called()
        with patch.object(control.os, 'geteuid', return_value=0), patch.object(control, 'lock'), patch.object(control, 'run') as run:
            for args in [['shell', 'id'], ['apply', '/etc/passwd', 'x', '{}'], ['service', 'updater', 'restart'], ['apply', 'updater', 'x', '[]']]:
                with self.assertRaises(ValueError):
                    control.main(args)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
