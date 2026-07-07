def safe_float(val, default=0.0) -> float:
    """
    Safely converts a value to float. Returns default if conversion fails or val is None.
    """
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def evaluate_split_model_candidate(baseline: dict, candidate: dict) -> dict[str, object]:
    """
    Compares baseline and candidate split model metrics to determine if the candidate is eligible for promotion.
    
    Metrics evaluated:
    - excess_return_net (must improve, i.e., candidate > baseline)
    - max_drawdown_net (must not worsen, i.e., candidate >= baseline)
    - roc_auc (must not worsen, i.e., candidate >= baseline)
    - precision_at_top_10pct (must not worsen, i.e., candidate >= baseline)
    """
    if baseline is None:
        baseline = {}
    if candidate is None:
        candidate = {}

    # Define metrics and their check rules
    # Tuple format: (name_in_result, category, source_key, comparator, is_strict_improvement, default_val_if_missing)
    metric_rules = [
        ("composite_excess_return_net", "backtest_composite_summary", "excess_return_net", ">", True, 0.0),
        ("max_drawdown_net", "backtest_composite_summary", "max_drawdown_net", ">=", False, -1.0),
        ("risk_roc_auc", "risk_metrics", "roc_auc", ">=", False, 0.0),
        ("risk_precision_at_top_10pct", "risk_metrics", "precision_at_top_10pct", ">=", False, 0.0),
    ]

    checks = []
    all_passed = True
    baseline_summary = {}
    candidate_summary = {}

    for name, category, source_key, comparator, strict_improvement, default_val in metric_rules:
        # Safely extract from nested dictionaries
        baseline_cat = baseline.get(category, {})
        if not isinstance(baseline_cat, dict):
            baseline_cat = {}
        baseline_val = safe_float(baseline_cat.get(source_key), default_val)

        candidate_cat = candidate.get(category, {})
        if not isinstance(candidate_cat, dict):
            candidate_cat = {}
        candidate_val = safe_float(candidate_cat.get(source_key), default_val)

        if strict_improvement:
            passed = candidate_val > baseline_val
        else:
            passed = candidate_val >= baseline_val

        if not passed:
            all_passed = False

        checks.append({
            "name": name,
            "passed": passed,
            "baseline": baseline_val,
            "candidate": candidate_val,
            "comparator": comparator
        })

        baseline_summary[name] = baseline_val
        candidate_summary[name] = candidate_val

    return {
        "passed": all_passed,
        "checks": checks,
        "baseline": baseline_summary,
        "candidate": candidate_summary
    }

