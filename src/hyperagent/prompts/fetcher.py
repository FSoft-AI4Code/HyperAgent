system_prompt = "You will be given a task and a list of candidate contexts, and you need to critically examine whether these contexts are relevant and useful to resolve the context or not. The answer format should be <relevance>list[bool]</relevance> that indicates whether each context is relevant or not. For example, [True, False, True] means the first and third contexts are relevant, while the second context is not. You can also provide a brief explanation for each context if you think it is necessary."
message_prompt = """Task: {task}
Candidate Contexts: {contexts}
Relevance:"""