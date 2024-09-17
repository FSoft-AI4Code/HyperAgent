import os
import re
import json
from subprocess import PIPE, run
from hyperagent.tasks.utils.bl import name_utils, sequence_utils
from hyperagent.agents.llms import LocalLLM
from hyperagent.tasks.base import BaseTask, Result

BUG_INFO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                            "data/defects4j/")

class FaultLocalization(BaseTask):
    RANGE_REGEX = "\(line (?P<beginline>\d+),col (?P<begincol>\d+)\)-\(line (?P<endline>\d+),col (?P<endcol>\d+)\)"
    def __init__(self, logdir, split, _type="pred", **kwargs):
        self.max_repetitions = kwargs.get("max_repetitions", 3)
        self.max_num_tests = kwargs.get("max_num_tests", 1)
        super().__init__(logdir, split, _type=_type, **kwargs)
        self.task_template = """Given following failed test case, localize which method in the codebase is responsible for the failure.
            Failed Test: {test}
            The test looks like: \n\n```java\n{test_snippets}\n```\n\n
            It failed with the following error message and call stack:\n\n```\n{failing_traces}\n```\n\n
            <output> provide the method name in the format 'package.ClassName.methodName' that you think is responsible for the failure. No need to call editor to fix the fault.<\output>"""
        
        self._max_repetition_in_stack = 5
        self.defects4j_path = kwargs.get("defects4j_path")
        self.java_home = kwargs.get("java_home", "/usr")
        self.llm = LocalLLM({"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "system_prompt": "Given following answer and true buggy methods, output True or False whether the predicted method is matched with buggy methods or not.", "max_tokens": 25000})
        
    def failing_test_signatures(self, _fail_info):
        return list(_fail_info.keys())
    
    def report(self, results):
        correct = sum(r.kwargs["correct"] for r in results)
        total = len(results)
        return {"correct": correct, "total": total}

    def setup(self):
        self.bug_names = os.listdir(BUG_INFO_DIR)
    
    def construct_prompt(self, idx):
        bug_name = self.bug_names[idx]
        fail_info = self._load_fail_info(bug_name)
        fail_test_signatures = [
            signature for signature in self.failing_test_signatures(fail_info)
            if self.get_test_snippet(signature, bug_name) is not None
        ]
        fail_test_signatures = fail_test_signatures[:self.max_num_tests]
        test_snippets = "\n\n".join(self.get_test_snippet(signature, bug_name).rstrip() for signature in fail_test_signatures)
        failing_traces = "\n\n".join(self.get_fail_info(signature, bug_name, minimize=False).rstrip() for signature in fail_test_signatures)
        
        prompt = self.task_template.format(test=fail_test_signatures, test_snippets=test_snippets, failing_traces=failing_traces)
        return prompt
    
    def load_data(self, idx):
        bug_name = self.bug_names[idx]
        with open(os.path.join(BUG_INFO_DIR, bug_name, "snippet.json")) as f:
            data = json.load(f)
        return data
    
    def __len__(self):
        return len(self.bug_names)
    
    def __getitem__(self, idx):
        bug_name = self.bug_names[idx]
        project = bug_name.split("_")[0]
        bug_id = bug_name.split("_")[1]
        self.run_bash("checkout_bug", project, bug_id)
        repo_dir = f"data/repos/{project}-{bug_id}"
        return repo_dir 
    
    def run(self, system, idx) -> Result:
        prompt = self.construct_prompt(idx)
        data = self.load_data(idx)
        system.query_codebase(prompt)
        prediction = system.system._groupchat.messages[-1]["content"]
        result = self.validate(prediction, data)
        return result

    def match(self, prediction, buggy_methods):
        match_str = self.llm(f"Here is the answer: {prediction} and buggy methods {''.join(buggy_methods)}")
        if "true" in match_str.lower():
            return True
        return False
    
    def validate(self, prediction, data):
        buggy_methods = [method["name"] for method in data if method["is_bug"]]
        if self.match(prediction, buggy_methods):
            return Result(task="bug localization", correct=True)
        return Result(task="bug localization", correct=False)

    def _load_fail_info(self, bug_name):
        fail_info = dict()
        with open(os.path.join(BUG_INFO_DIR, bug_name, "failing_tests")) as f:
            for l in f:
                if l.startswith("--- "):
                    tc_name = l.split()[-1]
                    tc_signature = tc_name.replace("::", ".") + "()"
                    fail_info[tc_signature] = {"error_message": "", "stack_trace": ""}
                else:
                    fail_info[tc_signature][
                        "stack_trace" if l.startswith("\tat") else "error_message"] += l
        return fail_info
    
    def get_test_snippet(self, signature, bug_name):
        def _get_error_location(signature, fail_info):
            """
            Extracts the line number from the provided failure information related to a test case.

            Parameters:
                signature (str): The name of the test case in the format 'package.ClassName.test_method()'.
                fail_info (str): The failure information containing the stack trace with error details.

            Returns:
                int: The line number where the error occurred within the test method.

            Example:
                signature = 'org.jfree.data.general.junit.DatasetUtilitiesTests.testBug2849731_2()'
                fail_info = 'java.lang.NullPointerException\n\tat org.jfree.data.general.junit.DatasetUtilitiesTests.testBug2849731_2(DatasetUtilitiesTests.java:1276)'
                _get_error_location(signature, fail_info)
                Output: 1276

            Note:
                This function assumes that the provided 'fail_info' follows the standard Java stack trace format,
                where each line starts with '\tat' followed by the method name and file location in parentheses.
                It specifically looks for lines starting with '\tat' followed by the test method's fully-qualified name
                (obtained from 'signature') and extracts the line number from that line using regular expressions.
            """
            method_name = name_utils.get_method_name(signature, simple_name=False)
            for line in fail_info.splitlines():
                if not line.startswith("\tat"):
                    continue
                m = re.match(f"\tat (.*)\(.*:(\d+)\)", line)
                """
                line: '\tat org.jfree.data.general.junit.DatasetUtilitiesTests.testBug2849731_2(DatasetUtilitiesTests.java:1276)'
                group(0): org.jfree.data.general.junit.DatasetUtilitiesTests.testBug2849731_2
                group(1): 1276
                """
                if m is None or m.group(1) != method_name:
                    continue
                line_number = m.group(2)
                return int(line_number)
            return None # not found

        parents = list()
        matching_test_case = None
        test_class_name = name_utils.drop_base_name(
            name_utils.get_method_name(signature, simple_name=False))
        _test_lists = self._load_test_lists(bug_name) # list of dict
        for test_case in _test_lists:
            if signature == test_case["signature"]: # exact matching
                matching_test_case = test_case
                break
            if name_utils.get_method_name(signature) == name_utils.get_method_name(test_case["signature"]): # short method name matching
                if test_class_name in test_case["child_classes"]:
                    parents.append((len(test_case["child_classes"]), test_case)) # tuple(# childs, classname)

        if matching_test_case is None: # when the signature is not available
            if parents:
                matching_test_case = sorted(parents)[0][1]
            else:
                return None # not found

        test_case = matching_test_case
        snippet = test_case["snippet"]
        begin_lineno = int(test_case["begin_line"])

        if signature in self._load_fail_info(bug_name):
            # if the test is failed and the postprocessing is on,
            # find and annotate error location
            error_lineno = _get_error_location(test_case["signature"], # name of actual matching test case
                                               self.get_fail_info(signature, bug_name, minimize=False))
            annotate_error_location = error_lineno is not None
        else:
            annotate_error_location = False

        if annotate_error_location:
            # find line ranges containing the error location and previous assertions
            assertion_line_numbers = []
            snippet_raw_lines = snippet.splitlines()

            for child_range in test_case["child_ranges"]:
                m = re.match(self.__class__.RANGE_REGEX, child_range)
                range_info = m.groupdict()
                child_begin_lineno, child_end_lineno = int(range_info["beginline"]), int(range_info["endline"])
                range_statement = "\n".join(
                    snippet_raw_lines[child_begin_lineno-begin_lineno:child_end_lineno-begin_lineno+1]
                )
                if child_begin_lineno <= error_lineno <= child_end_lineno:
                    error_end_lineno = child_end_lineno
                if (range_statement.lstrip().startswith('assert') and
                    child_end_lineno < error_lineno): # save previous assertion locs
                    assertion_line_numbers += list(range(child_begin_lineno, child_end_lineno+1))
                last_lineno = child_end_lineno # actual last line of test

            # 1. trim (1) - remove lines that come after failure location
            snippet_lines = snippet_raw_lines[:error_end_lineno-begin_lineno+1]
            #    trim (2) - remove previous assertion statements
            line_numbers = [lineno
                            for lineno in range(begin_lineno, begin_lineno + len(snippet_lines))
                            if lineno not in assertion_line_numbers]
            removed_count = len(assertion_line_numbers)
            snippet_lines = [snippet_lines[lineno-begin_lineno] for lineno in line_numbers]
            # 2. annotate
            error_index = error_lineno-begin_lineno-removed_count
            snippet_lines[error_index] = snippet_lines[error_index] + " // error occurred here"
            # 3. closing
            snippet_lines += snippet_raw_lines[last_lineno-begin_lineno+1:]
            line_numbers += list(range(last_lineno+1,len(snippet_raw_lines)+begin_lineno))
        else:
            snippet_lines = snippet.splitlines()
            line_numbers = range(begin_lineno, begin_lineno + len(snippet_lines))

        # append line numbers
        snippet_lines = sequence_utils.concat_strings(
            line_numbers, snippet_lines, sep=" : ", align=True)

        return "\n".join(snippet_lines)
    
    def get_fail_info(self, tc_signature, bug_name, minimize=False, verbose=False):
        def _clean_error_message(error_message, max_lines=5, verbose=False):
            error_message = "\n".join(error_message.splitlines()[:max_lines])
            return error_message

        def _clean_stack_trace(stack_trace, verbose=False):
            '''Returns cleaned stack that does not contain:
            (1) stack entries that start with junit.framework
            (2) stack entries below the sun.reflect.NativeMethodAccessorImpl.invoke0'''

            raw_stack = stack_trace.splitlines()

            cleaned_stack = []
            for line in raw_stack:
                if 'sun.reflect.NativeMethodAccessorImpl.invoke0' in line:
                    break
                if not ('junit.framework' in line):
                    cleaned_stack.append(line)

            # reduce repeated subsequences
            repeated_subseq = sequence_utils.repeated_subsequences(cleaned_stack,
                min_repetition=self._max_repetition_in_stack + 1)
            while repeated_subseq:
                maxlen_subseq = repeated_subseq[0]
                if verbose:
                    print(f"{maxlen_subseq['subsequence']} repeated {maxlen_subseq['num_repetition']} times")

                reduced_stack = cleaned_stack[:maxlen_subseq["start"]]
                reduced_stack += maxlen_subseq['subsequence']
                reduced_stack += [f'... (same pattern repeats {maxlen_subseq["num_repetition"]-2} more times) ...']
                reduced_stack += maxlen_subseq['subsequence']
                if maxlen_subseq["end"]+1 < len(cleaned_stack):
                    reduced_stack += cleaned_stack[maxlen_subseq["end"]+1:]
                cleaned_stack = reduced_stack
                repeated_subseq = sequence_utils.repeated_subsequences(cleaned_stack, min_repetition=self._max_repetition_in_stack+1)

            return "\n".join(cleaned_stack)

        _fail_info = self._load_fail_info(bug_name)
        
        error_message = _fail_info[tc_signature]["error_message"].rstrip()
        stack_trace = _fail_info[tc_signature]["stack_trace"].rstrip()

        if minimize:
            error_message = _clean_error_message(error_message, verbose=verbose)
            stack_trace = _clean_stack_trace(stack_trace, verbose=verbose)

        return error_message + "\n" + stack_trace
    
    def run_bash(self, function, project, bug_id, extra_arg1=None, extra_arg2=None):
        project_location = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        work_dir = os.path.join(project_location, f"data/repos/{project}-{bug_id}")
        command = ['bash', "src/repopilot/tasks/utils/bl/defects4j.sh", function, f"{project}", f"{bug_id}", f"{work_dir}", f"{self.java_home}", f"{self.defects4j_path}", f"{extra_arg1}", f"{extra_arg2}"]
        result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        if len(result.stdout) > 0:
            if result.stdout[-1] == "\n":
                result.stdout = result.stdout[:-1]
        return result
    
    def _load_test_lists(self, bug_name):
        with open(os.path.join(BUG_INFO_DIR, bug_name, "test_snippet.json")) as f:
            test_list = json.load(f)
        return test_list