from pathlib import Path
from typing import Any, TypedDict
import json
import os
from hyperagent.agents.edit import Editor
from hyperagent.agents.navigator import Navigator
from hyperagent.agents.executor import Executor
from hyperagent.agents.planner import Planner
from hyperagent.agents.memory import Memory
from hyperagent.environment.swe_env import SWEEnv
from hyperagent.constants import MAX_STEPS
from hyperagent.log import get_logger

class TrajectoryStep(TypedDict):
    action: str
    observation: str
    response: str
    state: str | None
    thought: str

class State:
    def __init__(self, links, actions):
        self.links = links
        self.actions = actions

class Controller:
    def __init__(
        self, 
        args,
        planner: Planner,
        navigator: Navigator, 
        editor: Editor,
        executor: Executor,
        max_steps: int = MAX_STEPS,
        traj_dir: str = "data/trajectories",
    ):
        self.navigator = navigator
        self.editor = editor
        self.executor = executor
        self.planner = planner
        
        self.memory = Memory(*args.memory_config)
        self.args = args
        
        self.max_steps = max_steps
        self._links = None
        self._actions = None
        self._state : dict[str, State] = {}
        self.logger = get_logger("controller")
        self.traj_dir = traj_dir
    
    def select_agent(self, agent_type: str):
        if agent_type == "navigator":
            return self.navigator
        elif agent_type == "editor":
            return self.editor
        elif agent_type == "executor":
            return self.executor
        else:
            raise ValueError(f"Invalid agent type: {agent_type}")
    
    def run(
        self,
        query: str,
        env: SWEEnv,
        observation: str | None = None,
    ):  
        traj_log_path = os.path.join(self.traj_dir, (env.record["instance_id"] + ".traj"))
        iteration: int = 0
        task_completed = False
        trajectory = []
        info = {}
        
        while (self.max_steps > iteration):
            thought, subgoal, agent_type, reset, task_completed, output = self.planner.run(query, observation)
            
            self.logger.info(f"📝 PLANNER THOUGHT: \n{thought}")
            self.logger.info(f"✅ SUBGOAL: \n{subgoal}")
            
            if task_completed:
                break
        
            agent = self.select_agent(agent_type)
            fetched_contexts = self.memory.search_context(subgoal)
            
            trajectory_step = TrajectoryStep(
                {   
                    "agent": "planner",
                    "action": subgoal,
                    "observation": observation,
                    "response": output,
                    "thought": thought,
                },
            )
            
            trajectory.append(trajectory_step)
            agent.run(env, subgoal, fetched_contexts, self.memory, trajectory)
            observation = self.get_planner_obs(agent, subgoal)
            info["model_stats"] = {
                "planner": self.planner.model.stats.to_dict(), 
                "navigator": self.navigator.model.stats.to_dict(),
                "editor": self.editor.model.stats.to_dict(),
                "executor": self.executor.model.stats.to_dict(),
            }
            self.save_trajectory(trajectory, traj_log_path, env_name=env.name, info=info)
            iteration += 1
        
        self.logger.info(f"Task completed in {iteration} iterations.")
     
    def save_trajectory(
        self, trajectory: list[dict[str, Any]], log_path: Path, env_name: str, info: dict[str, Any]
    ) -> None:
        """Save the trajectory"""
        log_dict = {
            "environment": env_name,
            "trajectory": trajectory,
            "history": self.history,
            "info": info,
        }
        log_path.write_text(json.dumps(log_dict, indent=2))
           
    def get_planner_obs(self, agent, subgoal) -> str:
        final_observation = ""
        
        if isinstance(agent, Navigator):
            contexts = self.memory.search_context(subgoal)
            if len(contexts) > 0:
                final_observation += f"\n\n RELEVANT CONTEXTS: \n{contexts}"
            else:
                greedy_context = self.memory.get_greedy_context()
                final_observation += f"\n\n RELEVANT CONTEXTS: \n{greedy_context}"
        if isinstance(agent, Editor):
            patch = self.memory.get_patch()
            if patch:
                final_observation += f"\n\n Editor Patch: \n{patch}"
            else:
                final_observation += f"\n\n No edit was made by the editor."
                if self.memory.edits:
                    final_observation += f"\n\n Last Editor Attempt: \n{self.memory.edits[-1]}"
         
        if isinstance(agent, Executor):
            execution_result = self.memory.get_greedy_execution()
            final_observation += f"\n\n Execution Result: \n{execution_result}"
        
        return final_observation