
import os
import re
import codecs
import javalang
import subprocess as sp
import logging
import time
import json

from os import path
from collections import Counter, defaultdict

TEST_CLASS_NAME = 'TestAutoGen'
SP_OUTPUT_SUPPRESS = True

"""
For injecting LLM generated test
"""
def inject_test(repo_path, src_dir, test_dir, gen_test, needed_elements, dry=False):

    needed_classpaths, needed_asserts = needed_elements

    best_path, best_file = get_best_test_class_for_injection(
        repo_path, test_dir, gen_test)

    with codecs.open(best_path, 'r', encoding='utf-8', errors='ignore') as f:
        testf_lines = f.readlines()
        testf_content = ''.join(testf_lines)
        needs_assert_imports = '@Test' in testf_content

    needed_class_stubs = [e.split('.')[-1] for e in needed_classpaths]
    unhandled_imports = derive_unhandled_imports(
        testf_content, needed_classpaths, needed_class_stubs)

    if needs_assert_imports:
        unhandled_imports.extend(
            derive_unhandled_assert_imports(testf_content, needed_asserts))

    best_classpath = best_file.removeprefix(test_dir).removesuffix('.java')
    best_classpath = best_classpath.replace('/', '.').strip('.')

    new_file_content, new_gen_test = inject_with_imports(
        best_classpath, testf_lines, gen_test, unhandled_imports)

    with open(best_path, 'w') as f:
        print(new_file_content, file=f)

    # Return name of test to execute
    test_name = f'{best_classpath}::'+parse_method(new_gen_test).name

    return test_name

def is_injectable_test_class(file_content, filepath, titular_class_name):
    tree = javalang.parse.parse(file_content)
    titular_class_def = None
    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        if node.name == titular_class_name:
            titular_class_def = node
            break
    
    assert titular_class_def is not None, f'Could not find titular class {titular_class_name} in {filepath}'
    if 'abstract' in titular_class_def.modifiers:
        return False

    for annotation in titular_class_def.annotations:
        if hasattr(annotation, 'element'):
            anno = annotation.element
            if hasattr(anno, 'type') and anno.type.name == 'Parameterized':
                return False
    
    return True

def get_best_test_class_for_injection(repo_path, test_dir, gen_test):
    # experimental similarity checker
    file_scores = defaultdict(float)
    test_tokens = [e.value for e in javalang.tokenizer.tokenize(gen_test)]
    test_tokens = set(test_tokens)
    for root, dirs, files in os.walk(path.join(repo_path, test_dir), topdown=False):
        for name in [e for e in files if e.endswith('.java')]:
            filepath = path.join(root, name)
            with codecs.open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                file_cont = f.read()
                if 'abstract' in file_cont or '@RunWith(Parameterized.class)' in file_cont: 
                    if not is_injectable_test_class(file_cont, filepath, name.removesuffix('.java')):
                        continue
                if '@Ignore' in file_cont:
                    continue  # these files are ignored when testing
                tokens = javalang.tokenizer.tokenize(file_cont)
                file_tokens = set([e.value for e in tokens])
                simsc = len(test_tokens & file_tokens)/len(test_tokens)
                file_scores[filepath.removeprefix(repo_path)] += simsc

    # Identifying best file
    best_files = sorted(file_scores.keys(),
                        key=lambda x: (file_scores[x], x),
                        reverse=True)
    best_file = list(best_files)[0]
    if best_file.startswith('/'):
        best_file = best_file[1:]
    best_path = path.join(repo_path, best_file)

    return best_path, best_file


def derive_unhandled_imports(test_class_content, needed_classpaths, needed_class_stubs):
    existing_imports = re.findall(r'import (.*);', test_class_content)

    already_imported_stubs = []
    for stub in needed_class_stubs:
        for imp in existing_imports:
            if imp.endswith(stub):
                already_imported_stubs.append(stub)
                break

    unhandled_classpaths = []
    for ncp in needed_classpaths:
        import_needed = True
        for stub in already_imported_stubs:
            if ncp.endswith(stub):
                import_needed = False
                break
        if import_needed:
            unhandled_classpaths.append(ncp)

    unhandled_imports = []
    # deriving needed imports
    for ncp in unhandled_classpaths:
        ncp_package = '.'.join(ncp.split('.')[:-1])
        search_terms = []
        search_terms.append(f'package {ncp_package};')
        search_terms.append(f'import {ncp};')
        search_terms.append(f'import static {ncp};')
        search_terms.append(f'import {ncp_package}.*;')
        search_terms.append(f'import static {ncp_package}.*;')

        append = True
        for search_term in search_terms:
            if search_term in test_class_content:
                append = False
                break
        if append:
            unhandled_imports.append(ncp)

    return unhandled_imports


def derive_unhandled_imports_legacy(test_class_content, needed_classpaths):
    unhandled_imports = []

    # deriving needed imports
    for ncp in needed_classpaths:
        ncp_package = '.'.join(ncp.split('.')[:-1])
        search_term = f'package {ncp_package};'
        if search_term in test_class_content:
            continue
        search_term = f'import {ncp};'
        if search_term in test_class_content:
            continue
        unhandled_imports.append(ncp)

    return unhandled_imports


def derive_unhandled_assert_imports(test_class_content, needed_asserts):
    unhandled_imports = []

    # deriving needed asserts
    for na in needed_asserts:
        ncp_form = f'static org.junit.Assert.{na}'
        search_term = f'import {ncp_form};'
        if search_term in test_class_content:
            continue
        unhandled_imports.append(ncp_form)

    return unhandled_imports


def inject_with_imports(best_classpath, testf_lines, gen_test, unhandled_imports):
    new_test_lines = testf_lines[:]

    # Adding necessary imports
    import_loc = -1
    for idx, line in enumerate(testf_lines):
        if 'package' in line:
            import_loc = idx+1
        if 'import' in line:
            import_loc = idx
            break
    assert import_loc != -1, best_classpath
    new_test_lines = (
        new_test_lines[:import_loc] +
        [f'import {ncp};\n' for ncp in unhandled_imports] +
        new_test_lines[import_loc:]
    )

    # Adding test to the last line of the titular class
    # change test name to avoid collision
    org_test_name = parse_method(gen_test).name
    new_test_name = org_test_name + 'AutoGen'
    gen_test = gen_test.replace(
        'void ' + org_test_name,
        'void ' + new_test_name)
    # add @Test decorator if necessary
    if '@Test' in ''.join(testf_lines):
        gen_test = '@Test\n' + gen_test.strip()

    # find last line of titular class
    tree = javalang.parse.parse(''.join(new_test_lines))
    is_titular_class = [(e.name == best_classpath.split('.')[-1]) for e in tree.types]
    assert sum(is_titular_class) == 1, f'Class with same name as classpath {best_classpath} not found.'
    titular_class_idx = is_titular_class.index(True)
    if titular_class_idx+1 == len(tree.types):
        start_loc = len(new_test_lines)-1
    else:
        start_loc = tree.types[titular_class_idx+1]._position.line-1
    
    final_paren_loc = 0
    for idx in range(start_loc, 0, -1):
        if '}' in new_test_lines[idx]:
            final_paren_loc = idx
            break
    assert final_paren_loc != 0
    new_test_lines = (
        new_test_lines[:final_paren_loc] +
        [e+'\n' for e in gen_test.split('\n')] +
        new_test_lines[final_paren_loc:]
    )
    new_file_content = ''.join(new_test_lines)
    
    return new_file_content, gen_test


"""
For adding LLM generated test as a new test class
"""
def add_test(proj, repo_path, test_prefix, gen_test, needed_elements, dry=False):
    needed_classpaths, _ = needed_elements

    # import section
    file_content = '/* Added by an automated tool. */\n'
    packages = map(lambda x: '.'.join(x.split('.')[:-1]), needed_classpaths)
    ok_packages = [k for k in packages
                   if proj_identifying_class(proj) in k]

    def package_dir_exists(p): return path.isdir(
        path.join(repo_path, test_prefix, p.replace('.', '/')))
    ok_packages = [k for k in ok_packages
                   if package_dir_exists(k)]
    if len(ok_packages) > 0:
        test_package = get_most_common_item(ok_packages)
        file_content += f'package {test_package};\n\n'
    else:
        test_package = ''
    file_content += 'import junit.framework.TestCase;\n\n'
    for ncp in needed_classpaths:
        ncp_package = '.'.join(ncp.split('.')[:-1])
        if ncp_package == test_package:
            continue  # already "imported"
        file_content += f'import {ncp};\n'
    file_content += '\n'

    # class instantiation
    file_content += 'public class TestAutoGen extends TestCase {\n'
    file_content += gen_test + '\n'
    file_content += '}'

    if dry:
        return file_content  # for debugging

    if not SP_OUTPUT_SUPPRESS:
        print(file_content)

    # File content is complete, now write test file
    test_dir = path.join(repo_path, test_prefix,
                         test_package.replace('.', '/'))

    with open(f'{test_dir}/TestAutoGen.java', 'w') as f:
        print(file_content, file=f)

    if len(test_package) > 0:
        test_name = test_package + '.TestAutoGen::'+parse_method(gen_test).name
    else:
        test_name = 'TestAutoGen::'+parse_method(gen_test).name
    return test_name


"""
Common helper functions
"""
def normalize_test(test_content):
    '''Removes comments, normalizes method name and
    variable names that are declared within the test method.'''
    test_content = test_content.strip().strip('```')
    file_lines = test_content.split('\n')
    file_tokens = list(javalang.tokenizer.tokenize(test_content))
    file_parser = javalang.parser.Parser(file_tokens)
    file_parse_tree = file_parser.parse_member_declaration()

    replace_to = dict()
    var_counter = 0

    # finding names to replace (not replacing yet)
    for path, node in file_parse_tree:
        if isinstance(node, javalang.tree.MethodDeclaration):
            replace_to[node.name] = 'testMethodAutoGen'
        elif isinstance(node, javalang.tree.VariableDeclaration):
            for declarator in node.declarators:
                replace_to[declarator.name] = f'var{var_counter}'
                var_counter += 1

    norm_test_lines = file_lines[:]
    line_delta = defaultdict(int)
    handled_lines = set()  # for removing comments
    for token in file_tokens:
        tokstr = token.value
        line, col = token.position
        line, col = line-1, col-1
        handled_lines.add(line)
        if tokstr in replace_to:
            prev_delta = line_delta[line]
            norm_test_lines[line] = (
                norm_test_lines[line][:col+prev_delta] +
                norm_test_lines[line][col+prev_delta:].replace(
                    tokstr, replace_to[tokstr], 1))
            line_delta[line] += len(replace_to[tokstr]) - len(tokstr)
    noncomment_lines = [e for idx, e in enumerate(norm_test_lines)
                        if idx in handled_lines]
    return '\n'.join(noncomment_lines)


def get_most_common_item(iterator):
    counts = Counter(iterator)
    return max(counts.keys(), key=counts.__getitem__)


def parse_method(gen_test):
    tokens = javalang.tokenizer.tokenize(gen_test)
    parser = javalang.parser.Parser(tokens)
    tree = parser.parse_member_declaration()
    return tree


def needed_imports(repo_path, src_dir, gen_test):
    tree = parse_method(gen_test)

    RelevantTypeClass = (javalang.tree.VariableDeclaration,
                         javalang.tree.MemberReference,
                         javalang.tree.MethodInvocation,
                         javalang.tree.ReferenceType,
                         javalang.tree.ClassCreator,)

    ExceptionTypeClass = (javalang.tree.CatchClauseParameter,
                          javalang.tree.MethodDeclaration,)

    # get (unqualified) class names
    needed_class_stubs = set()
    needed_asserts = set()
    for path, node in tree:
        if isinstance(node, ExceptionTypeClass):
            if isinstance(node, javalang.tree.CatchClauseParameter):
                exception_types = node.types
            if isinstance(node, javalang.tree.MethodDeclaration):
                exception_types = node.throws
            if exception_types is not None:
                for exception_type in exception_types:
                    needed_class_stubs.add(exception_type)
        if isinstance(node, RelevantTypeClass):
            if isinstance(node, javalang.tree.VariableDeclaration):
                needed_class_stubs.add(node.type.name)
            elif isinstance(node, javalang.tree.ReferenceType):
                needed_class_stubs.add(node.name)
            elif isinstance(node, javalang.tree.ClassCreator):
                needed_class_stubs.add(node.type.name)
            elif (isinstance(node, javalang.tree.MethodInvocation) and
                  ('assert' in node.member or 'fail' == node.member)):
                needed_asserts.add(node.member)
            else:
                if (node.qualifier is not None and
                    len(node.qualifier) > 0 and
                        node.qualifier[0].isupper()):
                    needed_class_stubs.add(node.qualifier.split('.')[0])

    # we need to get classpaths for full implementation
    classpaths = []
    for class_stub in needed_class_stubs:
        cmd = f'find {src_dir} -name {class_stub}.java'
        cp = sp.run(cmd.split(), capture_output=True, cwd=repo_path)
        output = cp.stdout.decode('utf-8')
        out_lines = output.split('\n')
        if len(out_lines) != 2:
            # either the file is not in the project, or there are two;
            cp = sp.run(['grep', '-rh', r'import.*\.'+class_stub+';', '.'],
                        capture_output=True, cwd=repo_path)
            example_paths = cp.stdout.decode('utf-8').split('\n')
            example_paths = [e.removeprefix('import ').rstrip('\r').rstrip(';')
                             for e in example_paths]
            if len([e for e in example_paths if len(e) > 0]) == 0:
                if len(out_lines) == 1:
                    continue
                else:
                    # multiple files with the same name, none imported.
                    # At this point, just pick one at random.
                    filepath = out_lines[0]
                    classpath = filepath.removeprefix(
                        src_dir).removesuffix('.java')
                    classpath = classpath.replace('/', '.')
            else:
                classpath = get_most_common_item(example_paths)
        else:
            filepath = out_lines[0]  # only file is selected here
            classpath = filepath.removeprefix(src_dir).removesuffix('.java')
            classpath = classpath.replace('/', '.')
        classpaths.append(classpath)
    return classpaths, needed_class_stubs, needed_asserts


def proj_identifying_class(proj):
    if proj == 'Closure':
        return 'google'
    elif 'Jackson' in proj:
        return 'jackson'
    elif 'sslcontext' in proj:
        return 'altindag.ssl'
    else:
        return proj.lower()


def get_token_similarity(bug_report_tokens, test_tokens):
    bug_report_tokens = set(bug_report_tokens)
    test_tokens = set(test_tokens)
    return len(bug_report_tokens & test_tokens) / len(test_tokens)


def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""


def process_result(result_json_path, gen_test_path):
    """
    Load execution result & return result dictionary (attaching parse error information)
    """
    with open(result_json_path, 'r') as f:
        result = json.load(f)

    
    with open(os.path.join(os.path.dirname(__file__), '../data/Defects4J/invalid_bug_reports.txt')) as f:
        invalid_bugs = [e.strip().replace('-', '_') for e in f.readlines()]

    result_processed = defaultdict(dict)
    for bug_id, test_results in result.items():
        if bug_id in invalid_bugs:
            continue
        for filename, test_result in test_results.items():
            if not filename.endswith('.txt'):
                filename = filename + '.txt'
            test_file = os.path.join(gen_test_path, filename)
            result_processed[bug_id][filename] = test_result
            result_processed[bug_id][filename]['fib_test_id'] = test_result['buggy']['failed_tests'][0] if len(test_result['buggy']['failed_tests']) > 0 else None

            if isinstance(test_result, str):
                result_processed[bug_id][filename] = {
                    'parse_error': True,
                    'compile_error': False,
                    'has_error': True,
                    'buggy_output': None,
                    'is_fib': False,
                    'success': False,
                    'test_file_path': test_file
                }
                continue


            compile_error_in_fixed = (test_result['fixed']['compile_error']) if test_result['fixed'] is not None else False
            runtime_error_in_fixed = (test_result['fixed']['runtime_error']) if test_result['fixed'] is not None else False

            error_in_fixed = compile_error_in_fixed or runtime_error_in_fixed

            result_processed[bug_id][filename]['parse_error'] = False
            result_processed[bug_id][filename]['compile_error'] = test_result['buggy']['compile_error'] or compile_error_in_fixed
            result_processed[bug_id][filename]['has_error'] = test_result['buggy']['compile_error'] or test_result['buggy']['runtime_error'] or error_in_fixed
            result_processed[bug_id][filename]['test_file_path'] = test_file
            result_processed[bug_id][filename]['buggy_output'] = test_result['buggy']['fib_error_msg'] if 'fib_error_msg' in test_result['buggy'] else None
            result_processed[bug_id][filename]['exception_type'] = test_result['buggy']['exception_type'] if 'exception_type' in test_result['buggy'] else None
            result_processed[bug_id][filename]['value_matching'] = test_result['buggy']['value_matching'] if 'value_matching' in test_result['buggy'] else None
            result_processed[bug_id][filename]['exception_msg'] = test_result['buggy']['failure_message'] if 'failure_message' in test_result['buggy'] else None

            result_processed[bug_id][filename]['is_fib'] = test_result['buggy']['autogen_failed'] and (not error_in_fixed)
            result_processed[bug_id][filename]['success'] = test_result['success'] and (not error_in_fixed)

    return result_processed


def count_test_tokens(test_content):
    test_content = test_content.strip().strip('```')
    file_tokens = list(javalang.tokenizer.tokenize(test_content))
    return len(file_tokens)