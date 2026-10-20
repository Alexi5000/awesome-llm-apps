import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'ai_agent_framework_crash_course/google_adk_crash_course/4_tool_using_agent/4_2_function_tools/calculator_agent/tools.py'
spec = importlib.util.spec_from_file_location('calculator_tools', PATH)
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class CalculatorSecurityTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        for expression, result in [('2 + 3 * 4', 14), ('-(2 + 3) / 2', -2.5), ('7 // 2', 3), (' .5 + .25 ', .75)]:
            with self.subTest(expression=expression):
                self.assertEqual(tools.calculate_basic_math(expression)['result'], result)

    def test_rejects_unbounded_and_non_arithmetic_expressions(self):
        for expression in ['9**9**9', '2**8', '1e309', 'True', '__import__("os")', '1abc2', '1+' * 300 + '1', '(' * 1000 + '1' + ')' * 1000, '1e100*1e100', '[1]', '']:
            with self.subTest(expression=expression):
                self.assertEqual(tools.calculate_basic_math(expression)['status'], 'error')

    def test_zero_division_remains_explicit(self):
        self.assertEqual(tools.calculate_basic_math('1 / 0')['error'], 'Division by zero')


if __name__ == '__main__':
    unittest.main()
