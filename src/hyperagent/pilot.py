from typing import Optional, Any
from hyperagent.utils import setup_logger
from hyperagent.constants import DEFAULT_VERBOSE_LEVEL, DEFAULT_LLM_CONFIGS, DEFAULT_TRAJECTORIES_PATH, DEFAULT_IMAGE_NAME
from hyperagent.environment.swe_env import SWEEnv
from hyperagent.agents.agent import AgentArguments
from hyperagent.agents.llms import ModelArguments
from hyperagent.agents import Navigator, Executor, Editor, Planner, Controller
from hyperagent.log import get_logger
from pathlib import Path    

logger = setup_logger()

def Setup(
    config=DEFAULT_LLM_CONFIGS,
    save_trajectories_path=DEFAULT_TRAJECTORIES_PATH,
):
    
    navigator = Navigator(
        args=AgentArguments(
            model = ModelArguments(
                model_name=config.navigator.model,
                per_instance_cost_limit=4.0,
                temperature=0.0,
            ),
            config_file=config.navigator.config_file,
        )
    )
    
    editor = Editor(
        args=AgentArguments(
            model = ModelArguments(
                model_name=config.editor.model,
                per_instance_cost_limit=4.0,
                temperature=0.0,
            ),
            config_file=config.editor.config_file,
        )
    )

    executor = Executor(
        args=AgentArguments(
            model = ModelArguments(
                model_name=config.executor.model,
                per_instance_cost_limit=4.0,
                temperature=0.0,
            ),
            config_file=config.executor.config_file,
        )
    )
    
    planner = Planner(
        model = ModelArguments(
            model_name=config.planner.model,
            per_instance_cost_limit=4.0,
            temperature=0.0,
        )
    )
    
    controller = Controller(
        config,
        planner=planner,
        navigator=navigator,
        editor=editor,
        executor=executor,
        traj_dir=save_trajectories_path
    )
            
    return controller
    
    
class RepoPilot:
    def __init__(
        self,
        language="python",
        save_trajectories_path=DEFAULT_TRAJECTORIES_PATH,
        llm_configs = DEFAULT_LLM_CONFIGS,
    ):
        self.language = language
        self.system = Setup(
            config=llm_configs,
        )
        self.config = llm_configs
        self.save_trajectories_path = save_trajectories_path
        self.logger = get_logger("pilot")
    
    def init_environment_vars(self, env: SWEEnv):
        self.set_environment_vars(env, self.args.env_variables)
    
    def set_environment_vars(self, env: SWEEnv, env_variables: dict[str, Any]) -> None:
        assert self.config is not None  # mypy
        commands_to_execute = (
            [self.config.state_command.code]
            +
            # [code for code in self.config.util_functions] +
            # [command.code for command in self.config._commands] +
            [f"{k}={v}" for k, v in env_variables.items()]
        )
        commands = "\n".join(commands_to_execute)
        try:
            output = env.communicate(commands)
            if env.returncode != 0:
                msg = f"Nonzero return code: {env.returncode}\nOutput: {output}"
                raise RuntimeError(msg)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.logger.warning("Failed to set environment variables")
            raise e
        command_files = list()
        for file in self.config.command_files:
            datum = dict()
            with open(file) as f:
                contents = f.read()
            datum["contents"] = contents
            filename = Path(file).name
            if not contents.strip().startswith("#!"):
                if filename.endswith(".sh"):
                    # files are sourced, so they are not executable
                    datum["name"] = Path(file).name
                    datum["type"] = "source_file"
                elif filename.startswith("_"):
                    # files are sourced, so they are not executable
                    datum["name"] = Path(file).name
                    datum["type"] = "utility"
                else:
                    msg = (
                        f"Non-shell script file {file} does not start with shebang.\n"
                        "Either add a shebang (#!) or change the file extension to .sh if you want to source it.\n"
                        "You can override this behavior by adding an underscore to the file name (e.g. _utils.py)."
                    )
                    raise ValueError(msg)
            else:
                # scripts are made executable
                datum["name"] = Path(file).name.rsplit(".", 1)[0]
                datum["type"] = "script"
            command_files.append(datum)
        env.add_commands(command_files)

    def query_codebase(self, query, env):
        self.init_environment_vars(env)
        return self.system.run(query, env)