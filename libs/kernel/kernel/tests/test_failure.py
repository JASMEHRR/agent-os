from kernel.failure import FailureCategory, FailureClassifier

CLASSIFICATION_BOUND_SECONDS = 60.0


def test_classifies_within_bound():
    classifier = FailureClassifier()
    result = classifier.classify(TimeoutError("slow"), rule=lambda e: FailureCategory.TRANSIENT)
    assert result.category == FailureCategory.TRANSIENT
    assert result.response == "retry_with_backoff"
    assert result.elapsed_seconds < CLASSIFICATION_BOUND_SECONDS


def test_each_category_maps_to_response():
    classifier = FailureClassifier()
    expected = {
        FailureCategory.TRANSIENT: "retry_with_backoff",
        FailureCategory.DEGRADABLE: "degrade",
        FailureCategory.CRITICAL: "halt_and_escalate",
        FailureCategory.SECURITY: "isolate",
        FailureCategory.FINANCIAL: "freeze_budget",
    }
    for category, response in expected.items():

        def rule(e: Exception, c: FailureCategory = category) -> FailureCategory:
            return c

        result = classifier.classify(Exception(), rule=rule)
        assert result.response == response
