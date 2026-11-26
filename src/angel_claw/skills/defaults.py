"""Which skill modules are exposed to the model by default.

A default install should not hand the model credentials-dependent or
redundant integrations it cannot use yet: sending mail, Google Calendar,
mobile-bridge commands, cross-account messages and weather all need setup
that a fresh account does not have.  They stay installed and can be switched
on from Settings -> Skills (or ``skill_config.json``).

Everything else - local calendar, todos, reminders, memory, files and the web
tools - works without external accounts and is enabled by default.
"""

# Tools in these modules are part of every prompt. Everything else is
# enabled but its tool schemas are loaded on demand with load_skill_tools,
# so a 60-tool install does not spend context on tools a chat never uses.
EAGER_MODULES = frozenset(
    {
        "calendar",
        "core",
        "memory_ops",
        "reminder",
        "todo",
        "web",
    }
)

DEFAULT_DISABLED_MODULES = frozenset(
    {
        "email",
        "get_weather",
        "google_calendar",
        "messaging",
        "mobile",
    }
)

MODULE_DESCRIPTIONS = {
    "browser": "Drive a real browser: open pages, click, type, screenshot",
    "calendar": "Local calendar events and availability",
    "core": "Scheduling, chat history and skill management",
    "email": "Send mail through your SMTP account",
    "file_handler": "Uploaded files, PDFs and images",
    "get_weather": "Weather lookup (needs an OpenWeather key)",
    "google_calendar": "Google Calendar integration",
    "memory_ops": "Long-term memory: store and search",
    "messaging": "Internal messages between accounts",
    "mobile": "Mobile device alarms, apps and commands",
    "reminder": "One-off reminders delivered when due",
    "todo": "Personal to-do lists",
    "web": "Web search and readable page fetching",
}


def module_enabled(config: dict, module: str) -> bool:
    """A module is enabled unless explicitly disabled or disabled by default."""
    entry = config.get(module)
    if isinstance(entry, dict) and "disabled" in entry:
        return not bool(entry["disabled"])
    return module not in DEFAULT_DISABLED_MODULES


def tool_enabled(config: dict, module: str, tool: str) -> bool:
    """Tools follow their module, plus legacy per-tool disable flags."""
    entry = config.get(tool)
    if isinstance(entry, dict) and entry.get("disabled"):
        return False
    return module_enabled(config, module)


def clear_legacy_tool_disables(config: dict, tools) -> None:
    """Drop old per-tool disables when their module is enabled.

    Older builds exposed both module and individual tool switches. The current
    Settings page only has module switches, so leaving a hidden tool disable in
    place makes the enabled module look broken. Field values are untouched.
    """
    for tool in tools:
        entry = config.get(tool)
        if not isinstance(entry, dict):
            continue
        entry.pop("disabled", None)
        if not entry:
            config.pop(tool, None)
