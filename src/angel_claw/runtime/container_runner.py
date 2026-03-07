import sys
import json
import importlib.util
import inspect
import os

def run_skill(file_path, func_name, args_json):
    try:
        args = json.loads(args_json)
        
        # Load the skill module
        spec = importlib.util.spec_from_file_location("dynamic_skill", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        func = getattr(module, func_name)
        
        if inspect.iscoroutinefunction(func):
            import asyncio
            result = asyncio.run(func(**args))
        else:
            result = func(**args)
            
        print(json.dumps({"status": "success", "result": result}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "message": "Missing arguments"}))
        sys.exit(1)
        
    run_skill(sys.argv[1], sys.argv[2], sys.argv[3])
