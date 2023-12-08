# parent of defects4j repo directories
import os
from shutil import which
from datetime import datetime

# make a soft link from where D4J projects are located to below location
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '/root/data/Defects4J/repos/')
# defects4j home directory
D4J_HOME = "/".join(which("defects4j").split("/")[:-3]) + "/"
# random seed
RAND_SEED=1234

def repo_path(proj, bugid):
    return os.path.join(ROOT_DIR, f'{proj}_{bugid}/')

class TimeoutException(Exception):
    pass

def d4j_path_prefix(proj, bug_num):
    if proj == 'Chart':
        return 'source/'
    elif proj == 'Closure':
        return 'src/'
    elif proj == 'Lang':
        if bug_num <= 35:
            return 'src/main/java/'
        else:
            return 'src/java/'
    elif proj == 'Math':
        if bug_num <= 84:
            return 'src/main/java/'
        else:
            return 'src/java/'
    elif proj == 'Mockito':
        return 'src/'
    elif proj == 'Time':
        return 'src/main/java/'
    elif proj == 'Cli':
        if bug_num <= 29:
            return 'src/java/'
        else:
            return 'src/main/java/'
    elif proj == 'Codec':
        if bug_num <= 10:
            return 'src/java/'
        else:
            return 'src/main/java/'
    elif proj == 'Collections':
        return 'src/main/java/'
    elif proj == 'Compress':
        return 'src/main/java/'
    elif proj == 'Csv':
        return 'src/main/java/'
    elif proj == 'Gson':
        return 'gson/src/main/java/'
    elif proj in ('JacksonCore', 'JacksonDatabind', 'JacksonXml'):
        return 'src/main/java/'
    elif proj == 'Jsoup':
        return 'src/main/java/'
    elif proj == 'JxPath':
        return 'src/java/'
    else:
        raise ValueError(f'Unrecognized project {proj}')

def d4j_test_path_prefix(proj, bug_num):
    if proj == 'Chart':
        return 'tests/'
    elif proj == 'Closure':
        return 'test/'
    elif proj == 'Lang':
        if bug_num <= 35:
            return 'src/test/java/'
        else:
            return 'src/test/'
    elif proj == "Math":
        if bug_num <= 84:
            return 'src/test/java/'
        else:
            return 'src/test/'
    elif proj == 'Mockito':
        return 'test/'
    elif proj == "Time":
        return 'src/test/java/'
    elif proj == 'Cli':
        if bug_num <= 29:
            return 'src/test/'
        else:
            return 'src/test/java/'
    elif proj == 'Codec':
        if bug_num <= 10:
            return 'src/test/'
        else:
            return 'src/test/java/'
    elif proj == 'Collections':
        return 'src/test/java/'
    elif proj == 'Compress':
        return 'src/test/java/'
    elif proj == 'Csv':
        return 'src/test/java/'
    elif proj == 'Gson':
        return 'gson/src/test/java/'
    elif proj in ('JacksonCore', 'JacksonDatabind', 'JacksonXml'):
        return 'src/test/java/'
    elif proj == 'Jsoup':
        return 'src/test/java/'
    elif proj == 'JxPath':
        return 'src/test/'
    else:
        raise ValueError(f'Cannot find test path prefix for {proj}{bug_num}')

def d4j_proj_identifing_class(proj):
    if proj == 'Closure':
        return 'google'
    elif 'Jackson' in proj:
        return 'jackson'
    else:
        return proj.lower()
        
def parse_abs_path(jfile):
    repo_dir_name = jfile.removeprefix(ROOT_DIR).split('/')[0]
    repo_dir_path = ROOT_DIR + repo_dir_name + '/'
    rel_jfile_path = jfile.removeprefix(repo_dir_path)
    return repo_dir_path, rel_jfile_path

def log(*args):
    '''Used only when flush is desired'''
    now = datetime.now()
    now_str = now.strftime(r'%Y-%m-%d %H:%M:%S.%f')
    print(f'[{now_str}]', *args, flush=True)