import ijson
import sys


class BaseVisitor:
    def __init__(self):
        self._invocation = None
        self._store_next_param_in = None

    def matches(self, command):
        return False

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
    COMMAND_PREFIXES = ['clang', 'gcc', 'g++']

    def __init__(self):
        super().__init__()

    def matches(self, command):
        return any(command.startswith(cmd) for cmd in self.COMMAND_PREFIXES)

    def derive_invocation_from(self, param):
        # refer to: https://gcc.gnu.org/onlinedocs/gcc/Preprocessor-Options.html#Preprocessor-Options
        #   TODO: support -U
        if param in ["-D"]:
            self._store_next_param_in = self._invocation.defines
        # refer to: https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html
        #   TODO: support -iquote, -idirafter, -isysroot,
        #   TODO: support -iprefix, -iwithprefix*
        elif param in ["-I", "-isystem"]:
            self._store_next_param_in = self._invocation.includes
        else:
            super().derive_invocation_from(param)


TOKEN_VISITORS = [
    GccCompatibleVisitor()
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

    return tokens


class JsonDbEntry:
    def __init__(self):
        self.directory = None
        self.command = None
        self.file = None
        self._tokens = []
        self.invocation = None

    def __repr__(self):
        return "%s:\n    in        %s\n%s" % (
            self.file, self.directory, self.invocation)

    def store(self, name, value):
        try:
            setattr(self, name, value)
        except AttributeError:
            pass  # just eat any unsupported name

    def finish(self):
        self._tokens = tokenize_command(self.command)

        for p in TOKEN_VISITORS:
            if p.matches(self._tokens[0]):
                p.start_invocation()

                for token in self._tokens[1:]:
                    p.derive_invocation_from(token)

                self.invocation = p.end_invocation()


class Lint4JsonCompilationDb:
    def __init__(self, compilation_db):
        self._current_item = None
        self.items = []

        self.read_json_db(compilation_db)

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

    def forward(self, prefix, event, value):
        parts = prefix.split('.')

        if len(parts) > 1:
            self._current_item.store(parts[1], value)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser('lint 4 JSON compilation database')
    parser.add_argument('--compilation-db', type=str, required=True)
    parser.add_argument('--lint-path', type=str, required=True)
    parser.add_argument('--lint-binary', type=str, required=True)

    args = parser.parse_args()

    db = Lint4JsonCompilationDb(args.compilation_db)
    print(db)

