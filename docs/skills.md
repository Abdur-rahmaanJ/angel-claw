# Angel Claw Skills

Skills are functional tools that Angel Claw can use to perform specific tasks. They are implemented as Python functions decorated with `@skill`.

## Using Skills

### Listing Skills
To see what skills Angel Claw currently has, ask:
- "What skills do you have?"
- "List my available tools."

### Creating New Skills
Angel Claw can autonomously create its own skills. Simply describe what you want the tool to do:
- "Create a skill named 'greet' that takes a name and returns 'Hello, {name}!'."
- "Implement a tool that calculates the square root of a number."

The assistant will generate the Python code, save it in `src/angel_claw/skills/`, and the tool will be available for use immediately in the same session.

## Skill Storage and Structure

All active skills are stored in:
`src/angel_claw/skills/`

### Manual Skill Definition
You can also manually add skills by creating a new `.py` file in the skills directory:

```python
@skill
def my_custom_tool(param1: str) -> str:
    """Description for the assistant."""
    return f"Processed: {param1}"
```
*Note: The `@skill` decorator is automatically injected into the module's namespace by the `SkillManager`, so you don't need to import it.*

## OpenClaw Skill Compatibility

Angel Claw can import skill definitions from Markdown files (`skill.md`), making it compatible with the OpenClaw ecosystem.

### Importing MD Skills
1. Create a subfolder in the root `skills/` directory (e.g., `skills/my-new-skill/`).
2. Add a `skill.md` file following the OpenClaw format (Title, Description, Tools, Parameters, Examples).
3. Ask the assistant to scan the directory:
   - "Scan my skills folder for new definitions."
   - "Implement the Weather Skill from my skills directory."

### Example `skill.md` Format:
```markdown
# Weather Skill

## Description
Provides real-time weather information.

## Tools

### get_weather
Get the current weather for a specific location.

**Parameters:**
- `location` (string, required): The city name.

## Examples
- "What is the weather in Paris?"
```

## Advanced Management

### GitHub Imports
You can install entire repositories of skills:
- "Install skills from https://github.com/example/my-skills-repo"

The assistant will clone the repo and copy all `.py` files containing skills into its internal skills directory.
