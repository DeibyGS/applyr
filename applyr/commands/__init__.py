"""Re-export all cmd_* functions from sub-modules."""

from applyr.commands.core import (
    cmd_init,
    cmd_setup_agent,
    cmd_add,
    cmd_list,
    cmd_show,
    cmd_update,
    cmd_delete,
    cmd_search,
)
from applyr.commands.analytics import (
    cmd_pipeline,
    cmd_stats,
    cmd_gaps,
    cmd_followups,
    cmd_trends,
    cmd_summary,
    cmd_compare,
    cmd_plan,
    cmd_salary,
    cmd_gaps_save,
    cmd_gaps_list,
    cmd_gaps_stats,
)
from applyr.commands.workflow import cmd_export, cmd_doctor, cmd_cv_stats

__all__ = [
    "cmd_cv_stats",
    "cmd_init",
    "cmd_setup_agent",
    "cmd_add",
    "cmd_list",
    "cmd_show",
    "cmd_update",
    "cmd_delete",
    "cmd_search",
    "cmd_pipeline",
    "cmd_stats",
    "cmd_gaps",
    "cmd_followups",
    "cmd_trends",
    "cmd_summary",
    "cmd_compare",
    "cmd_plan",
    "cmd_salary",
    "cmd_gaps_save",
    "cmd_gaps_list",
    "cmd_gaps_stats",
    "cmd_export",
    "cmd_doctor",
]
