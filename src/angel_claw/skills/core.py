import os
import shutil
import subprocess
from angel_claw.skills.manager import skill
from angel_claw.cron import cron_manager, Job, JobSchedule, JobPayload

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

@skill
def schedule_task(name: str, schedule_kind: str, schedule_value: str, payload_kind: str, content: str = None, skill_name: str = None, args: dict = None) -> str:
    """
    Schedules a task.
    - schedule_kind: 'at' (isoformat), 'in' (relative, e.g. '1m', '30s'), 'every' (recurring, e.g. '1h'), 'cron' (expression).
    - payload_kind: 'message' (send content to user), 'prompt' (ask agent content), 'skill' (run skill_name with args).
    """
    try:
        job = Job(
            name=name,
            schedule=JobSchedule(kind=schedule_kind, value=schedule_value),
            payload=JobPayload(kind=payload_kind, content=content, skill_name=skill_name, args=args)
        )
        # Recalculate next run to ensure it's valid
        cron_manager._calculate_next_run(job)
        if not job.next_run and schedule_kind != "at":
             return f"Error: Invalid schedule {schedule_kind}: {schedule_value}"
             
        cron_manager.save_job(job)
        return f"Task '{name}' scheduled. Next run: {job.next_run}"
    except Exception as e:
        return f"Error scheduling task: {e}"

@skill
def list_tasks() -> str:
    """Lists all scheduled tasks."""
    if not cron_manager.jobs:
        return "No tasks scheduled."
    
    tasks = []
    for name, job in cron_manager.jobs.items():
        status = "Enabled" if job.enabled else "Disabled"
        tasks.append(f"- {name}: {job.schedule.kind}({job.schedule.value}) | {job.payload.kind} | Next run: {job.next_run} | {status}")
    
    return "\n".join(tasks)

@skill
def delete_task(name: str) -> str:
    """Deletes a scheduled task by name."""
    if name in cron_manager.jobs:
        cron_manager.delete_job(name)
        return f"Task '{name}' deleted."
    else:
        return f"Task '{name}' not found."
