from repopilot.tools import GoToDefinitionTool

def get_all_symbols():
    gst = GoToDefinitionTool("/datadrive05/huypn16/focalcoder/data/repos/repo__TempleRAIL__drl_vo_nav__commit__", language="python")
    symbols = gst._run(relative_path="drl_vo/src/custom_cnn_full.py", line=272, word="_forward_impl")
    print(symbols)
    
if __name__ == "__main__":
    get_all_symbols()