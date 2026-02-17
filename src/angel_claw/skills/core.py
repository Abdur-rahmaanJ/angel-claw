import os
import shutil
import subprocess

@skill
def create_skill(name: str, code: str) -> str:
    """
    Creates a new Python skill for Angel Claw. 
    'name' should be the filename (without .py).
    'code' should be the full Python code, including the @skill decorator and necessary imports.
    """
    skills_dir = os.path.dirname(__file__)
    file_path = os.path.join(skills_dir, f"{name}.py")
    
    try:
        with open(file_path, "w") as f:
            f.write(code)
        return f"Skill '{name}' created successfully at {file_path}."
    except Exception as e:
        return f"Error creating skill: {e}"

@skill
def install_skill_from_github(repo_url: str) -> str:
    """
    Installs skills from a GitHub repository.
    The repo should contain .py files with skills.
    """
    temp_dir = os.path.join(os.path.dirname(__file__), "_temp_repo")
    skills_dir = os.path.dirname(__file__)
    
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
        subprocess.run(["git", "clone", repo_url, temp_dir], check=True)
        
        installed_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    src = os.path.join(root, file)
                    dst = os.path.join(skills_dir, file)
                    shutil.copy(src, dst)
                    installed_files.append(file)
        
        shutil.rmtree(temp_dir)
        return f"Successfully installed skills: {', '.join(installed_files)}"
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return f"Error installing skill from GitHub: {e}"

@skill
def import_skills_from_directory(path: str = "skills") -> str:
    """
    Scans a directory for skill.md files and returns their content 
    so the agent can decide to implement them.
    """
    root_dir = os.getcwd()
    target_dir = os.path.join(root_dir, path)
    
    if not os.path.exists(target_dir):
        # Try relative to project root if called from elsewhere
        # (Though current working dir should be project root)
        return f"Error: Directory {target_dir} not found."
        
    found_skills = []
    for root, dirs, files in os.walk(target_dir):
        if "skill.md" in files:
            skill_file = os.path.join(root, "skill.md")
            with open(skill_file, "r") as f:
                content = f.read()
                rel_path = os.path.relpath(skill_file, target_dir)
                found_skills.append(f"--- Skill at {rel_path} ---\n{content}")
    
    if not found_skills:
        return "No skill.md files found."
        
    return "\n\n".join(found_skills)

@skill
def list_skills() -> str:
    """Lists all currently installed skills."""
    skills_dir = os.path.dirname(__file__)
    skills = [f[:-3] for f in os.listdir(skills_dir) if f.endswith(".py") and f != "__init__.py"]
    return f"Installed skills: {', '.join(skills)}"
