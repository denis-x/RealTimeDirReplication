from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

spec = spec_from_loader("dirsync",
                        SourceFileLoader("dirsync", r"C:\Users\nxa14730\PycharmProjects\dirsync\dirsync\__init__.py"))
mod = module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.__file__)

import argparse
import re
import time
import os
import stat
import shutil
import logging

from watchdog.observers import Observer
from watchdog.events import RegexMatchingEventHandler
from dirsync.syncer import Syncer as DirSyncSyncer
from dirsync.syncer import DCMP

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


class Syncer(DirSyncSyncer):

    def _compare(self, dir1, dir2):
        """FIX: Compare contents of two directories """

        left = set()
        right = set()

        self._numdirs += 1

        excl_patterns = set(self._exclude).union(self._ignore)

        for cwd, dirs, files in os.walk(dir1):
            self._numdirs += len(dirs)
            for f in dirs + files:
                path = os.path.relpath(os.path.join(cwd, f), dir1)
                re_path = path.replace('\\', '/')
                if self._only:
                    for pattern in self._only:
                        if re.match(pattern, re_path):
                            # go to exclude and ignore filtering
                            break
                    else:
                        # next item, this one does not match any pattern
                        # in the _only list
                        continue

                add_path = False
                for pattern in self._include:
                    if re.match(pattern, re_path):
                        add_path = True
                        break
                else:
                    # path was not in includes
                    # test if it is in excludes
                    for pattern in excl_patterns:
                        if re.match(pattern, re_path):
                            # path is in excludes, do not add it
                            break
                    else:
                        # path was not in excludes
                        # it should be added
                        add_path = True

                if add_path:
                    left.add(path)
                    # Code retired below, because it adds all sub-directories to the left,
                    # which creates difference between identical dir1 and dir2
                    # anc_dirs = re_path[:-1].split('/')
                    # anc_dirs_path = ''
                    # for ad in anc_dirs[1:]:
                    #     anc_dirs_path = os.path.join(anc_dirs_path, ad)
                    #     left.add(anc_dirs_path)

        for cwd, dirs, files in os.walk(dir2):
            for f in dirs + files:
                path = os.path.relpath(os.path.join(cwd, f), dir2)
                re_path = path.replace('\\', '/')
                for pattern in self._ignore:
                    if re.match(pattern, re_path):
                        if f in dirs:
                            dirs.remove(f)
                        break
                else:
                    right.add(path)
                    # no need to add the parent dirs here,
                    # as there is no _only pattern detection
                    if f in dirs and path not in left:
                        self._numdirs += 1

        common = left.intersection(right)
        left.difference_update(common)
        right.difference_update(common)

        return DCMP(left, right, common)


class FileSystemEventHandler(RegexMatchingEventHandler):

    def __init__(self, **kwargs):
        self._origin_path = kwargs.pop('origin_path', None)
        self._replica_path = kwargs.pop('replica_path', None)
        self._last_moved_dir = None
        self._last_deleted_dir = None
        super().__init__(**kwargs)
        try:
            if not os.path.isdir(self._origin_path):
                logger.critical('Origin directory %s does not exist!' % self._origin_path)
            if not os.path.isdir(self._replica_path):
                logger.warning('Replica directory %s does not exist' % self._replica_path)
                logger.info('Create directory %s' % self._replica_path)
                try:
                    os.makedirs(self._replica_path)
                except Exception as e:
                    logger.critical(str(e))
        except Exception as e:
            logger.critical(str(e))

    def on_moved(self, event):
        """File/directory movement event.
        File/directory is to be moved from source to destination location at replica.
        When upper level directory has been already moved within underlying files/directories,
        movement events for them are to be ignored."""
        self._last_deleted_dir = None
        # Ignore file/dir, which has been already moved together with upper level directory
        if self._last_moved_dir is not None and event.src_path.find(self._last_moved_dir) == 0:
            logger.debug('%s has been already moved' % event.src_path)
            return
        # Memorize last moved directory, it will be reset by any other operation then file/dir movement
        if event.is_directory:
            # Append '/', because can exist directory having the same combination of chars in the beginning of its name
            self._last_moved_dir = event.src_path + r'/'
        # Construct path to source file/directory being moved in replica folder
        path_moved_from = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
        # Construct path to destination file/directory being moved in replica folder
        path_moved_to = os.path.join(self._replica_path, os.path.relpath(event.dest_path, self._origin_path))
        logger.info('Move %s->%s' % (path_moved_from, path_moved_to))
        try:
            if os.path.exists(path_moved_from):
                try:
                    shutil.move(path_moved_from, path_moved_to)
                except shutil.Error as e:
                    logger.error(str(e))
            elif os.path.exists(path_moved_to):
                if event.is_directory:
                    logger.warning('Directory does not exist in replica by source location, '
                                   'but in destination location')
                else:
                    logger.warning('File does not exist in replica by source location, '
                                   'but in destination location')
            else:
                if event.is_directory:
                    logger.error('Directory does not exist in replica either by source or destination locations')
                else:
                    logger.error('File does not exist in replica either by source or destination locations')
        except Exception as e:
            logger.error(str(e))

    def on_created(self, event):
        """File/Directory creation event.
        Directory is to be created at replica.
        File is to be copied from source locatin at origin to destination location at replica"""
        self._last_moved_dir = None
        self._last_deleted_dir = None
        # Construct path to file/directory being created in replica folder
        path_to_created = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
        logger.info('Create %s' % path_to_created)
        try:
            if event.is_directory:
                if os.path.isdir(event.src_path):
                    try:
                        if not os.path.isdir(path_to_created):
                            try:
                                os.makedirs(path_to_created)
                            except OSError as e:
                                logger.error(str(e))
                    except Exception as e:
                        logger.error(str(e))
                else:
                    logger.warning('Directory does not exist at origin')
            else:
                if os.path.isfile(event.src_path):
                    try:
                        shutil.copy2(event.src_path, path_to_created)
                    except (IOError, OSError) as e:
                        logger.error(str(e))
                else:
                    logger.warning('File does not exist at origin')
        except Exception as e:
            logger.error(str(e))

    def on_deleted(self, event):
        """File/directory deleting event.
        File/directory is to be deleted at replica.
        When upper level directory has been already deleted within underlying files/directories,
        deleting events for them are to be ignored."""
        # Ignore file/dir, which has been already deleted together with upper level directory
        if self._last_deleted_dir is not None and event.src_path.find(self._last_deleted_dir) == 0:
            logger.debug('%s has been already deleted' % event.src_path)
            return
        # Memorize last deleted directory, it will be reset by any other operation then file/dir deleting
        if event.is_directory:
            # Append '/', because can exist directory having the same combination of chars in the beginning of its name
            self._last_deleted_dir = event.src_path + r'/'
        self._last_moved_dir = None
        # Construct path to file/directory being deleted in replica folder
        path_to_deleted = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
        logger.info('Delete %s' % path_to_deleted)
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
                        logger.error(str(e))
                else:
                    logger.warning('File does not already exist at replica')
            else:
                if os.path.isdir(path_to_deleted):
                    try:
                        shutil.rmtree(path_to_deleted, True)
                    except shutil.Error as e:
                        logger.error(str(e))
                else:
                    logger.warning('Directory does not already exist at replica')
        except Exception as e:  # of any use ?
            logger.error(str(e))

    def on_modified(self, event):
        """File modification event (ignoring for directories).
        File is to be copied from origin to replica. Directory path is to be preserved."""
        if not event.is_directory:
            self._last_moved_dir = None
            self._last_deleted_dir = None
            # Construct path to file/directory being modified in replica folder
            path_to_modified = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
            logger.info('Update %s' % path_to_modified)
            if os.path.exists(event.src_path):
                try:
                    shutil.copy2(event.src_path, path_to_modified)
                except (IOError, OSError) as e:
                    logger.error(str(e))
            else:
                logger.warning('File does not exist at origin')


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
                        default='',
                        metavar='PATH',
                        help='Path to origin directory, content of which is to be replicated in replica directory.')
    parser.add_argument('-r', '--replica',
                        dest='path_to_replica',
                        default='',
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
        # # Configure and run syncer
        # syncer = Syncer(
        #     cmd_args['path_to_origin'],
        #     cmd_args['path_to_replica'],
        #     'diff',
        #     logger=logger,
        #     exclude=[re.compile(cmd_args['ignore_pattern'])],
        #     verbose=True,
        # )
        # syncer.do_work()
        # logger.info('Directory comparision has been completed')
        # Configure and run syncer
        syncer = Syncer(
            cmd_args['path_to_origin'],
            cmd_args['path_to_replica'],
            'sync',
            logger=logger,
            exclude=[re.compile(cmd_args['ignore_pattern'])],
            purge=True,
            create=True,
            verbose=True,
        )
        syncer.do_work()
        logger.info('Directory synchronization has been completed')
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
