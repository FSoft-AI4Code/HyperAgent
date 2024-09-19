from typing import List

class Result:
    def __init__(self, task, **kwargs):
        self.task = task
        self.kwargs = kwargs
    
class BaseTask:
    def __init__(self, logdir, split, type, **kwargs):
        self.logdir = logdir
        self.split = split
        self.type = type
        self.kwargs = kwargs
        self.subtasks = []
        self.setup()
    
    def setup(self):
        raise NotImplementedError()
    
    def run(self):
        raise NotImplementedError()
    
    def validate(self):
        raise NotImplementedError()
    
    def report(self, results: List[Result]):
        raise NotImplementedError()