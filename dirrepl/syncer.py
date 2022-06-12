import os
import re
from dirsync.syncer import DCMP
from dirsync.syncer import Syncer as BaseSyncer


class Syncer(BaseSyncer):
    def _diff(self, dir1, dir2):
        self._dcmp = self._compare(dir1, dir2)
        if not self._dcmp.left_only and not self._dcmp.right_only:
            self.log('Origin and mirror directories match by content each other!')
        elif not self._dcmp.common:
            self.log('No common files or sub-directories!')
            if self._dcmp.right_only:
                self.log('Files, which only exist at mirror %s' % dir2)
                for x in sorted(self._dcmp.right_only):
                    self.log('<< %s' % x)
        else:
            if self._dcmp.left_only:
                self.log('Files, which only exist at origin %s' % dir1)
                for x in sorted(self._dcmp.left_only):
                    self.log('>> %s' % x)
                self.log('')
            if self._dcmp.right_only:
                self.log('Files, which only exist at mirror %s' % dir2)
                for x in sorted(self._dcmp.right_only):
                    self.log('<< %s' % x)

    # Local fix, before new version of dirsync will be issued with proper fix
    def _compare(self, dir1, dir2):
        """ Compare contents of two directories """

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
                    # anc_dirs = re_path.split('/')
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
