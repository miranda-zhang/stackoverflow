# -*- coding: utf-8 -*-

from testing import ModuleTestBase, FunctionTestBase, StagedTest

import math
math.inf = float('inf')

class ExamTest (ModuleTestBase):

    def __init__(self, arg1, verbose = 0, raise_exceptions = True, timeout = None):
        ModuleTestBase.__init__(self, arg1, verbose, raise_exceptions)
        self.timeout = timeout
        self.allowed_modules = ['math', 'numpy', 'bisect', 'heapq', 'matplotlib.pyplot', 'itertools', 'statistics','scipy.special','scipy','scipy.signal', 'typing', 'numbers']

    fun_name = "peaks_valleys"

    # test1: sequence length 0-2
    test1 = (
        # length 0
        (([],), 0,),
        # length 1
        (([-6],), 0,),
        # length 2
        (([1, 7],), 0,),
        (([4, -1],), 0,),
        (([2, 2],), 0,),
    )  

    def mark(self):
        ok, fun, msg = self.find_function(self.fun_name)
        if not ok:
            print("0|" + msg)
            return            
        if fun is None:
            print("0|" + msg)
            return
        ft_1 = FunctionTestBase(fun, self.test1,
                                         verbose = self.verbose - 1,
                                         raise_exceptions = self.raise_exceptions,
                                         suppress_output = (self.verbose == 0))
        

        ft_1.collate = 0

        st = StagedTest((ft_1,), self.verbose, self.raise_exceptions, self.timeout)
        st.collate = 1
        ok, msg = st.run()
        if ok:
            mark = 7
            msg = "all tests passed"
        else:
            stages_ok = st.solved()
            totals_by_stage = st.totals_by_stage()
            passed_by_stage = [ passed for (passed, failed) in totals_by_stage]
            assert len(passed_by_stage) == 7
            if len(stages_ok) == 7:
                mark = 7
            else:
                mark = len(stages_ok)
        print(str(mark) + '|' + msg)

    ## end ExamTest


## To produce less verbose output, change verbose from 3 to 2 or 1:
#ExamTest("homework5.py", verbose = 3).run()

from argparse import ArgumentParser

if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("--verbose", "-v", type=int, nargs='?',
                        dest="verbosity", default=0, help="verbosity")
#    parser.add_argument("--test", "-t", action='store_true',
#                        dest="test", help="run original tests")
    parser.add_argument("--exceptions", "-e", action='store_true',
                        dest="exceptions", help="raise exception on first error")
    parser.add_argument('--timeout', type=int, default=10,
                        help="Time-out in seconds for marking script")
    parser.add_argument('file', type=str, nargs=1, help="file to test")
    args = parser.parse_args()

#    if args.test:
#        ExamTest(args.file[0], raise_exceptions = args.exceptions,
#                      verbose = args.verbosity).run()
#    else:
    ExamTest(args.file[0], raise_exceptions = args.exceptions,
                      verbose = args.verbosity, timeout = args.timeout).mark()
