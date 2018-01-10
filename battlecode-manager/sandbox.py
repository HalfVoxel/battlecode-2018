from pathlib import Path
from threading import Timer
import threading
from container import FakeContainer
from tqdm import tqdm
import os
import shutil
import time
import socket
import fcntl
import struct
import string
import random
import io
import zipfile
from distutils.dir_util import copy_tree
import psutil
import subprocess
from pathlib import Path
try:
    # Unused in this file?
    import boto3
except:
    pass


bindings_path = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../bindings")
target_path = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../target")
def delete_folder(path):
    try:
        for sub in path.iterdir():
            if sub.is_dir():
                delete_folder(sub)
            else:
                sub.unlink()
        path.rmdir()
    except Exception as e:
        pass


def random_key(length):
    return ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(length)])


class Sandbox:
    '''
    Creates a sandbox with the code for a player.
    If the docker_instance parameter is None then sandboxing will not be performed.
    '''

    def __init__(self, socket_file, docker_instance, local_dir=None, s3_bucket=None, s3_key=None,
                 player_key="", working_dir="working_dir/",
                 player_mem_limit=256, player_cpu=20):
        self.player_mem_limit = str(player_mem_limit) + 'mb'
        self.player_key = player_key
        self.docker = docker_instance
        self.socket_file = socket_file
        if working_dir[-1] != "/":
            working_dir += "/"

        self.working_dir = Path(working_dir + random_key(20) + "/")
        self.working_dir.mkdir(parents=True, exist_ok=True)

        if s3_bucket:
            self.extract_code(s3_bucket, s3_key)
        elif local_dir:
            copy_tree(local_dir, str(self.working_dir.absolute()))
        else:
            raise ValueError("Must provide either S3 key and bucket or local directory for code.")

        if self.docker is None:
            # TODO: How is this done in docker and can this be simplified?
            self.copy_bindings()
        self.dos2unix()

    def copy_bindings(self):
        print("Copying Bindings...")
        copy_tree(bindings_path + "/c/include", str(self.working_dir))
        shutil.copyfile(target_path + "/release/libbattlecode.a", str(self.working_dir) + "/libbattlecode.a")

    def dos2unix(self):
        pathlist = list(Path(str(self.working_dir.absolute())).glob("**/*.sh"))
        pathlist += list(Path(str(self.working_dir.absolute())).glob("**/*.py"))

        for path in pathlist:
            with open(str(path), 'r') as f:
                x = f.read()
            with open(str(path), 'w') as f:
                f.write(x.replace('\r\n', '\n'))

    def stream_logs(self, stdout=True, stderr=True, line_action=lambda line: print(line.decode())):
        if type(self.container) is FakeContainer:
            # Custom support for streaming logs!
            self.container.stream_logs(stdout, stderr, line_action)
        else:
            def _stream_logs(container, stdout, stderr, line_action):
                for line in container.logs(stdout=stdout, stderr=stderr, stream=True):
                    line_action(line)
            threading.Thread(target=_stream_logs, args=(self.container, stdout, stderr, line_action)).start()

    def extract_code(self, bucket, key):
        obj = bucket.Object(key)
        with io.BytesIO(obj.get()["Body"].read()) as tf:
            tf.seek(0)
            with zipfile.ZipFile(tf, mode='r') as zipf:
                zipf.extractall(path=str(self.working_dir.absolute()))

    def start(self):
        use_docker = self.docker is not None
        command = 'sh run.sh'
        if use_docker:
            env = {'PLAYER_KEY': self.player_key, 'SOCKET_FILE': '/tmp/battlecode-socket', 'RUST_BACKTRACE': 1}
            volumes = {str(self.working_dir.absolute()): {'bind': '/code', 'mode': 'rw'}, self.socket_file: {'bind': '/tmp/battlecode-socket', 'mode': 'rw'}}

            working_dir = '/code'
            self.container = self.docker.containers.run('battlebaby', command,
                                                        privileged=False, detach=True, stdout=True, stderr=True,
                                                        volumes=volumes, working_dir=working_dir, environment=env,
                                                        mem_limit=self.player_mem_limit, memswap_limit=self.player_mem_limit,
                                                        network_disabled=True)
        else:
            env = {'PLAYER_KEY': self.player_key, 'SOCKET_FILE': self.socket_file, 'RUST_BACKTRACE': 1, 'PYTHONPATH': os.environ['PYTHONPATH']}
            self.container = FakeContainer(working_dir=str(self.working_dir.absolute()), env=env, command=command)
            self.container.start()

    def pause(self):
        if self.container.status == 'running':
            self.container.pause()
        else:
            raise RuntimeError('You attempted to pause a non-running container.')

    def unpause(self, timeout=None):
        if self.container.status == 'paused':
            self.container.unpause()
            Timer(timeout, self.pause).start()
        else:
            raise RuntimeError('You attempted to unpause a container that was not paused.')

    def destroy(self):
        try:
            self.container.remove(force=True)
        except Exception as e:
            pass

        delete_folder(self.working_dir)

    def docker_stats(self, stream=False):
        return self.container.stats(decode=True, stream=stream)

    def __del__(self):
        self.destroy()
