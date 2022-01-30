import json
import time
import subprocess
import traceback

JSON_RESPONSE_START = "--multiprocessor-start' + '-json-response--"
JSON_RESPONSE_END = "--multiprocessor-end' + '-json-response--"


def print_json_response(data):
    print(JSON_RESPONSE_START)
    json.dumps(data)
    print(JSON_RESPONSE_END)


class Multiprocessor:

    def __init__(self, max_parallel_processes):
        self.max_parallel_processes = max_parallel_processes
        self.is_async = max_parallel_processes > 1
        self.processes = {}
        self._async_processes_completed = set()
        self._async_processes_errored = set()

    def _init(self, *args, **kwargs):
        # can be implemented by extending classes to run initialization code
        pass

    def _run_async(self, *args, **kwargs):
        raise NotImplementedError()

    def _run_sync(self,*args, **kwargs):
        raise NotImplementedError()

    def _get_process_key(self, *args, **kwargs):
        raise NotImplementedError()

    def _handle_process_response(self, key, res):
        # can be implemented by extending classes to handle responses as they come in
        pass

    def get_active_processes(self):
        process: subprocess.Popen
        num_active_processes = 0
        for key, process in self.processes.items():
            if process.poll() is None:
                num_active_processes += 1
            elif key not in self._async_processes_completed:
                self._async_processes_completed.add(key)
                if process.returncode == 0:
                    out = process.stdout.read().decode().strip()
                    res = None
                    if out:
                        if JSON_RESPONSE_START in out and JSON_RESPONSE_END in out:
                            new_out = ''
                            tmp = out.strip().split(JSON_RESPONSE_START)
                            new_out += tmp[0].strip()
                            tmp = tmp[1].split(JSON_RESPONSE_END)
                            res = json.loads(tmp[0])
                            new_out += tmp[1].strip()
                            if new_out:
                                print(new_out)
                        else:
                            print(out)
                    self._handle_process_response(key, res)
                else:
                    self._async_processes_errored.add(key)
                    print("Error in process key {} ({})".format(key, self.processes[key].returncode))
                    out = self.processes[key].stdout.read().decode().strip()
                    if out:
                        print(out)
        return num_active_processes

    def wait_for_available_process_slot(self):
        while self.get_active_processes() >= self.max_parallel_processes:
            time.sleep(1)

    def wait_for_all_processes_to_complete(self):
        while self.get_active_processes() != 0:
            time.sleep(1)

    def init(self, *args, **kwargs):
        self._init(*args, **kwargs)

    def process(self, *args, **kwargs):
        if self.is_async:
            key = self._get_process_key(*args, **kwargs)
            assert key not in self.processes
            self.processes[key] = self._run_async(*args, **kwargs)
            self.wait_for_available_process_slot()
        else:
            key = self._get_process_key(*args, **kwargs)
            self._handle_process_response(key, self._run_sync(*args, **kwargs))

    def finalize(self):
        if self.is_async:
            self.wait_for_all_processes_to_complete()
            if len(self._async_processes_errored) > 0:
                raise Exception("Encountered errors in the following process keys: {}".format(", ".join(self._async_processes_errored)))
