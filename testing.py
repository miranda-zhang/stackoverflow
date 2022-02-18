
## This module is used by the testing programs.

## Do NOT open, run, modify, move or delete this file.

import sys
import os.path
import importlib
import importlib.machinery
import ast
import io

import multiprocessing

class ModuleTestBase (object):
    STAGE_READ = 1
    STAGE_PARSE = 2
    STAGE_CHECK = 3
    STAGE_LOAD = 4
    STAGE_TEST = 5

    allowed = (ast.Import, ast.ImportFrom, ast.FunctionDef)

    allowed_modules = None
    forbidden_modules = None

    def __init__(self, arg1, verbose = 0, raise_exceptions = True):
        self.raise_exceptions = raise_exceptions
        self.verbose = verbose
        self.filepath = None
        self.source = None
        self.ast = None
        self.module = None
        if isinstance(arg1, str):
            self.filepath = arg1
            self.name = os.path.basename(self.filepath)
            self.stage = 0
        else:
            self.module = sys.modules['__main__']
            self.stage = self.STAGE_LOAD
        self.warnings = []

    def _parse_file(self):
        assert(isinstance(self.filepath, str))
        try:
            f = open(self.filepath, 'r')
            self.source = f.read() # should read all of the file
            f.close()
        except FileNotFoundError as fnf_exc:
            if self.raise_exceptions:
                raise fnf_exc
            else:
                return False, self.STAGE_READ, "file " + self.filepath + " not found"
        except Exception as exc:
            if self.raise_exceptions:
                raise exc
            else:
                return False, self.STAGE_READ, exc.__class__.__name__ + " " + \
                    str(exc) + " reading file " + self.filepath
        self.stage = self.STAGE_READ
        try:
            self.ast = ast.parse(self.source)
        except Exception as exc:
            if self.raise_exceptions:
                raise exc
            else:
                return False, self.STAGE_PARSE, exc.__class__.__name__ + " " + \
                    str(exc) + " parsing " + self.name
        assert(isinstance(self.ast, ast.Module))
        self.stage = self.STAGE_PARSE
        return True, self.STAGE_PARSE, "file parsed ok"

    def _check_ast_exception(self, item):
        if type(item) == ast.Expr:
            assert hasattr(item, 'value')
            if type(item.value) == ast.Str:
                self.warnings.append(("docstring outside function def",
                                      self.name + ", line " + str(item.lineno)))
                return True
        return False

    def _check_ast(self, warn_only = False):
        assert(isinstance(self.ast, ast.Module))
        for item in ast.iter_child_nodes(self.ast):
            if self._check_ast_exception(item):
                continue
            elif type(item) not in self.allowed:
                if warn_only:
                    self.warnings.append((item.__class__.__name__ + " ignored",
                                          self.name + ", line " + str(item.lineno)))
                else:
                    msg = self.name + ", line " + str(item.lineno) + " : " \
                          + item.__class__.__name__ + " is not allowed" + \
                          "\n(only import statements and function definitions)"
                    if self.raise_exceptions:
                        raise Exception(msg)
                    else:
                        return False, self.STAGE_CHECK, msg
        self.stage = self.STAGE_CHECK
        return True, self.STAGE_CHECK, "ast check ok"

    def _recursive_check_imports(self, node, allowed, forbidden):
        msg = ""
        ok = True
        for item in ast.iter_child_nodes(node):
            if type(item) == ast.Import:
                assert hasattr(item, 'names')
                assert isinstance(item.names, list)
                assert len(item.names) > 0
                for alias in item.names:
                    assert hasattr(alias, 'name')
                    assert isinstance(alias.name, str)
                    if allowed is not None:
                        if alias.name not in allowed:
                            if len(msg) > 0:
                                msg += "; "
                            msg += self.name + ", line " + str(item.lineno) \
                                   + " : " + " use of module " + alias.name \
                                   + " is not allowed"
                            ok = False
                    if forbidden is not None:
                        if alias.name in forbidden:
                            if len(msg) > 0:
                                msg += "; "
                            msg += self.name + ", line " + str(item.lineno) \
                                   + " : " + " use of module " + alias.name \
                                   + " is not allowed"
                            ok = False
            elif type(item) == ast.ImportFrom:
                assert hasattr(item, 'module')
                assert isinstance(item.module, str)
                if allowed is not None:
                    if item.module not in allowed:
                        if len(msg) > 0:
                            msg += "; "
                        msg += self.name + ", line " + str(item.lineno) \
                               + " : " + " use of module " + item.module \
                               + " is not allowed"
                        ok = False
                if forbidden is not None:
                    if item.module in forbidden:
                        if len(msg) > 0:
                            msg += "; "
                        msg += self.name + ", line " + str(item.lineno) \
                               + " : " + " use of module " + item.module \
                               + " is not allowed"
                        ok = False
            else:
                r_ok, r_msg = self._recursive_check_imports(item, allowed, forbidden)
                if not r_ok:
                    if len(msg) > 0:
                        msg += "; "
                    msg += r_msg
                ok = ok & r_ok
        return ok, msg

    def _check_imports(self, allowed = None, forbidden = None):
        assert(isinstance(self.ast, ast.Module))
        ok, msg = self._recursive_check_imports(self.ast, allowed, forbidden)
        if not ok:
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, self.STAGE_CHECK, msg
        self.stage = self.STAGE_CHECK
        return True, self.STAGE_CHECK, "import check ok"

    def _load_file(self):
        assert(isinstance(self.filepath, str))
        loader = importlib.machinery.SourceFileLoader("_test_mod", self.filepath)
        try:
            self.module = loader.load_module()
        except ImportError as exc:
            if self.raise_exceptions:
                raise exc
            else:
                return False, self.STAGE_LOAD, "error " + str(exc) + \
                    " loading " + self.filepath
        self.stage = self.STAGE_LOAD
        return True, self.STAGE_LOAD, "load ok"

    def _load_functions(self):
        assert (isinstance(self.ast, ast.Module))
        statements = []
        for child_node in ast.iter_child_nodes(self.ast):
            if isinstance(child_node, ast.FunctionDef):
                statements.append(child_node)
            elif isinstance(child_node, ast.Import):
                statements.append(child_node)
            elif isinstance(child_node, ast.ImportFrom):
                statements.append(child_node)
        self.filtered_module = ast.Module(body=statements, type_ignores=[])
        code = compile(self.filtered_module, '<ast>', 'exec')
        self.module = {}
        exec(code, self.module)
        self.stage = self.STAGE_LOAD
        return True, self.STAGE_LOAD, "load ok"

    def test_LOAD(self):
        if self.stage < self.STAGE_CHECK:
            (ok, stage, msg) = self.test_CHECK()
            if not ok:
                return False, stage, msg
        #return self._load_file()
        return self._load_functions()

    def test_CHECK(self):
        if self.stage < self.STAGE_PARSE:
            (ok, stage, msg) = self._parse_file()
            if not ok:
                return False, stage, msg
        (ok, stage, msg) = self._check_ast(warn_only = True)
        assert ok
        if ok:
            if self.allowed_modules is not None or \
               self.forbidden_modules is not None:
                (ok, stage, msg) = self._check_imports(self.allowed_modules,
                                                       self.forbidden_modules)
        return ok, stage, msg

    def run(self):
        return self.test_LOAD()

    def find_function(self, name):
        if self.stage < self.STAGE_LOAD:
            (ok, stage, msg) = self.test_LOAD()
            if not ok:
                return False, stage, msg
        #if name not in self.module.__dict__:
        if name not in self.module:
            return True, None, name + " is not defined in " + self.name \
                + " (did you name it _exactly_ as the problem requires?)"
        #fun = self.module.__dict__[name]
        fun = self.module[name]
        if type(fun) != type(ModuleTestBase.find_function):
            return False, None, name + " is defined in " + self.name + \
                " but it is not a function"
        return True, fun, "ok"

    def pre_test_run(self):
        for name in self.allowed_modules:
            mod = importlib.import_module(name)
        for name, mod in sys.modules.items():
            mod.__loader__ = None

    def pre_test_run(self):
        for name in self.allowed_modules:
            mod = importlib.import_module(name)
        for name, mod in sys.modules.items():
            mod.__loader__ = None
        sys.modules['builtins'].open = None
        sys.modules['builtins'].compile = None
        sys.modules['builtins'].eval = None
        sys.modules['builtins'].exec = None
        # __builtins__.open = None
        # __builtins__.compile = None
        # __builtins__.eval = None
        # __builtins__.exec = None

    def cleanup(self):
        if '_test_mod' in sys.modules:
            sys.modules.pop('_test_mod')

    ## end class ModuleTestBase

class ReadOnlyStringIO (io.StringIO):

    def writable(self):
        return False

    def seekable(self):
        return False

class FunctionTestBase (object):

    def __init__(self, function, tests = tuple(),
                 type_cast_answer = True,
                 verbose = 0, raise_exceptions = True,
                 suppress_output = False):
        self.raise_exceptions = raise_exceptions
        self.suppress_output = suppress_output
        self.verbose = verbose
        # delayed initialisation
        if type(function) == tuple:
            self.mod, self.name = function
            self.function = None
        else:
            self.function = function
            self.name = function.__name__
        self.tests = tests
        self.type_cast_answer = type_cast_answer
        self.details = None
        self.collate = 0

    # Methods _get_test_args and _check_answer can be overridden
    # by subclasses to extend/specialise the definition of a test
    # case (and/or the way the function return value is compared
    # to the expected value, and/or the message produced if it is
    # not correct). The default implementation (i.e., this class)
    # assumes a test is two-element sequence (args, ans), and that
    # answers are checked with simple equality.
    def _get_test_args(self, test):
        return test[0]

    def _str_tuple(self, args):
        return '(' + ', '.join([repr(arg) for arg in args]) + ')'

    def _call_string(self, test):
        return "call " + self.name + self._str_tuple(self._get_test_args(test))

    def _test_type_ctor(self, test):
        return type(test[1])

    def _type_check_answer(self, test, fvalue):
        # special check for no return:
        if type(fvalue) == type(None):
            msg = self._call_string(test) + \
                  " did not return any value (missing return statement?)"
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        # first, check if type already matches:
        if type(fvalue) == type(test[1]):
            return True, fvalue
        # if type casting enabled, check if returned value can
        # be cast to expected type:
        if self.type_cast_answer:
            ok = False
            try:
                fvalue_type = type(fvalue)
                expected_type = self._test_type_ctor(test)
                type_cast_fvalue = expected_type(fvalue)
                #print(fvalue, expected_type, type_cast_fvalue)
                if fvalue_type(type_cast_fvalue) == fvalue:
                    ok = True
                    fvalue = type_cast_fvalue
            except:
                pass
            if not ok:
                msg = self._call_string(test) + \
                      " returned the value " + str(fvalue) + " of type " + \
                      str(type(fvalue)) + \
                      " which could not be converted to the type " + \
                      str(type(test[1])) + " of the expected answer " + \
                      str(test[1])
                if self.raise_exceptions:
                    raise Exception(msg)
                else:
                    return False, msg
        # else (type casting not enabled), check return type matches exactly
        elif type(fvalue) != type(test[1]):
            msg = self._call_string(test) + \
                  " returned incorrect type " + str(type(fvalue)) \
                  + "; the expected type is " + str(type(test[1]))
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        return True, fvalue

    def _check_answer(self, test, fvalue):
        ok, result = self._type_check_answer(test, fvalue)
        if not ok:
            return ok, result
        fvalue = result
        # check returned value matches (equal)
        if fvalue != test[1]:
            msg = self._call_string(test) + \
                  " returned incorrect answer " + str(fvalue) \
                  + "; the expected answer is " + str(test[1])
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        else:
            return True, self._call_string(test) + " ok"

    def _run_test(self, test):
        args = self._get_test_args(test)
        if self.verbose > 1:
            print("calling " + self.name + self._str_tuple(args))
        try:
            fvalue = self.function(*args)
        except Exception as exc:
            msg = self._call_string(test) + \
                  " caused " + exc.__class__.__name__ + " " + str(exc)
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        return self._check_answer(test, fvalue)

    def _group_fails_by_message(self):
        assert self.details is not None
        assert len(self.details) == len(self.tests)
        assert len(self.tests) > 0
        msg_map = dict()
        for index in range(len(self.tests)):
            call = self._call_string(self.tests[index])
            msg = self.details[index][2][len(call):]
            if msg not in msg_map:
                msg_map[msg] = []
            msg_map[msg].append(index)
        return msg_map

    def run(self, result):
        # resolve delayed initialisation of the function to be tested:
        if self.function is None:
            ok, fun, msg = self.mod.find_function(self.name)
            if not ok or fun is None:
                self.details = [(i, False, msg) for i in range(len(self.tests))]
                return False, msg
            self.function = fun
        n_passed = 0
        self.details = []
        sys_stdin = sys.stdin
        sys_stdout = sys.stdout
        sys.stdin =  ReadOnlyStringIO('')
        if self.suppress_output:
            sys.stdout =  io.StringIO('')
        for num, test in enumerate(self.tests):
            passed, msg = self._run_test(test)
            if passed:
                n_passed += 1
            self.details.append((num, passed, msg))
            if self.verbose > 0:
                print(msg)
        sys.stdin =  sys_stdin
        if self.suppress_output:
            sys.stdout =  sys_stdout
        if self.collate == 2:
            rmsg = "; ".join(["#{}: {}".format(num, msg)
                              for (num, was_ok, msg) in self.details])
        elif self.collate == 1:
            if n_passed == 0:
                msg_map = self._group_fails_by_message()
                parts = [ str(nums) + ": " + msg for msg, nums in msg_map.items() ]
                cmsg = "; ".join(parts)
                rmsg = "all (" + str(len(self.tests)) + ") tests failed: " + cmsg
            elif n_passed < len(self.tests):
                rmsg = str(len(self.tests) - n_passed) + " of " \
                       + str(len(self.tests)) + " tests failed: " \
                       + "; ".join(["#{}: {}".format(num, msg) for
                                    (num, was_ok, msg) in self.details
                                    if not was_ok])
            else:
                rmsg = str(len(self.tests)) + " tests passed"
        else:
            if n_passed < len(self.tests):
                rmsg = str(len(self.tests) - n_passed) + " of " \
                       + str(len(self.tests)) + " tests failed"
            else:
                rmsg = str(len(self.tests)) + " tests passed"
        
        result.extend([n_passed >= len(self.tests), rmsg])
        return n_passed >= len(self.tests), rmsg

    def total(self):
        ## can only be called after tests have run:
        #assert self.details is not None
        passed = 0
        failed = 0
        if self.details is not None:
            for (num, was_ok, msg) in self.details:
                if was_ok:
                    passed += 1
                else:
                    failed += 1
        return passed, failed

    def common_error_msg(self):
        '''This method can only be called after tests have executed.
        Checks if all tests failed with a common error message; if so,
        returns that error message (string); otherwise, returns None.'''
        assert self.details is not None
        assert len(self.details) == len(self.tests)
        assert len(self.tests) > 0
        n_pass, n_fail = self.total()
        if n_fail < len(self.tests):
            return None # not all tests failed, so no common error
        # set message from first test as template
        template_msg = self.details[0][2]
        # remove the call string from the template message
        template_msg = template_msg[len(self._call_string(self.tests[0])):]
        # count how many messages equal the template, post their call string
        n_same = sum([self.details[i][2][len(self._call_string(self.tests[i])):] == template_msg for i in range(len(self.tests))])
        # if it's all, then return the common error message:
        if n_same == len(self.tests):
            return template_msg
        # else, None
        return None

    ## end class FunctionTestBase


class FunctionTestWithExplanation (FunctionTestBase):

    # def __init__(self, function, tests = tuple(),
    #              type_cast_answer = True, 
    #              verbose = 0, raise_exceptions = True,
    #              suppress_output = False):
    #     FunctionTestBase.__init__(self, function, tests, type_cast_answer,
    #                               verbose, raise_exceptions, suppress_output)

    def _make_explanation(self, test):
        if len(test) > 3:
            expl = " (" + test[2].format(*test[3:]) + ")"
        elif len(test) > 2:
            expl = " (" + test[2] + ")"
        else:
            expl = ""
        return expl

    def _check_answer(self, test, fvalue):
        ok, result = self._type_check_answer(test, fvalue)
        if not ok:
            return ok, result
        fvalue = result
        # check returned value matches (equal)
        if fvalue != test[1]:
            msg = self._call_string(test) + \
                  " returned incorrect answer " + str(fvalue) \
                  + "; the expected answer is " + str(test[1]) \
                  + self._make_explanation(test)
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        else:
            return True, self._call_string(test) + " ok"

    ## end class FunctionTestWithExplanation


class FunctionTestReturningFloat (FunctionTestWithExplanation):

    def __init__(self, function, tests = tuple(), precision = 1e-5,
                 verbose = 0, raise_exceptions = True,
                 suppress_output = False):
        FunctionTestBase.__init__(self, function, tests, True, verbose,
                                  raise_exceptions, suppress_output)
        self.precision = precision

    def _check_answer(self, test, fvalue):
        ok, result = self._type_check_answer(test, fvalue)
        if not ok:
            return ok, result
        fvalue = result
        # check returned value matches (to precision):
        if abs(fvalue - test[1]) > self.precision:
            msg = self._call_string(test) + \
                  " returned incorrect answer " + str(fvalue) \
                  + "; the expected answer is " + str(test[1]) \
                  + self._make_explanation(test) \
                  + " and the difference is > " + str(self.precision)
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        else:
            return True, self._call_string(test) + " ok"

    ## end class FunctionTestReturningFloat

class FunctionTestOnMutableArgs (FunctionTestWithExplanation):

    import copy

    def _run_test(self, test):
        args = self._get_test_args(test)
        args1 = self.copy.deepcopy(args)
        if self.verbose > 1:
            print("calling " + self.name + self._str_tuple(args))
        try:
            fvalue = self.function(*args1)
        except Exception as exc:
            msg = self._call_string(test) + \
                  " caused " + exc.__class__.__name__ + " " + str(exc)
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        if not (args1 == args):
            msg = self._call_string(test) + \
                  " modified argument(s): " + self._str_tuple(args1)
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        return self._check_answer(test, fvalue)

    ## end class FunctionTestOnMutableArgs

class FunctionTestArgModifier (FunctionTestWithExplanation):

    import copy

    def _run_test(self, test):
        args = self._get_test_args(test)
        args1 = self.copy.deepcopy(args)
        if self.verbose > 1:
            print("calling " + self.name + self._str_tuple(args))
        try:
            self.function(*args1)
        except Exception as exc:
            msg = self._call_string(test) + \
                  " caused " + exc.__class__.__name__ + " " + str(exc)
            if self.raise_exceptions:
                raise Exception(msg)
            else:
                return False, msg
        ## this assumes the argument to be modified is the first
        return self._check_answer(test, args1[0])

    ## end class FunctionTestArgModifier

class StagedTest:

    def __init__(self, tests = tuple(), verbose = 0,
                 raise_exceptions = True, timeout = None):
        self.raise_exceptions = raise_exceptions
        self.verbose = verbose
        self.tests = tests
        self.details = None
        self.collate = 0
        self.timeout = timeout

    def run(self):
        n_passed = 0
        self.details = []
        for (i, test) in enumerate(self.tests):
            if self.verbose > 1:
                print("testing stage " + str(i + 1))
                
            #passed, msg = test.run()
            manager = multiprocessing.Manager()
            run_result = manager.list()
            proc = multiprocessing.Process(target = test.run, args = (run_result,))
            proc.start()
            proc.join(timeout = self.timeout)
            proc.terminate()
            if len(run_result) == 0:
                # timeout
                passed = False
                msg = "timeout"
            else:
                passed = run_result[0]
                msg = run_result[1]
            
            if passed:
                n_passed += 1
            self.details.append((i + 1, passed, msg))
            if self.verbose > 0:
                print("stage " + str(i + 1) + ": " + msg)
        if n_passed == len(self.tests):
            return True, "all stages passed"
        elif n_passed == 0:
            if self.collate == 1:
                return False, "all stages failed (" + self.failed_stage_messages() + ")"
            else:
                return False, "all stages failed"
        else:
            if self.collate == 1:
                return False, "stages " + " & ".join([str(snum) for snum in self.solved()]) + \
                    " of " + str(len(self.tests)) + " passed (" + self.failed_stage_messages() + ")"
            else:
                return False, "stages " + " & ".join([str(snum) for snum in self.solved()]) + \
                    " of " + str(len(self.tests)) + " passed"

    def solved(self):
        ## this can only be called after tests have been run
        assert self.details is not None
        return [snum for snum, spass, _ in self.details if spass]

    def total(self):
        ## can only be called after tests have run:
        assert self.details is not None
        passed = 0
        failed = 0
        for test in self.tests:
            stage_passed, stage_failed = test.total()
            passed += stage_passed
            failed += stage_failed
        return passed, failed

    def totals_by_stage(self):
        ## can only be called after tests have run:
        assert self.details is not None
        return [test.total() for test in self.tests]

    def failed_stage_messages(self):
        ## this can only be called after tests have been run
        assert self.details is not None
        return "; ".join([str(snum) + ":" + smsg for snum, spass, smsg in self.details if not spass])

    def common_error_msg(self):
        '''Retrieve the common error message from each stage; if they
        all exist and are all equal, return as the common error message
        of the staged test, else return None.'''
        stage_cems = [ test.common_error_msg() for test in self.tests ]
        if any([ cem is None for cem in stage_cems ]):
            return None
        if sum([ cem == stage_cems[0] for cem in stage_cems ]) == len(self.tests):
            return stage_cems[0]
        return None
        
    ## end class StagedTest
