from app.nodes import analyze_bugs, send_email_node


class BugReportPipeline:
    def run(self, bugs: str) -> dict:
        state = {"bugs": bugs}
        state.update(analyze_bugs(state))
        state.update(send_email_node(state))
        return state
