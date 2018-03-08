import sys


class Lint4JsonCompilationDb:
    def __init__(self):
        pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser('lint 4 JSON compilation database')
    parser.add_argument('--compilation-db', type=str, required=True)
    parser.add_argument('--lint-path', type=str, required=True)
    parser.add_argument('--lint-binary', type=str, required=True)

    args = parser.parse_args()
    print(args)
