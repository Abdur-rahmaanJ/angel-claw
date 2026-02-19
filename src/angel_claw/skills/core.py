import os
import shutil
import subprocess
import httpx
import zipfile
import io
import json
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
def schedule_task(name: str, schedule_kind: str, schedule_value: str, payload_kind: str, content: str = None, skill_name: str = None, args: dict = None, session_id: str = "cli-default") -> str:
    """
    Schedules a task.
    - schedule_kind: 'at' (isoformat), 'in' (relative, e.g. '1m', '30s'), 'every' (recurring, e.g. '1h'), 'cron' (expression).
    - payload_kind: 'message' (send content to user), 'prompt' (ask agent content), 'skill' (run skill_name with args).
    - session_id: The session ID this task belongs to (defaults to cli-default).
    """
    try:
        job = Job(
            name=name,
            schedule=JobSchedule(kind=schedule_kind, value=schedule_value),
            payload=JobPayload(kind=payload_kind, content=content, skill_name=skill_name, args=args),
            session_id=session_id
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
def list_tasks(session_id: str = "cli-default") -> str:
    """Lists all scheduled tasks for a specific session."""
    if not cron_manager.jobs:
        return "No tasks scheduled."
    
    tasks = []
    for name, job in cron_manager.jobs.items():
        if job.session_id == session_id:
            status = "Enabled" if job.enabled else "Disabled"
            tasks.append(f"- {name}: {job.schedule.kind}({job.schedule.value}) | {job.payload.kind} | Next run: {job.next_run} | {status}")
    
    if not tasks:
        return f"No tasks scheduled for session '{session_id}'."
        
    return "\n".join(tasks)

@skill
def delete_task(name: str, session_id: str = "cli-default") -> str:
    """Deletes a scheduled task by name for a specific session."""
    if name in cron_manager.jobs:
        job = cron_manager.jobs[name]
        if job.session_id == session_id:
            cron_manager.delete_job(name)
            return f"Task '{name}' deleted."
        else:
            return f"Task '{name}' found but belongs to a different session."
    else:
        return f"Task '{name}' not found."

@skill
def search_clawhub(query: str = "") -> str:
    """
    Searches ClawHub.ai for skills matching the query.
    Returns a list of skill slugs and descriptions.
    """
    url = "https://clawhub.ai/api/v1/skills"
    try:
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            
            if query:
                # Basic client-side filtering
                filtered = [i for i in items if query.lower() in i.get("slug", "").lower() or query.lower() in i.get("description", "").lower()]
            else:
                filtered = items[:10] # Show top 10 if no query
            
            if not filtered:
                return f"No skills found on ClawHub matching '{query}'."
            
            results = ["ClawHub Search Results:"]
            for i in filtered:
                slug = i.get('slug')
                desc = i.get('description', 'No description.')
                results.append(f"- {slug}: {desc}")
            
            return "\n".join(results)
    except Exception as e:
        return f"Error searching ClawHub: {e}"

@skill
def install_skill_from_clawhub(slug: str) -> str:
    """
    Downloads and installs a skill from ClawHub.ai by its slug.
    The skill will be saved as a SKILL.md file which provides instructions to the agent.
    WARNING: ClawHub skills are community-contributed; use with extreme caution.
    """
    url = f"https://auth.clawdhub.com/api/v1/download?slug={slug}"
    # Use consistent local skills directory in CWD
    skills_dir = os.path.join(os.getcwd(), "skills", "clawhub", slug)
    
    try:
        if not os.path.exists(skills_dir):
            os.makedirs(skills_dir)
            
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(skills_dir)
        
        skill_file = os.path.join(skills_dir, "SKILL.md")
        if os.path.exists(skill_file):
            with open(skill_file, "r") as f:
                content = f.read()
            return f"Successfully installed ClawHub skill '{slug}'.\n\n--- SKILL.md ---\n{content}"
        else:
            return f"Successfully installed ClawHub skill '{slug}' but no SKILL.md was found in the archive."
            
    except Exception as e:
        return f"Error installing skill from ClawHub: {e}"
