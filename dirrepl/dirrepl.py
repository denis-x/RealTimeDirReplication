import sys
import time
import os
import stat
import shutil
import logging
from watchdog.observers import Observer
from watchdog.events import RegexMatchingEventHandler


class FileSystemEventHandler(RegexMatchingEventHandler):

    def __init__(self, **kwargs):
        self._dst_path = kwargs.pop('dst_path', None)
        self._src_path = kwargs.pop('src_path', None)
        self._last_moved_dir = None
        super().__init__(**kwargs)
        if not os.path.isdir(self._src_path):
            logging.critical('Source directory %s does not exist!' % self._src_path)
        if not os.path.isdir(self._dst_path):
            logging.warning('Destination directory %s does not exist' % self._dst_path)
            logging.info('Create directory %s' % self._dst_path)
            try:
                os.makedirs(self._dst_path)
            except Exception as e:
                logging.critical(str(e))

    def on_moved(self, event):
        # Ignore file/dir, which has been already moved together with upper level directory
        if self._last_moved_dir is not None and event.src_path.find(self._last_moved_dir) == 0:
            logging.debug('%s has been already moved' % event.src_path)
            return
        # Memorize last moved directory, it will be reset by any other operation then file/dir movement
        if event.is_directory:
            # Append '/', because can exist directory having the same combination of chars in the beginning of its name
            self._last_moved_dir = event.src_path + r'/'
        # Construct path to origin file/directory being moved in destination folder
        path_moved_from = os.path.join(self._dst_path, os.path.relpath(event.src_path, self._src_path))
        # Construct path to target file/directory being moved in destination folder
        path_moved_to = os.path.join(self._dst_path, os.path.relpath(event.dest_path, self._src_path))
        logging.info('Move %s->%s' % (path_moved_from, path_moved_to))
        try:
            if os.path.exists(path_moved_from):
                try:
                    shutil.move(path_moved_from, path_moved_to)
                except shutil.Error as e:
                    logging.error(str(e))
            elif os.path.exists(path_moved_to):
                logging.warning('Origin does not exist or has been already deleted')
            else:
                logging.error('Neither origin nor target exists')
        except Exception as e:
            logging.error(str(e))

    def on_created(self, event):
        self._last_moved_dir = None
        # Perform only for directories, as file creation is always followed by modification event
        if event.is_directory:
            # Construct path to directory being created in destination folder
            path_to_created = os.path.join(self._dst_path, os.path.relpath(event.src_path, self._src_path))
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
                logging.warning('Source directory does not exist or has been already deleted')

    def on_deleted(self, event):
        self._last_moved_dir = None
        # Construct path to file/directory being deleted in destination folder
        path_to_deleted = os.path.join(self._dst_path, os.path.relpath(event.src_path, self._src_path))
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
                    logging.warning('File does not exist or has been already deleted')
            else:
                if os.path.isdir(path_to_deleted):
                    try:
                        shutil.rmtree(path_to_deleted, True)
                    except shutil.Error as e:
                        logging.error(str(e))
                else:
                    logging.warning('Directory does not exist or has been already deleted')
        except Exception as e:  # of any use ?
            logging.error(str(e))

    def on_modified(self, event):
        if not event.is_directory:
            self._last_moved_dir = None
            # Construct path to file/directory being modified in destination folder
            path_to_modified = os.path.join(self._dst_path, os.path.relpath(event.src_path, self._src_path))
            logging.info('Modify %s->%s' % (event.src_path, path_to_modified))
            if os.path.exists(event.src_path):
                try:
                    if not os.path.exists(path_to_modified):
                        # if self._forcecopy:
                        #     # 1911 = 0o777
                        #     os.chmod(os.path.dirname(dir2_root), 1911)
                        try:
                            os.makedirs(path_to_modified)
                        except OSError as e:
                            logging.error(str(e))
                    # if self._forcecopy:
                    #     os.chmod(dir2, 1911)  # 1911 = 0o777
                    try:
                        if os.path.islink(event.src_path):
                            os.symlink(os.readlink(event.src_path), path_to_modified)
                        else:
                            shutil.copy2(event.src_path, path_to_modified)
                    except (IOError, OSError) as e:
                        logging.error(str(e))
                except Exception as e:
                    logging.error(str(e))
            else:
                logging.warning('Source does not exist or has been already deleted')


default_ignore_regex = r'.*\.git\b|.*\.idea\b|.*\.gitignore\b'


def main(path_to_origin, path_to_target, ignore_pattern=default_ignore_regex):
    # Configure logger
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    # Configure event handler
    event_handler = FileSystemEventHandler(
        src_path=path_to_origin,
        dst_path=path_to_target,
        ignore_regexes=[ignore_pattern],
        case_sensitive=True
    )
    # Configure and run file system events observer
    observer = Observer()
    observer.schedule(event_handler, path_to_origin, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main('/home/denis/dirsync_test/B', '/home/denis/dirsync_test/C')
