from typing import List
from typing import Any, Dict, List, Optional

from langchain.callbacks.manager import (
    CallbackManagerForChainRun,
)
from langchain.schema import Document
from repopilot.agents.plan_seeking import PlanSeeking

class AdaptivePlanSeeking(PlanSeeking):
    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        inputs["previous_steps"] = ""
        current_notes = ""
        plan = self.planner.plan(
            inputs,
            callbacks=run_manager.get_child() if run_manager else None,
        )
        if run_manager:
            run_manager.on_text(str(plan), verbose=self.verbose)
        
        index = 0    
        while len(plan.steps) > 0:
            step = plan.steps.pop(0)
            _new_inputs = {
                "previous_steps": self.step_container,
                "current_step": step,
                "objective": inputs[self.input_key],
            }
            new_inputs = {**_new_inputs, **inputs}          
            response, intermediate_steps = self.navigator.step(
                new_inputs,
                callbacks=run_manager.get_child() if run_manager else None,
            )
            for j, react_step in enumerate(intermediate_steps):
                if isinstance(react_step[1], list):
                    obs_strings = [str(x) for x in react_step[1]]
                    tool_output = "\n".join(obs_strings)
                else:
                    tool_output = str(react_step[1])
                current_notes += f"\n\nStep: {step.value}\n\nSubstep:{j}\n\Thought: {react_step[0].log.split('Action:')[0]}\nOutput: {tool_output}\n\n"
                vec_note = react_step[0].log + "\n" + tool_output
                self.vectorstore.add_documents([Document(page_content=vec_note)])
                
            current_notes += f"Response for step {index}: {response.response}"
            
            inputs["previous_steps"] = current_notes
            
            plan = self.planner.plan(
                inputs,
                callbacks=run_manager.get_child() if run_manager else None,
            )
            
            if run_manager:
                run_manager.on_text(
                    f"*****\n\nStep: {step.value}", verbose=self.verbose
                )
                run_manager.on_text(
                    f"\n\nResponse: {response.response}", verbose=self.verbose
                )
            self.step_container.add_step(step, response)
            index +=1 
        
        ## Run the analyzer
        analyzer_inputs = {
            "current_notes": current_notes,
            "objective": inputs[self.input_key],
        }
        answer = self.analyzer.step(
            analyzer_inputs,
            callbacks=run_manager.get_child() if run_manager else None,
        )
        return {self.output_key: answer}