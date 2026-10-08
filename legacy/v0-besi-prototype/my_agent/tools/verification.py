from google.adk.tools import ToolContext


def exit_verification_loop(tool_context: ToolContext, message: str = "Loop exited"):
    """Call this to exit the loop immediately.

    Args:
        message: The final response message to show to the user.
    """
    print(f"[Loop] Exiting with message: {message}")
    tool_context.actions.escalate = True
    return message


def ask_user_approval(tool_context: ToolContext, plan_summary: str):
    """Presents the search plan to the user for approval.

    Args:
        plan_summary: A human-readable summary of the proposed search strategy.
    """
    print("[Planner] Proposing plan to user...")
    tool_context.actions.escalate = True
    return f"I have created a search plan:\n\n{plan_summary}\n\nDo you approve this plan? (Type 'yes' to proceed, or explain changes)"
