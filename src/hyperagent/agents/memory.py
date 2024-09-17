from hyperagent.agents.llms import ModelArguments
from sentence_transformers import SentenceTransformer
from hyperagent.agents.llms import get_model
import numpy as np
import re
from hyperagent.prompts.fetcher import system_prompt, message_prompt

class Memory:
    """
    Memory class for managing and retrieving relevant contexts.
    Attributes:
        contexts (list[str]): A list to store context strings.
        edits (list[str]): A list to store edit strings.
        execution_results (list[str]): A list to store execution result strings.
        contexts_embeddings (list[np.array]): A list to store embeddings of contexts.
        llm: The language model used for querying relevance scores.
        engine: The SentenceTransformer model used for encoding and similarity calculations.
    Methods:
        __init__(config: ModelArguments, retriever_model: str = "all-MiniLM-L6-v2"):
            Initializes the Memory class with the given configuration and retriever model.
        search_context(request: str, top_candidates: int = 3):
    """
    
    def __init__(self, config: ModelArguments, retriever_model: str = "all-MiniLM-L6-v2"):
        self.act_contexts: list[tuple[str,str]] = []
        self.contexts: list[str] = []
        self.edits: list[tuple[str, str]] = []
        self.execution_traj: list[tuple[str, str]] = []
        self.context_traj: list[list[tuple[str, str]]] = []
        self.contexts_embeddings: list[np.array] = []
        self.patches = []
        self.changed = []
        self.llm = get_model(config)
        self.engine = SentenceTransformer(retriever_model)
        
    def search_context(self, request, top_candidates=5):
        """
        Searches for the most relevant contexts based on the given request.
        Args:
            request (str): The input request for which to find relevant contexts.
            top_candidates (int, optional): The number of top candidate contexts to retrieve. Defaults to 3.
        Returns:
            None: The function currently does not return any value.
        """

        if len(self.contexts) < top_candidates: 
            top_ids = range(len(self.contexts))
        else:
            # using the retriever model to get the top candidates
            request_embedding = self.engine.encode(request)
            similarities = self.engine.similarity(request_embedding, self.contexts.values())
            top_ids = np.argsort(similarities)[-top_candidates:]
        
        # Get the top candidate contexts
        candidate_contexts = self.contexts[top_ids]
        candidate_contexts_str = "\n".join(candidate_contexts)
        messages = [
            {"message": system_prompt, "role": "system"},
            {"message": message_prompt.format(task=request, contexts=candidate_contexts_str), "role": "system"}  
        ]
        relevance_scores = self.llm.query(messages)
        should_selected = self.parse_relevance_scores(relevance_scores, len(candidate_contexts))
        selected_id = [i for i, should_select in enumerate(should_selected) if should_select]
        return "\n".join(self.contexts[selected_id])
    
    def get_greedy_context(self):
        last_trajectory = self.context_traj[-1]
        return "\n".join([context for action, context in last_trajectory])
    
    def add_context(self, trajectory: list[tuple[str, str]]):
        """
        Adds a context to the memory.
        Args:
            context (str): The context to be added to the memory.
        Returns:
            None: The function currently does not return any value.
        """
        for (action, context) in trajectory:
            if context not in self.contexts:
                self.act_contexts.append((action, context))
                self.contexts.append(context)
                self.contexts_embeddings.append(self.engine.encode(context))
            else:
                pass
        
        self.context_traj.append(trajectory)
    
    def add_edit(self, action: str, edit: str):
        """
        Adds an edit to the memory.
        Args:
            edit (str): The edit to be added to the memory.
        """
        self.edits.append((action, edit))
    
    def add_patch(self, patch):
        if patch not in self.patches:
            self.patches.append(patch)
            self.changed.append(True)
        else:
            self.changed.append(False)
    
    def get_patch(self):
        if self.changed[-1]:
            return self.patches[-1]
        else:
            return None
    
    def get_greedy_execution(self):
        return "\n".join([execution_result for action, execution_result in self.execution_traj[-1]])
    
    def add_execution_result(self, trajectories: list[tuple[str, str]]):
        """
        Adds an execution result to the memory.
        Args:
            execution_result (str): The execution result to be added to the memory.
        """
        temp = []
        for (action, execution_result) in trajectories:
            if len(execution_result.split("\n")) > 100:
                temp.append((action, execution_result.split("\n")[-100:]))
            else:
                temp.append((action, execution_result))
        
        self.execution_traj.append(temp)
    
    def parse_relevance_scores(self, relevance_scores_str, length: int):
        """
        Parses the relevance scores obtained from the LLM.
        Args:
            relevance_scores (list[bool]): The relevance scores obtained from the LLM.
        Returns:
            list[bool]: The parsed relevance scores.
        """
        match = re.match(r"<relevance>(.*)</relevance>", relevance_scores_str)
        if match:
            return list(map(bool, eval(match.group(1))))
        else:
            return [False] * length
    