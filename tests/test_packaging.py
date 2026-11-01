"""Real subprocess cleanup checks, including Windows file-handle cleanup."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('packaging_smoke', Path(__file__).resolve().parents[1] / 'scripts' / 'smoke_backend.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class PackagingCleanup(unittest.TestCase):
    def launch(self, script):
        actual_popen = subprocess.Popen
        processes = []
        def start(_command, **kwargs):
            process = actual_popen([sys.executable, '-c', script], **kwargs)
            processes.append(process)
            return process
        return start, processes

    def test_failure_after_ready_stops_backend_and_releases_log(self):
        launch, processes = self.launch("import time; print('LEDGERLY_READY=http://127.0.0.1:1',flush=True); time.sleep(60)")
        with tempfile.TemporaryDirectory() as data:
            with patch.object(smoke.subprocess, 'Popen', side_effect=launch):
                with self.assertRaisesRegex(RuntimeError, 'HTTP check failed'):
                    with smoke.running_backend(data):
                        raise RuntimeError('HTTP check failed')
            self.assertIsNotNone(processes[0].poll())
            # Windows refuses this if either the service or test owns the handle.
            (Path(data) / 'startup.log').unlink()

    def test_startup_crash_preserves_diagnostic_and_releases_log(self):
        launch, processes = self.launch("print('Startup diagnostic',flush=True); raise SystemExit(3)")
        with tempfile.TemporaryDirectory() as data:
            with patch.object(smoke.subprocess, 'Popen', side_effect=launch):
                with self.assertRaisesRegex(RuntimeError, 'Startup diagnostic'):
                    with smoke.running_backend(data):
                        self.fail('Crashed backend must never be ready')
            self.assertEqual(processes[0].poll(), 3)
            (Path(data) / 'startup.log').unlink()

    def test_launch_failure_closes_log_before_cleanup(self):
        with tempfile.TemporaryDirectory() as data:
            with patch.object(smoke.subprocess, 'Popen', side_effect=OSError('Cannot launch backend')):
                with self.assertRaisesRegex(OSError, 'Cannot launch'):
                    with smoke.running_backend(data):
                        self.fail('Missing backend must never be ready')
            (Path(data) / 'startup.log').unlink()
