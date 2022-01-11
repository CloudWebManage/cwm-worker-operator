import time
import subprocess


class Multiprocessor:

    def __init__(self, max_parallel_processes):
        self.max_parallel_processes = max_parallel_processes
        self.is_async = max_parallel_processes > 1
        self.processes = {}

    def _run_async(self, *args, **kwargs):
        raise NotImplementedError()

    def _run_sync(self,*args, **kwargs):
        raise NotImplementedError()

    def _get_process_key(self, *args, **kwargs):
        raise NotImplementedError()

    def get_active_processes(self):
        process: subprocess.Popen
        return sum((1 for process in self.processes.values() if process.poll() is None))

    def wait_for_available_process_slot(self):
        while self.get_active_processes() >= self.max_parallel_processes:
            time.sleep(1)

    def wait_for_all_processes_to_complete(self):
        while self.get_active_processes() != 0:
            time.sleep(1)

    def process(self, *args, **kwargs):
        if self.is_async:
            key = self._get_process_key(*args, **kwargs)
            assert key not in self.processes
            self.processes[key] = self._run_async(*args, **kwargs)
            self.wait_for_available_process_slot()
        else:
            self._run_sync(*args, **kwargs)

    def finalize(self):
        if self.is_async:
            self.wait_for_all_processes_to_complete()
            error_keys = set()
            process: subprocess.Popen
            for key, process in self.processes.items():
                if process.returncode == 0:
                    out = process.stdout.read().decode().strip()
                    if out:
                        print(out)
                else:
                    error_keys.add(key)
            if len(error_keys) > 0:
                for key in error_keys:
                    print("------")
                    print("Error in process key {} ({})".format(key, self.processes[key].returncode))
                    out = self.processes[key].stdout.read().decode().strip()
                    if out:
                        print(out)
                    print("------")
                raise Exception("Encountered errors in the following process keys: {}".format(", ".join(error_keys)))
