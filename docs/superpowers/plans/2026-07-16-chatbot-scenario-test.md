# 챗봇 시나리오 통합 성능 진단 스크립트 구현 계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 챗봇의 핵심 비즈니스 시나리오 7가지를 가상으로 기동하여 도구 매핑 정확도, 파라미터 바인딩 정밀도 및 한국어 종목명 복원율을 정량 평가하는 성능 진단 스크립트와 리포트 생성기를 구축합니다.

**Architecture:** Flask Application Context 하에서 `ChatbotService`를 기동하고, LLM Function Calling 실행 단계에 임시로 인터셉터 데코레이터(Wrapper)를 장착하여 추출된 arguments와 기대값을 비교 진단한 뒤 마크다운 리포트를 자동 적재합니다.

**Tech Stack:** Python 3.13, Flask, Pytest, Supabase client.

## Global Constraints
- 모든 분석 및 출력 보고서는 반드시 한국어로 작성합니다. (코드 및 테스트 모듈은 영문 표준)
- 챗봇의 기본 거래소 매핑 규칙(가상자산: COINONE, 주식: TOSS)을 준수하여 검증합니다.
- TDD 프로세스를 준수합니다. (Failing test -> Run and fail -> Implement -> Run and pass -> Commit)

---

### Task 1: 테스트 인터셉터 및 시나리오 검증기 헬퍼 구현

**Files:**
- Create: `backend/scripts/run_chatbot_scenario_test.py`
- Create: `backend/tests/test_run_chatbot_scenario_test.py`

**Interfaces:**
- Produces: `make_test_interceptor(original_func)` 데코레이터, `evaluate_scenario(captured_call, expected)` 검증 함수.

- [ ] **Step 1: 실패하는 단위 테스트 작성**
  `backend/tests/test_run_chatbot_scenario_test.py` 에 인터셉터가 호출을 가로채서 인자를 수집하고, `evaluate_scenario`가 기대값과 비교하여 올바른 판정을 내리는지 검사하는 실패하는 테스트 코드를 작성합니다.

  ```python
  # backend/tests/test_run_chatbot_scenario_test.py
  import pytest
  from backend.scripts.run_chatbot_scenario_test import make_test_interceptor, evaluate_scenario

  def test_interceptor_captures_arguments():
      captured = []
      def dummy_tool(auth_header, message, **kwargs):
          return {"success": True}
      
      wrapped = make_test_interceptor(dummy_tool, captured)
      wrapped("Bearer test", "msg", exchange="COINONE", query="BTC")
      
      assert len(captured) == 1
      assert captured[0]["exchange"] == "COINONE"
      assert captured[0]["query"] == "BTC"

  def test_evaluate_scenario_passes_on_exact_match():
      captured = {"tool_name": "get_asset_price", "arguments": {"query": "BTC", "exchange": "COINONE"}}
      expected = {"tool_name": "get_asset_price", "arguments": {"query": "BTC", "exchange": "COINONE"}}
      result = evaluate_scenario(captured, expected)
      assert result["status"] == "PASS"

  def test_evaluate_scenario_fails_on_mismatch():
      captured = {"tool_name": "get_asset_price", "arguments": {"query": "XRP", "exchange": "COINONE"}}
      expected = {"tool_name": "get_asset_price", "arguments": {"query": "BTC", "exchange": "COINONE"}}
      result = evaluate_scenario(captured, expected)
      assert result["status"] == "FAIL"
  ```

- [ ] **Step 2: 테스트를 실행하여 실패하는지 확인**
  실행: `PYTHONPATH=. uv run pytest backend/tests/test_run_chatbot_scenario_test.py`
  기대결과: FAIL (ImportError 및 함수 정의 미비로 실패)

- [ ] **Step 3: 최소한의 코드로 구현 작성**
  `backend/scripts/run_chatbot_scenario_test.py` 에 테스트를 통과시킬 최소한의 인터셉터 및 검증 함수 구현을 작성합니다.

  ```python
  # backend/scripts/run_chatbot_scenario_test.py
  def make_test_interceptor(original_func, captured_list):
      def wrapper(auth_header, message, **kwargs):
          captured_list.append(kwargs)
          return original_func(auth_header, message, **kwargs)
      return wrapper

  def evaluate_scenario(captured: dict, expected: dict) -> dict:
      tool_match = captured.get("tool_name") == expected.get("tool_name")
      
      cap_args = captured.get("arguments") or {}
      exp_args = expected.get("arguments") or {}
      args_match = True
      for k, v in exp_args.items():
          if cap_args.get(k) != v:
              args_match = False
              break
              
      status = "PASS" if (tool_match and args_match) else "FAIL"
      return {
          "status": status,
          "tool_match": tool_match,
          "args_match": args_match
      }
  ```

- [ ] **Step 4: 테스트를 실행하여 패스하는지 확인**
  실행: `PYTHONPATH=. uv run pytest backend/tests/test_run_chatbot_scenario_test.py`
  기대결과: PASS

- [ ] **Step 5: 커밋 실행**
  ```bash
  git add backend/scripts/run_chatbot_scenario_test.py backend/tests/test_run_chatbot_scenario_test.py
  git commit -m "test: 챗봇 성능진단 인터셉터 및 검증기 헬퍼 구현 및 테스트 완료"
  ```

---

### Task 2: 7대 시나리오 실행 루프 및 마크다운 리포트 생성기 구현

**Files:**
- Modify: `backend/scripts/run_chatbot_scenario_test.py`
- Modify: `backend/tests/test_run_chatbot_scenario_test.py`

**Interfaces:**
- Produces: `generate_report(results)` 리포트 파일 적재 함수, `run_test_suite()` 전체 구동 함수.

- [ ] **Step 1: 실패하는 단위 테스트 작성**
  `backend/tests/test_run_chatbot_scenario_test.py` 에 리포트 작성 기능과 성공률 계산이 정확히 수치화되는지 검증하는 실패하는 테스트를 추가합니다.

  ```python
  # backend/tests/test_run_chatbot_scenario_test.py 에 추가
  from backend.scripts.run_chatbot_scenario_test import calculate_metrics, generate_report
  import os

  def test_calculate_metrics_accuracy():
      results = [
          {"status": "PASS"},
          {"status": "PASS"},
          {"status": "FAIL"},
      ]
      metrics = calculate_metrics(results)
      assert metrics["total"] == 3
      assert metrics["passed"] == 2
      assert metrics["failed"] == 1
      assert metrics["success_rate"] == pytest.approx(66.67, 0.01)

  def test_generate_report_creates_markdown_file(tmp_path):
      test_results = [{"scenario_id": 1, "input": "test input", "status": "PASS", "details": "Success"}]
      test_metrics = {"total": 1, "passed": 1, "failed": 0, "success_rate": 100.0}
      
      report_dir = tmp_path / "specs"
      report_dir.mkdir()
      report_path = report_dir / "2026-07-16-chatbot-scenario-test-result.md"
      
      generate_report(test_results, test_metrics, str(report_path))
      
      assert report_path.exists()
      content = report_path.read_text(encoding="utf-8")
      assert "총 테스트 케이스: 1" in content
      assert "성공률: 100.0%" in content
  ```

- [ ] **Step 2: 테스트를 실행하여 실패하는지 확인**
  실행: `PYTHONPATH=. uv run pytest backend/tests/test_run_chatbot_scenario_test.py`
  기대결과: FAIL (calculate_metrics 및 generate_report 함수 부재)

- [ ] **Step 3: 최소한의 코드로 구현 작성**
  `backend/scripts/run_chatbot_scenario_test.py` 에 테스트를 패스할 계산 헬퍼 및 마크다운 출력 기능을 완수하고 시나리오 구동 루프 `run_test_suite`를 설계합니다.

  ```python
  # backend/scripts/run_chatbot_scenario_test.py 에 구현 추가
  import json
  import time
  from datetime import datetime, timezone

  def calculate_metrics(results: list) -> dict:
      total = len(results)
      passed = sum(1 for r in results if r["status"] == "PASS")
      failed = total - passed
      success_rate = (passed / total * 100) if total > 0 else 0.0
      return {
          "total": total,
          "passed": passed,
          "failed": failed,
          "success_rate": round(success_rate, 2)
      }

  def generate_report(results: list, metrics: dict, filepath: str) -> None:
      now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
      lines = [
          "# 챗봇 시나리오 통합 성능 진단 결과 보고서",
          f"\n* **진단 시간**: {now_str}",
          f"* **총 테스트 케이스**: {metrics['total']}개",
          f"* **통과**: {metrics['passed']}개",
          f"* **실패**: {metrics['failed']}개",
          f"* **최종 성공률**: {metrics['success_rate']}%\n",
          "## 1. 시나리오별 검증 세부 내역",
          "| 번호 | 발화 (Input) | 결과 | 세부 판정 |",
          "| :--- | :--- | :--- | :--- |"
      ]
      for r in results:
          lines.append(f"| {r['scenario_id']} | \"{r['input']}\" | **{r['status']}** | {r.get('details') or ''} |")
      
      with open(filepath, "w", encoding="utf-8") as f:
          f.write("\n".join(lines))

  def run_test_suite():
      # 실제 7대 시나리오를 구동하는 메인 스크립트 로직 (App context 바인딩 등 포함)
      pass
  ```

- [ ] **Step 4: 테스트를 실행하여 패스하는지 확인**
  실행: `PYTHONPATH=. uv run pytest backend/tests/test_run_chatbot_scenario_test.py`
  기대결과: PASS

- [ ] **Step 5: 커밋 실행**
  ```bash
  git add backend/scripts/run_chatbot_scenario_test.py backend/tests/test_run_chatbot_scenario_test.py
  git commit -m "feat: 챗봇 시나리오 실행 메트릭 계산 및 마크다운 리포터 기능 구현 완료"
  ```
