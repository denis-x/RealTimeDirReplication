import sys
import time
import os
import stat
import shutil
import logging
from watchdog.observers import Observer
from watchdog.events import RegexMatchingEventHandler


# FileSystemEventHandler


class MyEventHandler(RegexMatchingEventHandler):

    def __init__(self, **kwargs):
        super().__init__()
        # self.target = kwargs.get('dst_path', None)
        self._dst_path = kwargs.get('dst_path', None)
        self._src_path = kwargs.get('src_path', None)
        if not os.path.isdir(self._src_path):
            logging.critical('Source directory %s does not exist!' % self._src_path)
        if not os.path.isdir(self._dst_path):
            logging.warning('Destination directory %s does not exist' % self._dst_path)
            logging.info('Create directory %s' % self._dst_path)
            try:
                os.makedirs(self._dst_path)
            except Exception as e:
                logging.critical(str(e))

    def catch_all_handler(self, event):
        # logging.debug(event)
        return

    def on_moved(self, event):
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
        print('creat')
        print(event)
        self.catch_all_handler(event)

    def on_deleted(self, event):
        # Construct path to file/directory being deleted in destination folder
        del_path = os.path.join(self._dst_path, os.path.relpath(event.src_path, self._src_path))
        logging.info('Delete %s' % del_path)
        try:
            if os.path.isfile(event.src_path):
                if os.path.isfile(del_path):
                    try:
                        try:
                            os.remove(del_path)
                        except PermissionError as e:
                            os.chmod(del_path, stat.S_IWRITE)
                            os.remove(del_path)
                    except OSError as e:
                        logging.error(str(e))
                else:
                    logging.warning('File does not exist or has been already deleted')
            elif os.path.isdir(event.src_path):
                if os.path.isdir(del_path):
                    try:
                        shutil.rmtree(del_path, True)
                    except shutil.Error as e:
                        logging.error(str(e))
                else:
                    logging.warning('Directory does not exist or has been already deleted')
        except Exception as e:  # of any use ?
            logging.error(str(e))

    def on_modified(self, event):
        if not event.is_directory:
            # Construct path to file/directory being modified in destination folder
            path_to_modified = os.path.join(self._dst_path, os.path.relpath(event.src_path, self._src_path))
            logging.info('Copy %s->%s' % (event.src_path, path_to_modified))
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    # path = sys.argv[1] if len(sys.argv) > 1 else '.'
    path = '/home/denis/dirsync_test/B'
    # event_handler = MyEventHandler(patterns=['*.py', '*.pyc'],
    #                                ignore_patterns=['version.py'],
    #                                ignore_directories=True)
    event_handler = MyEventHandler(
        src_path='/home/denis/dirsync_test/B',
        dst_path='/home/denis/dirsync_test/C',
        ignore_regexes=[r'.*\.git\b']
    )
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
    finally:
        observer.stop()
        observer.join()
