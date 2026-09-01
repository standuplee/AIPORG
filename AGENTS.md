1. 임의 schema 추가 금지.
2. 기존 Pydantic model 이름 변경 금지.
3. Repository 외 직접 DB write 금지.
4. Collector에서 LLM 호출 금지.
5. Analyzer에서 웹 요청 금지.
6. Writer에서 새로운 fact 생성 금지.
7. numeric value는 evidence 없는 경우 생성 금지.
8. 모든 module 변경 시 unit test 작성.
9. integration test 실패 시 다음 기능 구현 금지.
