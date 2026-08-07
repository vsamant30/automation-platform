import logging
import sys
import threading

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

project_root_string = str(PROJECT_ROOT)

if project_root_string not in sys.path:
    sys.path.insert(
        0,
        project_root_string,
    )

import servicemanager
import win32service
import win32serviceutil

from agents.windows_agent.config import (
    load_agent_settings,
)
from agents.windows_agent.main import (
    configure_logging,
    run_agent,
)


logger = logging.getLogger(
    "automation_platform_windows_agent_service"
)


class AutomationPlatformWindowsAgentService(
    win32serviceutil.ServiceFramework
):
    _svc_name_ = "AutomationPlatformWindowsAgent"
    _svc_display_name_ = (
        "Automation Platform Windows Agent"
    )
    _svc_description_ = (
        "Executes remote Automation Platform jobs "
        "on this Windows machine."
    )

    def __init__(
        self,
        args,
    ):
        super().__init__(args)

        self.stop_event = threading.Event()

    def SvcStop(self):
        self.ReportServiceStatus(
            win32service.SERVICE_STOP_PENDING
        )

        servicemanager.LogInfoMsg(
            (
                "Automation Platform Windows Agent "
                "service stop requested."
            )
        )

        self.stop_event.set()

    def SvcDoRun(self):
        servicemanager.LogInfoMsg(
            (
                "Automation Platform Windows Agent "
                "service started."
            )
        )

        try:
            configure_logging()

            settings = load_agent_settings()

            run_agent(
                settings=settings,
                stop_event=self.stop_event,
            )

        except Exception:
            logger.exception(
                "Windows Agent service failed."
            )

            servicemanager.LogErrorMsg(
                (
                    "Automation Platform Windows Agent "
                    "service failed."
                )
            )

            raise

        finally:
            servicemanager.LogInfoMsg(
                (
                    "Automation Platform Windows Agent "
                    "service stopped."
                )
            )


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(
        AutomationPlatformWindowsAgentService
    )