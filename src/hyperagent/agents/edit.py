from typing import Any

from hyperagent.agents.agent import Agent, AgentArguments
from hyperagent.agents.memory import Memory
from hyperagent.environment.swe_env import SWEEnv
from hyperagent.constants import MAX_EDIT_STEPS
from hyperagent.agents.controller import TrajectoryStep

class Editor(Agent):
    def __init__(self, args: AgentArguments):
        super().__init__("editor", args)
    
    def run(
        self,
        env: SWEEnv,   
        subgoal: str,
        observation: str,
        memory: Memory,
        trajectory: list[dict[str, Any]]
    ):
        done = False
        iteration = 0
        # Re-initialize primary
        self.setup()
        
        # Run action/observation loop
        trajectory = []
        lst_act_obs = []
        while (not done) and (iteration < MAX_EDIT_STEPS):
            for hook in self.hooks:
                hook.on_step_start()
            state = env.communicate(self.state_command) if self.state_command else None
            thought, action, output = self.forward(observation, subgoal, env.get_available_actions(), state)
            observations = list()
            run_action = self._guard_multiline_input(action)
            for sub_action in self.split_actions(run_action):
                if sub_action["agent"] == self.name or sub_action["cmd_name"] == self.config.submit_command:
                    obs, _, done, info = env.step(sub_action["action"])
                    observations.append(obs)
                    if sub_action["cmd_name"] == self.config.submit_command:
                        done = True
                        memory.add_patch(obs)
                    if done:
                        break
                else:
                    agent_name = sub_action["agent"]
                    sub_agent_output = self.call_subroutine(agent_name, sub_action, env)
                    observations.append(sub_agent_output)
                
            observation = "\n".join([obs for obs in observations if obs is not None])
            
            trajectory_step = TrajectoryStep(
                {
                    "agent": self.name,
                    "action": action,
                    "observation": observation,
                    "response": output,
                    "state": state,
                    "thought": thought,
                },
            )
            trajectory.append(trajectory_step)
            iteration += 1
        
        final_edit = [edit for action, edit in lst_act_obs if "edit" in action]
        final_obs = [obs for action, obs in lst_act_obs if "edit" not in action]
        memory.add_edit(final_edit[-1], final_obs[-1])