import os
import stat
import shutil
import logging
from watchdog.events import RegexMatchingEventHandler

logger = logging.getLogger(__name__)


class FileSystemEventHandler(RegexMatchingEventHandler):

    def __init__(self, **kwargs):
        self._origin_path = kwargs.pop('origin_path', None)
        self._replica_path = kwargs.pop('replica_path', None)
        self._last_moved_dir = None
        self._last_deleted_dir = None
        super().__init__(**kwargs)
        if not os.path.isdir(self._origin_path):
            logger.critical('Origin directory %s does not exist!' % self._origin_path)
        if not os.path.isdir(self._replica_path):
            logger.warning('Replica directory %s does not exist' % self._replica_path)
            logger.info('Create directory %s' % self._replica_path)
            try:
                os.makedirs(self._replica_path)
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
        """Directory creation event (ignoring for files, as file creation is always followed by modification event).
        Similar relative path directory is to be created at replica."""
        self._last_moved_dir = None
        self._last_deleted_dir = None
        if event.is_directory:
            # Construct path to directory being created in replica folder
            path_to_created = os.path.join(self._replica_path, os.path.relpath(event.src_path, self._origin_path))
            logger.info('Create %s' % path_to_created)
            if os.path.exists(event.src_path):
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
