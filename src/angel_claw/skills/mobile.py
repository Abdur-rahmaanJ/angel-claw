from angel_claw.skills.manager import skill
from angel_claw.mobile_bridge import queue_mobile_command
import logging

logger = logging.getLogger("angel-claw-mobile-skills")

@skill
def set_mobile_alarm(time: str, user_id: str = None) -> str:
    """
    Sets an alarm on the user's mobile device.
    
    Parameters:
    - time: The time for the alarm (e.g., "15:00", "7:30 AM")
    - user_id: The current user ID (automatically injected)
    """
    if not user_id:
        return "Error: User ID not found."
    
    # Queue the command for the Android app
    queue_mobile_command(user_id, "set_alarm", {"time": time})
    
    return f"⏰ I've sent a command to your mobile device to set an alarm for {time}."

@skill
def open_mobile_app(app_name: str, package_name: str = None, user_id: str = None) -> str:
    """
    Opens an app on the user's mobile device.
    
    Parameters:
    - app_name: The friendly name of the app
    - package_name: (Optional) The Android package name (e.g., "com.whatsapp")
    """
    if not user_id:
        return "Error: User ID not found."
        
    queue_mobile_command(user_id, "open_app", {"name": app_name, "package": package_name})
    return f"📱 Opening {app_name} on your phone."

@skill
def vibrate_mobile(duration_ms: int = 500, user_id: str = None) -> str:
    """
    Vibrates the user's mobile device.
    
    Parameters:
    - duration_ms: The duration of the vibration in milliseconds (default 500)
    """
    if not user_id:
        return "Error: User ID not found."
        
    queue_mobile_command(user_id, "vibrate", {"duration": str(duration_ms)})
    return "📳 Buzz! I've vibrated your phone."
