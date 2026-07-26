import platform
from datetime import datetime


def run_health_check_job():
    result = {
        "computer_name": platform.node(),
        "operating_system": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return (
        f"Health check completed. "
        f"Computer: {result['computer_name']}, "
        f"OS: {result['operating_system']}, "
        f"Python: {result['python_version']}, "
        f"Time: {result['checked_at']}"
    )