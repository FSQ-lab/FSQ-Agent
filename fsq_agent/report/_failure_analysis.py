from fsq_agent.models import StepResult, VerificationResult


class FailureAnalyzer:
    def classify(self, steps: list[StepResult], verification: VerificationResult) -> str:
        if verification.status == "success":
            return "success"
        if any(step.status == "failed" and step.error for step in steps):
            return "execution issue"
        if verification.status == "inconclusive":
            return "verification issue"
        return "planning issue"