import ijson
import sys


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

    def store(self, name, value):
        try:
            setattr(self, name, value)
        except AttributeError:
            pass  # just eat any unsupported name

    def finish(self):
        self._tokens = tokenize_command(self.command)


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

