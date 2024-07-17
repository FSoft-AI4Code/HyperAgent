import os
import re
import json
from subprocess import PIPE, run
from repopilot.tasks.utils.bl import name_utils, sequence_utils
from repopilot.agents.llms import LocalLLM
from repopilot.tasks.base import BaseTask, Result
from repopilot.utils import extract_patch
from repopilot.tasks.fault_localization import FaultLocalizationTask


class AutomatedProgramRepairTask(FaultLocalizationTask):
    def __init__(self, repo_dir, db_path, index_path, language, **kwargs):
        super().__init__(repo_dir, db_path, index_path, language, _type="patch", **kwargs)
        self.task_template = """Given following failed test case, fix the code is responsible for the failure. If there are multiple faults, find and fix them.
            Failed Test: {test}
            The test looks like: \n\n```java\n{test_snippets}\n```\n\n
            It failed with the following error message and call stack:\n\n```\n{failing_traces}\n```\n\n
            <output> Provide the method name in the format 'package.ClassName.methodName' that you think is responsible for the failure. You also need to edit the code to fix the fault.<\output>"""

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


    def run(self, system, idx) -> Result:
        prompt = self.construct_prompt(idx)
        system.query_codebase(prompt)
        prediction_patch = extract_patch(system.repo_dir)
        result = self.validate(prediction_patch, data)
        return result

    
    def validate(self, proposed_patch, data, mode="SH"):
        bug_name = self.bug_names[idx]
        project = bug_name.split("_")[0]
        bug_id = bug_name.split("_")[1]
        self.run_bash("checkout_bug", project, bug_id)
        result = self.run_bash("validate_patch", project, bug_id, proposed_patch, mode)
        patch_diff = self.run_bash("get_patch_git_diff", bug.project, bug.bug_id).stdout
        

        if result.returncode != 0:
            if result.stderr.find("error: ") > 0:
                result_reason = result.stderr
                result_reason = result_reason[result_reason.find("error: "):]
                result_reason = result_reason[:result_reason.find("\n")]
            elif "BUILD FAILED" in result.stderr:
                stderr_lines = result.stderr.split("\n")
                build_failed_line_i = next((i for i, line in enumerate(stderr_lines) if "BUILD FAILED" in line), None) # line number of line that contains "BUILD FAILED"
                result_reason = stderr_lines[build_failed_line_i+1]
                result_reason = result_reason[result_reason.find(' '):]
            else:
                result_reason = "Test timed out after 600 seconds"

            test_result, result_reason = "ERROR", result_reason # compilation error

        else:
            all_tests_passed = result.stdout.find("Failing tests: 0") != -1

            if all_tests_passed:
                test_result, result_reason = "PASS", "all tests passed" # test pass
            else:
                test_result = "FAIL" # test fail
                result_reason = self.run_bash("get_test_error", project, bug_id).stdout
        
        return Result("apr", test_result=test_result, result_reason=result_reason, proposed_patch=proposed_patch, patch_diff=patch_diff)

    def report(self, results):
        report = {"correct": 0, "incorrect": 0, "error": 0}
        for result in results:
            if result.kwargs["test_result"] == "PASS":
                report["correct"] += 1
            elif result.kwargs["test_result"] == "FAIL":
                report["incorrect"] += 1
            else:
                report["error"] += 1

        return report