# RealTimeDirectoryReplication

Command line utility to replicate a content of origin (source) directory into mirror (destination) directory in real time.
At the first run content is one-side, from the origin to the mirror, synchronized between directories.
Than, origing directory is monitored for any change (e.g. file add, remove or change), which is immediately reflected in the mirror.

> Attention: Content of mirror directory is purged for files different to origin.

This utility was created to support use case, when versioned source code is managed on Windows machine, while is executed on Linux.
So the main goal is to maintain always up-to-date source code's mirror on Linux's disk mounted by SMB.

```
  >>>python -m dirrepl --help

  usage: __main__.py [-h] [-o PATH] [-m PATH] [-c] [-s] [-i IGNORE_PATTERN] [-d] [-l PATH]

  Command line utility to replicate a content of origin directory in mirror directory in real time.
  Pattern can be additionally provided to exclude undesired files and directories from being replicated.

  optional arguments:
    -h, --help            show this help message and exit
    -o PATH, --origin PATH
                          Path to origin directory, content of which is to be replicated in mirror directory.
    -m PATH, --mirror PATH
                          Path to mirror directory, content of which is to be replicated from origin directory.
    -c, --compare         Just compare origin and mirror directories, without further action.
    -s, --sync            Just synchronise mirror directory with origin one, without further watching for changes.
    -i IGNORE_PATTERN, --ignore IGNORE_PATTERN
                          Regex pattern to exclude file/directories from replication.
    -d, --debug           Enable DEBUG messages in log.
    -l PATH, --log PATH   Path to log file.
```

> Functionallity of this program is based on dirsync and watchdog.

> How to install: pip install  git+https://github.com/denis-x/RealTimeDirReplication.git
