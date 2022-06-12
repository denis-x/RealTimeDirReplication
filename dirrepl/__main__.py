import argparse
import re
import time
import os
import logging
from watchdog.observers import Observer
from dirsync.syncer import Syncer
from .dirrepl import FileSystemEventHandler

default_ignore_regex = r'.*\.git\b|.*\.idea\b|.*\.gitignore\b'

# Define standard logger with desired formatting
logger = logging.getLogger(__name__)
_log_formatter = logging.Formatter(
    fmt='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(_log_formatter)
_log_handler.setLevel(logging.INFO)
logger.addHandler(_log_handler)
logger.setLevel(logging.DEBUG)


def cmd_args_parser():
    # --------------------------------------
    # Construct command line argument parser
    # --------------------------------------
    main_help = 'Command line utility to replicate a content of origin directory in mirror directory in real time.\n' \
                'Pattern can be additionally provided to exclude undesired files and directories from being replicated.'
    parser = argparse.ArgumentParser(description=main_help, formatter_class=argparse.RawTextHelpFormatter)
    # Export options
    parser.add_argument('-o', '--origin',
                        dest='path_to_origin',
                        default='',
                        metavar='PATH',
                        help='Path to origin directory, content of which is to be replicated in mirror directory.')
    parser.add_argument('-m', '--mirror',
                        dest='path_to_mirror',
                        default='',
                        metavar='PATH',
                        help='Path to mirror directory, content of which is to be replicated from origin directory.')
    parser.add_argument('-c', '--compare',
                        action='store_true',
                        dest='compare',
                        default=False,
                        help='Just compare origin and mirror directories, without further action.')
    parser.add_argument('-s', '--sync',
                        action='store_true',
                        dest='sync',
                        default=False,
                        help='Just synchronise mirror directory with origin one, without further watching for changes.')
    parser.add_argument('-i', '--ignore',
                        dest='ignore_pattern',
                        default=default_ignore_regex,
                        help='Regex pattern to exclude file/directories from replication.')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        dest='debug',
                        default=False,
                        help='Enable DEBUG messages in log.')
    parser.add_argument('-l', '--log',
                        default='',
                        dest='log_path',
                        metavar='PATH',
                        help='Path to log file.')

    # --------------------------------------
    # Parse command line arguments
    # --------------------------------------
    return vars(parser.parse_args())


def main():
    # Parse command line arguments
    cmd_args = cmd_args_parser()
    #
    if not cmd_args['path_to_origin'] or not cmd_args['path_to_mirror']:
        raise Exception(f"Both paths to origin and mirror directories should be provided in command line arguments")
    # Check source directory existence
    if not os.path.isdir(cmd_args['path_to_origin']):
        raise Exception(f"Origin directory '{cmd_args['path_to_origin']}' does not exist!")
    # Check mirror directory existence
    if not os.path.isdir(cmd_args['path_to_mirror']):
        raise Exception(f"Origin directory '{cmd_args['path_to_mirror']}' does not exist!")
    # Configure logger
    if cmd_args['log_path']:
        # When log to log file, configure console logger to report only errors
        _log_handler.setLevel(logging.ERROR)
        from logging.handlers import RotatingFileHandler
        file_logger = RotatingFileHandler(
            filename=cmd_args['log_path'],
            mode='w',
            maxBytes=5 * 1024 * 1024,
            backupCount=2,
            delay=0)
        file_logger.setFormatter(_log_formatter)
        file_logger.setLevel(logging.DEBUG if cmd_args['debug'] else logging.INFO)
        logger.addHandler(file_logger)
    elif cmd_args['debug']:
        _log_handler.setLevel(logging.DEBUG)
    if cmd_args['sync']:
        # Just synchronise mirror directory with origin one
        # Configure and run syncer
        syncer = Syncer(
            cmd_args['path_to_origin'],
            cmd_args['path_to_mirror'],
            'sync',
            logger=logger,
            exclude=[re.compile(cmd_args['ignore_pattern'])],
            purge=True,
            ctime=True,
            create=True,
            verbose=True,
        )
        syncer.do_work()
    elif cmd_args['compare']:
        # Just compare origin and mirror directories
        # Configure and run syncer
        syncer = Syncer(
            cmd_args['path_to_origin'],
            cmd_args['path_to_mirror'],
            'diff',
            logger=logger,
            exclude=[re.compile(cmd_args['ignore_pattern'])],
            purge=True,
            ctime=True,
            create=True,
            verbose=True,
        )
        syncer.do_work()
    else:
        # Configure event handler
        event_handler = FileSystemEventHandler(
            origin_path=cmd_args['path_to_origin'],
            replica_path=cmd_args['path_to_mirror'],
            ignore_regexes=[cmd_args['ignore_pattern']],
            case_sensitive=True
        )
        # Configure and run file system events observer
        observer = Observer()
        observer.schedule(event_handler, cmd_args['path_to_origin'], recursive=True)
        observer.start()
        try:
            # Configure and run syncer
            syncer = Syncer(
                cmd_args['path_to_origin'],
                cmd_args['path_to_mirror'],
                'sync',
                logger=logger,
                exclude=[re.compile(cmd_args['ignore_pattern'])],
                purge=True,
                ctime=True,
                create=True,
                verbose=True,
            )
            syncer.do_work()
            # Indefinite loop for observer operation
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # pass to mitigate error message
            pass
        finally:
            observer.stop()
            observer.join()


if __name__ == "__main__":
    main()
