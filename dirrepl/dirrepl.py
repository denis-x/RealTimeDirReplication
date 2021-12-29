import argparse
import re
import time
import os
import stat
import shutil
import logging
from watchdog.observers import Observer
from watchdog.events import RegexMatchingEventHandler
from dirsync.syncer import Syncer


class FileSystemEventHandler(RegexMatchingEventHandler):

    def __init__(self, **kwargs):
        self._origin_path = kwargs.pop('origin_path', None)
        self._replica_path = kwargs.pop('replica_path', None)
        self._last_moved_dir = None
        self._last_deleted_dir = None
        super().__init__(**kwargs)
        if not os.path.isdir(self._origin_path):
            logging.critical('Origin directory %s does not exist!' % self._origin_path)
        if not os.path.isdir(self._replica_path):
            logging.warning('Replica directory %s does not exist' % self._replica_path)
            logging.info('Create directory %s' % self._replica_path)
            try:
                os.makedirs(self._replica_path)
            except Exception as e:
                logging.critical(str(e))

    def on_moved(self, event):
        """File/directory movement event.
        File/directory is to be moved from source to destination location at replica.
        When upper level directory has been already moved within underlying files/directories,
        movement events for them are to be ignored."""
        self._last_deleted_dir = None
        # Ignore file/dir, which has been already moved together with upper level directory
        if self._last_moved_dir is not None and event.src_path.find(self._last_moved_dir) == 0:
            logging.debug('%s has been already moved' % event.src_path)
            return
        # Memorize last moved directory, it will be reset by any other operation then file/dir movement
        if event.is_directory:
            # Append '/', because can exist directory having the same combination of chars in the beginning of its name
            self._last_moved_dir = event.src_path + r'/'
        # Construct path to source file/directory being moved in replica folder
        path_moved_from = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
        # Construct path to destination file/directory being moved in replica folder
        path_moved_to = os.path.join(self._replica_path, os.path.relpath(event.dest_path, self._origin_path))
        logging.info('Move %s->%s' % (path_moved_from, path_moved_to))
        try:
            if os.path.exists(path_moved_from):
                try:
                    shutil.move(path_moved_from, path_moved_to)
                except shutil.Error as e:
                    logging.error(str(e))
            elif os.path.exists(path_moved_to):
                if event.is_directory:
                    logging.warning('Directory does not exist in replica by source location, '
                                    'but in destination location')
                else:
                    logging.warning('File does not exist in replica by source location, '
                                    'but in destination location')
            else:
                if event.is_directory:
                    logging.error('Directory does not exist in replica either by source or destination locations')
                else:
                    logging.error('File does not exist in replica either by source or destination locations')
        except Exception as e:
            logging.error(str(e))

    def on_created(self, event):
        """Directory creation event (ignoring for files, as file creation is always followed by modification event).
        Similar relative path directory is to be created at replica."""
        self._last_moved_dir = None
        self._last_deleted_dir = None
        if event.is_directory:
            # Construct path to directory being created in replica folder
            path_to_created = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
            logging.info('Create %s' % path_to_created)
            if os.path.exists(event.src_path):
                try:
                    if not os.path.isdir(path_to_created):
                        try:
                            os.makedirs(path_to_created)
                        except OSError as e:
                            logging.error(str(e))
                except Exception as e:
                    logging.error(str(e))
            else:
                logging.warning('Directory does not exist at origin')

    def on_deleted(self, event):
        """File/directory deleting event.
        File/directory is to be deleted at replica.
        When upper level directory has been already deleted within underlying files/directories,
        deleting events for them are to be ignored."""
        # Ignore file/dir, which has been already deleted together with upper level directory
        if self._last_deleted_dir is not None and event.src_path.find(self._last_deleted_dir) == 0:
            logging.debug('%s has been already deleted' % event.src_path)
            return
        # Memorize last deleted directory, it will be reset by any other operation then file/dir deleting
        if event.is_directory:
            # Append '/', because can exist directory having the same combination of chars in the beginning of its name
            self._last_deleted_dir = event.src_path + r'/'
        self._last_moved_dir = None
        # Construct path to file/directory being deleted in replica folder
        path_to_deleted = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
        logging.info('Delete %s' % path_to_deleted)
        try:
            if not event.is_directory:
                if os.path.isfile(path_to_deleted):
                    try:
                        try:
                            os.remove(path_to_deleted)
                        except PermissionError as e:
                            os.chmod(path_to_deleted, stat.S_IWRITE)
                            os.remove(path_to_deleted)
                    except OSError as e:
                        logging.error(str(e))
                else:
                    logging.warning('File does not already exist at replica')
            else:
                if os.path.isdir(path_to_deleted):
                    try:
                        shutil.rmtree(path_to_deleted, True)
                    except shutil.Error as e:
                        logging.error(str(e))
                else:
                    logging.warning('Directory does not already exist at replica')
        except Exception as e:  # of any use ?
            logging.error(str(e))

    def on_modified(self, event):
        """File modification event (ignoring for directories).
        File is to be copied from origin to replica. Directory path is to be preserved."""
        if not event.is_directory:
            self._last_moved_dir = None
            self._last_deleted_dir = None
            # Construct path to file/directory being modified in replica folder
            path_to_modified = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
            logging.info('Update %s' % path_to_modified)
            if os.path.exists(event.src_path):
                try:
                    shutil.copy2(event.src_path, path_to_modified)
                except (IOError, OSError) as e:
                    logging.error(str(e))
            else:
                logging.warning('File does not exist at origin')


default_ignore_regex = r'.*\.git\b|.*\.idea\b|.*\.gitignore\b'


def cmd_args_parser():
    # --------------------------------------
    # Construct command line argument parser
    # --------------------------------------
    main_help = 'Command line utility to replicate in real time content of origin directory in defined ' \
                'replica directory.\nPattern can be additionally provided to exclude undesired files and ' \
                'directories from replication.'
    parser = argparse.ArgumentParser(description=main_help, formatter_class=argparse.RawTextHelpFormatter)
    # Export options
    parser.add_argument('-o', '--origin',
                        dest='path_to_origin',
                        metavar='PATH',
                        help='Path to origin directory, content of which is to be replicated in replica directory.')
    parser.add_argument('-r', '--replica',
                        dest='path_to_replica',
                        metavar='PATH',
                        help='Path to replica directory, content of which is to be replicated from origin directory.')
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
                        metavar='PATH',
                        dest='log_path',
                        help='Path to log file.')

    # --------------------------------------
    # Parse command line arguments
    # --------------------------------------
    return vars(parser.parse_args())


def main():
    # Parse command line arguments
    cmd_args = cmd_args_parser()
    # Configure logger
    if cmd_args['log_path']:
        from logging.handlers import RotatingFileHandler
        log_formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
        my_handler = RotatingFileHandler(
            cmd_args['log_path'],
            mode='a',
            maxBytes=5 * 1024 * 1024,
            backupCount=0,
            encoding=None,
            delay=0)
        my_handler.setFormatter(log_formatter)
        my_handler.setLevel(logging.DEBUG if cmd_args['debug'] else logging.INFO)
        # app_log = logging.getLogger('root')
        # app_log.setLevel(logging.INFO)
        # app_log.addHandler(my_handler)
        logging.getLogger(__name__).addHandler(my_handler)
    else:
        logging.basicConfig(level=logging.DEBUG if cmd_args['debug'] else logging.INFO,
                            format='[%(levelname)s] %(asctime)s - %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    # Configure event handler
    event_handler = FileSystemEventHandler(
        origin_path=cmd_args['path_to_origin'],
        replica_path=cmd_args['path_to_replica'],
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
            cmd_args['path_to_replica'],
            'sync',
            logger=logging,
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
    # print(cmd_args_parser())
    # main('/home/denis/dirsync_test/B', '/home/denis/dirsync_test/C')
