# PC-lint (plus) invoker from JSON compilation databases

## Big picture

To check existing codebases with _PC-lint (plus)_ one has to:

- (according to manual) prepare a local PC-lint setup
    - creating a `lin.bat` or `lin.sh` that invokes _PC-lint (plus)_
    - create a `std.lnt` that includes `co.lnt` and `options.lnt`
    - create a `co.lnt` that sets up the compiler being used
    - create an `options.lnt` that sets up the output format and suppressions to use
- invoke `lint` with all _include paths_ and _defines_ per _compilation-unit_.

In order to integrate with existing build chains this tool can be used to execute _PC-lint_ using the build job's _JSON compilation database_.

## Usage
Invoke `lint4jsondb.py` 

```
W:\> lint4jsondb.py --compilation-db commands.json --lint-path D:\pclp --lint-binary pclp64.exe --jobs 6 -- std.lnt
```

where 

- `--compilation-db` points to your build system's JSON compilation database
- `--lint-path` points to you PC-lint root path (that contains the binaries and the `lnt` directory)
- `--lint-binary` names the PC-lint binary you want to execute (either `pclp32`, `pclp64` or `lint-nt`)
- `--jobs` is the number of parallel PC-lint jobs to spawn (defaults to _number of CPU core_)
- `--` and everything after it will be passed to the PC-lint binary; use it to point to your `std.lnt`

Optionally you can control which files of the overall JSON compilation database SHALL be processed using

- `--include-only <regexp>` will include only those files whose full file-path matches `<regexp>`
- `--exclude-all <regexp>` will additionally exclude all those files whose full file-path matches `<regexp>`


## Further notes
- might work with _FlexeLint_ as well (I don't have one to test with)


## Prerequisites
- Python >= 2.7
- Package `ijson` (for parsing JSON compilation databases on the fly)
- Package `mock` (mocking calls, since Python 3.3 shipped with it)


## JSON compilation database

The format specification for JSON compilation databases is available from [LLVM](https://clang.llvm.org/docs/JSONCompilationDatabase.html).

### ...with CMake

Set `CMAKE_EXPORT_COMPILE_COMMANDS` to `ON` - or just pass `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` when invoking `cmake`.

For more information refer to the [CMake manual](https://cmake.org/cmake/help/latest/variable/CMAKE_EXPORT_COMPILE_COMMANDS.html).


### ...with make-based projects

Use __Bear__, see [Bear on github](https://github.com/rizsotto/Bear).


### ...with qbs

Run `qbs` in `generate` mode and use the `clangdb` generator

```
$ > qbs generate -g clangdb
```

Refer to [qbs manual on generators](https://doc.qt.io/qbs/generators.html)
