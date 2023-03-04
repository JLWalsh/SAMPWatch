#!/usr/bin/python3

import configparser
import shutil
import subprocess
import time
from threading import Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CONFIG_FILE_NAME = '.sampwatch'

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_NAME)

    server_dir = config['server']['directory']
    watch_dir = config['watcher']['directory']

    files = config['watcher']['files'].split(',')

    return {'server_dir': server_dir, 'watch_dir': watch_dir, 'files': files}

# Taken from https://gist.github.com/walkermatt/2871026
def debounce(wait):
    """ Decorator that will postpone a functions
        execution until after wait seconds
        have elapsed since the last time it was invoked. """
    def decorator(fn):
        def debounced(*args, **kwargs):
            def call_it():
                fn(*args, **kwargs)
            try:
                debounced.t.cancel()
            except(AttributeError):
                pass
            debounced.t = Timer(wait, call_it)
            debounced.t.start()
        return debounced
    return decorator

def print_header(message):
    print(f'---------- {message} ----------')

def start_server(server_dir):
    print_header('STARTING SERVER')
    process = subprocess.Popen([f"exec {server_dir}/omp-server"], shell=True)
    print(f'SERVER STARTED ON PID {process.pid}')
    return process

@debounce(1)
def restart_server(server_process, config):
    print_header('STOPPING SERVER')
    server_process.kill()
    return start_server(config['server_dir'])

def copy_file_to_server(file, config):
    print(f'Copying {file} to {config["server_dir"]}')
    shutil.copyfile(config['watch_dir'] + '/' + file, config['server_dir'] + '/components/' + file)

def copy_all_files_to_server(config):
    files = config['files']
    for file in files:
        copy_file_to_server(file, config)

def start_file_watcher(process, config):
    event_handler = FileChangedHandler(process, config)
    observer = Observer()
    observer.schedule(event_handler, path=config['watch_dir'], recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

class FileChangedHandler(FileSystemEventHandler):
    server_process = None
    config = None

    def __init__(self, server_process, config):
        self.server_process = server_process
        self.config = config

    def on_modified(self, event):
        if event.event_type == 'modified':
            filename = event.src_path[len(self.config['watch_dir']) + 1:]

            if filename in self.config['files']:
                copy_file_to_server(filename, self.config)

                maybe_new_process = restart_server(self.server_process, self.config)
                if maybe_new_process is not None:
                    self.server_process = maybe_new_process

if __name__ == "__main__":
    config = read_config();

    copy_all_files_to_server(config)
    process = start_server(config['server_dir'])
    start_file_watcher(process, config)

