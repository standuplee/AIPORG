1. 임의 schema 추가 금지.
2. 기존 Pydantic model 이름 변경 금지.
3. Repository 외 직접 DB write 금지.
4. Collector에서 LLM 호출 금지.
5. Analyzer에서 웹 요청 금지.
6. Writer에서 새로운 fact 생성 금지.
7. numeric value는 evidence 없는 경우 생성 금지.
8. 모든 module 변경 시 unit test 작성.
9. integration test 실패 시 다음 기능 구현 금지.

## Codex ↔ Claude Code 작업 인계

- 이 저장소에서 작업을 시작할 때 루트 `HANDOFF.md`와 `git status`를 확인한다. 인계 문서는 요약이므로 실제 파일 상태와 사용자의 최신 요청을 우선한다.
- 의미 있는 작업 단계를 마칠 때, 다른 도구로 넘기기 전, 세션을 끝낼 때 `HANDOFF.md`의 현재 목표, 완료 작업, 변경 파일, 결정, 검증, 막힌 점, 다음 행동을 갱신한다. 긴 대화 기록을 붙이지 말고 오래된 상태를 교체한다.
- 기존 계획과 자세한 진행 기록은 `docs/superpowers/plans/2026-09-08-aiporg2-implementation.md`에 유지한다. 인계 문서에는 필요한 위치만 링크한다.
- 토큰, 비밀번호, 개인 정보, 채팅 원문을 기록하지 않는다. 동시 작업 중인 다른 에이전트의 변경을 덮어쓰지 않도록 수정 직전에 파일을 다시 읽는다.
