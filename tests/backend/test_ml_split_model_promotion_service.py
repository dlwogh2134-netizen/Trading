from backend.services.ml_split_model_promotion_service import evaluate_split_model_candidate

def test_promotion_passed_when_better_or_equal():
    # Scenario 1: Candidate shows better returns, improved MDD, improved AUC, and better precision
    baseline = {
        "backtest_composite_summary": {
            "excess_return_net": 0.05,
            "max_drawdown_net": -0.15,
        },
        "risk_metrics": {
            "roc_auc": 0.60,
            "precision_at_top_10pct": 0.12
        }
    }
    candidate = {
        "backtest_composite_summary": {
            "excess_return_net": 0.08,
            "max_drawdown_net": -0.12,
        },
        "risk_metrics": {
            "roc_auc": 0.62,
            "precision_at_top_10pct": 0.15
        }
    }
    
    result = evaluate_split_model_candidate(baseline, candidate)
    
    assert result["passed"] is True
    assert len(result["checks"]) == 4
    for check in result["checks"]:
        assert check["passed"] is True
        assert "name" in check
        assert "metric" not in check

    # Verify baseline and candidate summaries in the result
    assert "baseline" in result
    assert "candidate" in result
    assert result["baseline"]["composite_excess_return_net"] == 0.05
    assert result["baseline"]["max_drawdown_net"] == -0.15
    assert result["baseline"]["risk_roc_auc"] == 0.60
    assert result["baseline"]["risk_precision_at_top_10pct"] == 0.12

    assert result["candidate"]["composite_excess_return_net"] == 0.08
    assert result["candidate"]["max_drawdown_net"] == -0.12
    assert result["candidate"]["risk_roc_auc"] == 0.62
    assert result["candidate"]["risk_precision_at_top_10pct"] == 0.15

    # Scenario 2: Candidate has equal risk and metrics, but improved return (which is the only > requirement)
    candidate_equal_risk = {
        "backtest_composite_summary": {
            "excess_return_net": 0.06,  # improved
            "max_drawdown_net": -0.15,   # equal
        },
        "risk_metrics": {
            "roc_auc": 0.60,             # equal
            "precision_at_top_10pct": 0.12  # equal
        }
    }
    result_equal = evaluate_split_model_candidate(baseline, candidate_equal_risk)
    assert result_equal["passed"] is True
    for check in result_equal["checks"]:
        assert check["passed"] is True


def test_promotion_failed_when_metrics_worsened():
    baseline = {
        "backtest_composite_summary": {
            "excess_return_net": 0.05,
            "max_drawdown_net": -0.15,
        },
        "risk_metrics": {
            "roc_auc": 0.60,
            "precision_at_top_10pct": 0.12
        }
    }

    # Scenario 1: Max drawdown worsened (more negative)
    candidate_bad_mdd = {
        "backtest_composite_summary": {
            "excess_return_net": 0.08,
            "max_drawdown_net": -0.18,  # worsened
        },
        "risk_metrics": {
            "roc_auc": 0.62,
            "precision_at_top_10pct": 0.15
        }
    }
    result = evaluate_split_model_candidate(baseline, candidate_bad_mdd)
    assert result["passed"] is False
    mdd_check = next(c for c in result["checks"] if c["name"] == "max_drawdown_net")
    assert mdd_check["passed"] is False

    # Scenario 2: Excess return did not improve (equal to baseline)
    candidate_equal_return = {
        "backtest_composite_summary": {
            "excess_return_net": 0.05,  # must be strictly improved (> baseline)
            "max_drawdown_net": -0.12,
        },
        "risk_metrics": {
            "roc_auc": 0.62,
            "precision_at_top_10pct": 0.15
        }
    }
    result = evaluate_split_model_candidate(baseline, candidate_equal_return)
    assert result["passed"] is False
    return_check = next(c for c in result["checks"] if c["name"] == "composite_excess_return_net")
    assert return_check["passed"] is False

    # Scenario 3: ROC AUC worsened
    candidate_bad_auc = {
        "backtest_composite_summary": {
            "excess_return_net": 0.08,
            "max_drawdown_net": -0.12,
        },
        "risk_metrics": {
            "roc_auc": 0.58,  # worsened
            "precision_at_top_10pct": 0.15
        }
    }
    result = evaluate_split_model_candidate(baseline, candidate_bad_auc)
    assert result["passed"] is False
    auc_check = next(c for c in result["checks"] if c["name"] == "risk_roc_auc")
    assert auc_check["passed"] is False

    # Scenario 4: Precision worsened
    candidate_bad_precision = {
        "backtest_composite_summary": {
            "excess_return_net": 0.08,
            "max_drawdown_net": -0.12,
        },
        "risk_metrics": {
            "roc_auc": 0.62,
            "precision_at_top_10pct": 0.10  # worsened
        }
    }
    result = evaluate_split_model_candidate(baseline, candidate_bad_precision)
    assert result["passed"] is False
    precision_check = next(c for c in result["checks"] if c["name"] == "risk_precision_at_top_10pct")
    assert precision_check["passed"] is False

