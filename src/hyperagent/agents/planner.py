from hyperagent.agents.llms import ModelArguments, get_model
from hyperagent.prompts.planner import system_plan, next_observation_format
from hyperagent.agents.parsing import ParseFunction

class Planner:
    def __init__(self, model_args: ModelArguments):
        self.model = get_model(model_args.model)
        self.history = []
        
        self._append_history({"role": "system", "content": system_plan, "agent": self.name})
    
    def _append_history(self, item: dict):
        self.history.append(item)
    
    def check_format_and_query(
        self,
        output: str,
    ) -> tuple[str,str, str, bool, str]:
        thought, subgoal, agent_type, task_completed = ParseFunction.get("PlannerParser")(
            output,
            strict=False,
        )   
        return thought, subgoal, agent_type, task_completed, output
        
    def forward(self, query, observation): 
        self._append_history({
            "role": "system",
            "content": next_observation_format.format(observation=observation),
            "agent": self.name
        })
        thought, subgoal, agent_type, task_completed, output = self.check_format_and_query(query)
        return thought, subgoal, agent_type, task_completed, output
    
    def run(self, query, observation):
        thought, subgoal, agent_type, task_completed, output = self.forward(query, observation)
        self._append_history({
            "role": "assistant",
            "content": output,
            "agent": "planner"
        })
        
        return thought, subgoal, agent_type, True, task_completed, output