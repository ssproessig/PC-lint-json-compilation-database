import os
import tempfile
import unittest

import ijson
import mock

from lint4jsondb import \
    Lint4JsonCompilationDb, LintExecutor, \
    JsonDbEntry, Invocation, BaseVisitor


class Lint4JsonCompilationDbUnitTest(unittest.TestCase):
    def setUp(self):
        self._json_tested = None

    def tearDown(self):
        if self._json_tested is not None and os.path.exists(self._json_tested):
            os.remove(self._json_tested)

    def __create_temp_json(self, content):
        with tempfile.TemporaryFile('wb', delete=False) as f:
            self._json_tested = f.name
            f.write(content)

    def test_00_coverage_for_repr(self):
        e = JsonDbEntry()
        e.file = "<file>"
        e.directory = "<directory>"
        e.invocation = Invocation()
        e.invocation.includes = ['i1', 'i2']
        e.invocation.defines = ['d1', 'd2']

        as_string = str(e)

        self.assertIn("<file>:", as_string)
        self.assertIn("<directory>", as_string)
        self.assertIn("includes: i1\ti2", as_string)
        self.assertIn("defines:  d1\td2", as_string)

    def test_01_json_db_does_not_exist(self):
        with self.assertRaises(Exception) as cm:
            Lint4JsonCompilationDb('unknown.json')

        self.assertIn("unknown.json", str(cm.exception))

    def test_02a_broken_json_is_reported(self):
        self.__create_temp_json(b'broken')

        with self.assertRaises(ijson.JSONError):
            Lint4JsonCompilationDb(self._json_tested)

    def test_02b_not_having_an_array_does_not_create_an_entry(self):
        self.__create_temp_json(b'{}')

        db = Lint4JsonCompilationDb(self._json_tested)
        self.assertEqual(len(db.items), 0)

    def test_02c_having_an_empty_array_does_not_create_an_entry(self):
        self.__create_temp_json(b'[]')

        db = Lint4JsonCompilationDb(self._json_tested)
        self.assertEqual(len(db.items), 0)

    def test_02d_having_an_incomplete_object_fails_for_missing_token(self):
        self.__create_temp_json(b'[{"key":"value"}]')

        with self.assertRaises(AssertionError) as cm:
            Lint4JsonCompilationDb(self._json_tested)

        self.assertIn("Need to have at least one token", str(cm.exception))

    def test_03a_source_trail_style_json_db(self):
        self.__create_temp_json(
            b'[{'
            b'"directory": "F:/VS2017/working",'
            b'"command": "clang-tool -fms-extensions'
            b' -isystem \\"F:/VS2017/working/CMake\\"'
            b' -isystem \\"C:/Qt/5.10.0/msvc2017_64/include\\"'
            b' -D _DEBUG  -D _MT  -D _DLL  -D WIN32  -D _WINDOWS", '
            b'"file": "F:/VS2017/working/mocs_compilation.cpp"}]')

        db = Lint4JsonCompilationDb(self._json_tested)

        self.assertEqual(len(db.items), 1)
        self.assertEqual(db.items[0].directory,
                         "F:/VS2017/working")
        self.assertEqual(db.items[0].file,
                         "F:/VS2017/working/mocs_compilation.cpp")
        invocation = db.items[0].invocation
        self.assertListEqual(invocation.defines,
                             ['_DEBUG', '_MT', '_DLL', 'WIN32', '_WINDOWS'])
        self.assertListEqual(invocation.includes,
                             ['F:/VS2017/working/CMake',
                              'C:/Qt/5.10.0/msvc2017_64/include'])

    def test_03b_cmake_style_json_db(self):
        self.__create_temp_json(
            b'[{'
            b'"directory": "/home/user/build/login",'
            b'"command": "/opt/clang/bin/clang++ '
            b' -DQT_CORE_LIB -DQT_GUI_LIB -DQT_NO_DEBUG -DQT_WIDGETS_LIB'
            b' -I/home/user/code/login/'
            b' -Ilogin/login_autogen/include'
            b' -isystem /opt/Qt/5.11.0/gcc_64/include'
            b' -isystem /opt/Qt/5.11.0/gcc_64/include/QtWidgets'
            b' -Weverything -fPIC -std=gnu++14'
            b' -o login/CMakeFiles/login.dir/LoginDialog.cpp.o'
            b' -c /home/user/code/login/LoginDialog.cpp",'
            b'"file": "/home/user/code/login/LoginDialog.cpp"}]')

        db = Lint4JsonCompilationDb(self._json_tested)
        self.assertEqual(len(db.items), 1)
        self.assertEqual(db.items[0].directory,
                         "/home/user/build/login")
        self.assertEqual(db.items[0].file,
                         "/home/user/code/login/LoginDialog.cpp")
        invocation = db.items[0].invocation
        self.assertListEqual(invocation.defines,
                             ['QT_CORE_LIB', 'QT_GUI_LIB',
                              'QT_NO_DEBUG', 'QT_WIDGETS_LIB'])
        self.assertListEqual(invocation.includes,
                             ['/home/user/code/login/',
                              'login/login_autogen/include',
                              '/opt/Qt/5.11.0/gcc_64/include',
                              '/opt/Qt/5.11.0/gcc_64/include/QtWidgets'
                              ])

    def test_03c_qbs_created_for_msvc_json_db(self):
        self.__create_temp_json(
            b'[{"arguments":["C:/Program Files (x86)/Microsoft Visual '
            b'Studio/2017/Professional/VC/Tools/MSVC/14.13.26128/bin/'
            b'HostX64/x64/cl.exe","/nologo","/c","/EHsc","/Od","/Zi","/MDd",'
            b'"/IC:\\\\Qt\\\\5.11.0\\\\msvc2017_64\\\\include",'
            b'"/IC:\\\\Qt\\\\5.11.0\\\\msvc2017_64\\\\include\\\\QtCore",'
            b'"/DUNICODE","/D_UNICODE","/DWIN32","/DQT_CORE_LIB",'
            b'"/DQT_GUI_LIB","/DWINVER=0x0502",'
            b'"/FoG:\\\\qzipreader\\\\default\\\\qzipreader.ffaa043c\\\\3a52ce'
            b'd4d9\\\\main.cpp.obj",'
            b'"G:\\\\qzipreader\\\\main.cpp","/TP","/FS",'
            b'"/Zm200"],'
            b'"directory":"G:/qzipreader/default/'
            b'qzipreader.ffaa043c",'
            b'"file":"G:/qzipreader/main.cpp"}]'
        )

        db = Lint4JsonCompilationDb(self._json_tested)
        self.assertEqual(len(db.items), 1)
        self.assertEqual(db.items[0].directory,
                         "G:/qzipreader/default/qzipreader.ffaa043c")
        self.assertEqual(db.items[0].file,
                         "G:/qzipreader/main.cpp")
        invocation = db.items[0].invocation
        self.assertListEqual(invocation.defines,
                             ['UNICODE', '_UNICODE', 'WIN32', 'QT_CORE_LIB',
                              'QT_GUI_LIB', 'WINVER=0x0502'])
        self.assertListEqual(invocation.includes,
                             [r'C:\Qt\5.11.0\msvc2017_64\include',
                              r'C:\Qt\5.11.0\msvc2017_64\include\QtCore'])

    def test_04_ensure_BaseVisitor_never_matches(self):
        b = BaseVisitor()

        with self.assertRaises(NotImplementedError) as cm:
            b.matches("")

        self.assertIn("BaseVisitor can not match", str(cm.exception))


class LintExecutorUnitTest(unittest.TestCase):

    @mock.patch('os.path.exists')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.call')
    def test_invocation(self, mock_call, mock_os_path_exists, mock_os_makedirs):
        mock_os_path_exists.return_value = False

        lint = LintExecutor("<lint-path>", "<lint-exe>", ["o1", "o2"])

        item_to_process = JsonDbEntry()
        item_to_process.file = "<file>"
        item_to_process.directory = "<directory>"
        item_to_process.invocation = Invocation()
        item_to_process.invocation.defines = ["d1", "d2"]
        item_to_process.invocation.includes = ["i1", "i2"]

        lint.execute(item_to_process)

        self.assertEqual(mock_os_makedirs.call_count, 1)
        self.assertEqual(mock_os_makedirs.call_args[0][0], "<directory>")

        self.assertEqual(mock_call.call_count, 1)
        args = mock_call.call_args[0][0]

        # ensure lint is executed in the build directory
        self.assertDictEqual(mock_call.call_args[1], {'cwd': '<directory>'})

        # ensure lint is called
        self.assertEqual(args.pop(0), os.path.join("<lint-path>", "<lint-exe>"))
        # ensure lint suppresses the banner line
        self.assertEqual(args.pop(0), '-b')
        # ensure lint's "lnt" directory was added
        self.assertEqual(args.pop(0), '-i"<lint-path>/lnt"')
        # ensure all other options are passed as-is
        self.assertEqual(args.pop(0), "o1")
        self.assertEqual(args.pop(0), "o2")
        # ensure defines are passed as defines
        self.assertEqual(args.pop(0), "-dd1")
        self.assertEqual(args.pop(0), "-dd2")
        # ensure include paths a re passed quoted
        self.assertEqual(args.pop(0), '-i"i1"')
        self.assertEqual(args.pop(0), '-i"i2"')
        # ensure that the file to check is passed finally
        self.assertEqual(args.pop(0), "<file>")
