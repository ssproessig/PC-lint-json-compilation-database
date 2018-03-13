from __future__ import print_function
import os
import re
import subprocess
import sys

from multiprocessing import cpu_count
from threading import Lock, Thread
from queue import Queue     # works for Python 2 and 3 if "future" is installed

import ijson


class BaseVisitor:
    def __init__(self):
        self._invocation = None
        self._store_next_param_in = None

    def matches(self, command):
        raise NotImplementedError("BaseVisitor can not match")

    def start_invocation(self):
        self._invocation = Invocation()

    def end_invocation(self):
        return self._invocation

    def derive_invocation_from(self, param):
        if self._store_next_param_in is not None:
            self._store_next_param_in.append(param)
            self._store_next_param_in = None


class Invocation:
    def __init__(self):
        self.includes = []
        self.defines = []

    def __repr__(self):
        includes = "\t".join(self.includes)
        defines = "\t".join(self.defines)

        return "    includes: %s,\n    defines:  %s" % (includes, defines)


class GccCompatibleVisitor(BaseVisitor):
    COMMAND_PREFIXES = ['clang', 'clang++', 'gcc', 'cc', 'g++', 'c++', 'cpp']

    def __init__(self):
        BaseVisitor.__init__(self)

    def matches(self, command):
        _, executable = os.path.split(command)
        return any(cmd in command for cmd in self.COMMAND_PREFIXES)

    def derive_invocation_from(self, param):
        # refer to: http://bit.ly/2GbmHfo
        #   TODO: support -U
        if param in ["-D"]:
            self._store_next_param_in = self._invocation.defines
        elif param.startswith('-D'):
            self._invocation.defines.append(param[2:])
        # refer to: https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html
        #   TODO: support -iquote, -idirafter, -isysroot,
        #   TODO: support -iprefix, -iwithprefix*
        elif param in ["-I", "-isystem"]:
            self._store_next_param_in = self._invocation.includes
        elif param.startswith('-I'):
            self._invocation.includes.append(param[2:])
        else:
            BaseVisitor.derive_invocation_from(self, param)


class MSVCCompatibleVisitor(BaseVisitor):
    COMPILER = ["cl.exe"]

    def __init__(self):
        BaseVisitor.__init__(self)

    def matches(self, command):
        _, executable = os.path.split(command)
        return executable in self.COMPILER

    def derive_invocation_from(self, param):
        if param.startswith('/I') or param.startswith('-I'):
            self._store_next_param_in = self._invocation.includes
        elif param.startswith('/D') or param.startswith('-D'):
            self._store_next_param_in = self._invocation.defines

        if self._store_next_param_in is not None:
            self._store_next_param_in.append(param[2:])
            self._store_next_param_in = None


TOKEN_VISITORS = [
    GccCompatibleVisitor(),
    MSVCCompatibleVisitor()
]


def tokenize_command(command):
    tokens = []

    current_token = ""
    in_string = False

    for i in command:
        if i == "\"":
            in_string = not in_string
        elif i == " " and not in_string:
            if current_token != "":
                tokens.append(current_token)
                current_token = ""
        else:
            current_token += i

    tokens.append(current_token)
    return tokens


class JsonDbEntry:
    def __init__(self):
        self.directory = None
        self.command = None
        self.file = None
        self.arguments = []

        self._tokens = []

        self.invocation = None

    def __repr__(self):
        return "%s:\n    in        %s\n%s" % (
            self.file, self.directory, self.invocation)

    def store(self, name, value):
        try:
            if value is None:
                return

            a = getattr(self, name)
            if isinstance(a, list):
                a.append(value)
            else:
                a = value
            setattr(self, name, a)
        except AttributeError:
            pass  # just eat any unsupported name

    def finish(self):
        if self.command:
            self._tokens = tokenize_command(self.command)

        if len(self.arguments) > 0:
            self._tokens = self.arguments

        for p in TOKEN_VISITORS:
            assert len(self._tokens) > 0, "Need to have at least one token"

            if p.matches(self._tokens[0]):
                p.start_invocation()

                for token in self._tokens[1:]:
                    p.derive_invocation_from(token)

                self.invocation = p.end_invocation()

                continue


class Lint4JsonCompilationDb:
    def __init__(self, compilation_db, include_only=set(), exclude_all=set()):
        self._current_item = None
        self.items = []

        self.read_json_db(compilation_db)

        for regexp in include_only:
            r = re.compile(regexp)
            self.items[:] = [i for i in self.items if r.match(i.file)]

        for regexp in exclude_all:
            r = re.compile(regexp)
            self.items[:] = [i for i in self.items if not r.match(i.file)]

    def read_json_db(self, fn):
        with open(fn, 'r') as f:
            for prefix, event, value in ijson.parse(f):
                if prefix == "item":
                    if event == "start_map":
                        self.start_item()
                    elif event == "end_map":
                        self.end_item()
                else:
                    self.forward(prefix, event, value)

    def start_item(self):
        self._current_item = JsonDbEntry()

    def end_item(self):
        self._current_item.finish()
        self.items.append(self._current_item)
        self._current_item = None

    def forward(self, prefix, _, value):
        parts = prefix.split('.')

        if len(parts) > 1:
            self._current_item.store(parts[1], value)


class LintExecutor:
    def __init__(self, lint_path, lint_binary, other_args):
        self.args = [
            os.path.join(lint_path, lint_binary),
            '-b',
            '-i"%s/lnt"' % lint_path
        ]
        self.args.extend(other_args)

    def execute(self, item_to_process):
        inv = item_to_process.invocation

        arguments = self.args[:]
        arguments.extend('-d' + d for d in inv.defines)
        arguments.extend('-i"%s"' % i for i in inv.includes)
        arguments.append(item_to_process.file)

        if not os.path.exists(item_to_process.directory):
            os.makedirs(item_to_process.directory)

        proc = subprocess.Popen(
            arguments, cwd=item_to_process.directory,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0].decode()

        with Lock():
            print(stdout)


# using multiprocessing.dummy.ThreadPool does not allow to Ctrl+C running lint
# solution - taken from: https://www.metachris.com/2016/04/python-threadpool/
class Worker(Thread):
    def __init__(self, tasks):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            func, _args, kwargs = self.tasks.get()
            try:
                func(*_args, **kwargs)
            except Exception as e:
                print(e, file=sys.stderr)
            finally:
                self.tasks.task_done()


class ThreadPool:
    def __init__(self, num_threads):
        self.tasks = Queue(num_threads)
        for _ in range(num_threads):
            Worker(self.tasks)

    def add_task(self, func, *_args, **kwargs):
        self.tasks.put((func, _args, kwargs))

    def map(self, func, args_list):
        for _args in args_list:
            self.add_task(func, _args)

    def wait_completion(self):
        self.tasks.join()


# noinspection PyMethodMayBeStatic
class ExecuteLintForEachFile:
    def execute_with(self, args, json_db):
        lint = LintExecutor(args.lint_path, args.lint_binary, args.args)

        pool = ThreadPool(args.jobs)
        try:
            pool.map(lambda item: lint.execute(item), json_db.items)
            pool.wait_completion()
        except KeyboardInterrupt:
            pass


EXEC_MODES = {
    "each": ExecuteLintForEachFile(),
}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser('lint 4 JSON compilation database')
    parser.add_argument('--compilation-db', type=str, required=True)
    parser.add_argument('--lint-path', type=str, required=True)
    parser.add_argument('--lint-binary', type=str, required=True)
    parser.add_argument('--jobs', type=int, default=cpu_count())
    parser.add_argument('--include-only', action='append', default=[])
    parser.add_argument('--exclude-all', action='append', default=[])
    parser.add_argument('--exec-mode', type=str, default='each')
    parser.add_argument('args', nargs='*')

    args = parser.parse_args()

    if args.exec_mode not in EXEC_MODES:
        print("You must select a supported mode (%s)!" % ",".join(EXEC_MODES),
              file=sys.stderr)
        sys.exit(1)

    db = Lint4JsonCompilationDb(args.compilation_db,
                                args.include_only, args.exclude_all)

    EXEC_MODES[args.exec_mode].execute_with(args, db)
