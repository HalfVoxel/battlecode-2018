from subprocess import PIPE
import subprocess
import os
import threading


class FakeContainer:
    ''' Fakes a container with the same API as the docker client '''

    def __init__(self, working_dir: str, env, command: str):
        self._working_dir = working_dir
        self._env = env
        self._command = command
        self._process = None
        self.status = "not started"
        self._streaming = False

        if not os.path.isdir(self._working_dir):
            print("The given bot directory path '" + self._working_dir + "' must be a directory")

        if not os.path.isfile(os.path.join(self._working_dir, "run.sh")):
            print("You should have an executable file called run.sh in the bot directory '" + self._working_dir + "'")

    def start(self):
        cwd = os.path.abspath(self._working_dir)
        # Ensure all environment variables are strings
        env = {str(k): str(v) for k, v in self._env.items()}
        self._process = subprocess.Popen(self._command, cwd=cwd, stdout=PIPE, stderr=PIPE, shell=True, env=env)

    def pause(self):
        self.process.suspend()
        self.status = "paused"

    def unpause(self):
        self.process.resume()
        self.status = "running"

    def stream_logs(self, stdout, stderr, line_action):
        assert not self._streaming
        assert self._process is not None, "Container must be started"
        self._streaming = True
        if stdout:
            threading.Thread(target=self._stream_logs, args=(self._process.stdout, line_action)).start()
        if stderr:
            threading.Thread(target=self._stream_logs, args=(self._process.stderr, line_action)).start()

    def _stream_logs(self, stream, line_action):
        for line in stream:
            line_action(line)
        print("Log is finished")

    def remove(self, force=False):
        if self._process is not None:
            print("Killing bot")
            self._process.kill()
            self._process.stdout.close()
            self._process.stderr.close()
            self._process = None

    def stats(decode, stream):
        pass

    def __del__(self):
        self.remove()
