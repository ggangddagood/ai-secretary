phases/의 승인된 계획을 실행한다. 인자: task 이름 (없으면 phases/index.json의 pending task를 확인해 사용자에게 어떤 것을 실행할지 확인).

## 전제 확인

1. `phases/<task>/spec.md`와 step 파일들이 존재하고 사용자가 계획을 승인했는가. 아니면 /plan부터 안내.
2. git working tree가 clean한가. 아니면 중단하고 보고 — 무관한 변경이 실행·검증 경계에 섞이면 안 된다.
3. `feat-<task>` 브랜치로 checkout한다 (없으면 생성).

## step 실행 루프

pending인 step을 순서대로:

1. step 파일의 "읽어야 할 파일"을 전부 읽는다. `spec.md`는 항상 읽는다.
2. 구현한다. **spec이 정본이다** — step 지시와 spec이 충돌하면 spec을 따른다. spec 자체가 잘못되었거나 불완전해 보이면 편한 해석으로 바꾸지 말고 멈춰서 사용자에게 확인한다.
3. AC 명령을 **실제로 실행하고 exit code를 캡처한다.**
   - 평가하지 못한 검사는 실패다. 명령이 assertion에 도달하기 전에 죽었거나, 서버를 관찰할 수 없거나, 결과를 확인할 방법이 없으면 "눈에 띄는 에러가 없다"는 이유로 성공을 추론하지 않는다.
4. `phases/<task>/index.json` 갱신:
   - 통과 → `"completed"` + `"summary"` (다음 step에 유용한 정보: 생성 파일, 핵심 결정)
   - 3회 자가 수정 후에도 실패 → `"error"` + `"error_message"` 기록, 중단하고 보고
   - 사용자 개입 필요(API 키, 인증, 수동 설정) → `"blocked"` + `"blocked_reason"` 기록, 즉시 중단
5. 커밋을 분리한다: 코드는 `feat(<task>): step N — <name>`, 메타데이터(phases/)는 `chore(<task>): step N output`.

## 완료 게이트 (모든 step 완료 후)

- `bash scripts/verify.sh` 전체 실행 — exit 0을 캡처한다. step별로 통과했더라도 통합 상태에서 다시 실행한다 (step 간 상호작용은 개별 검증이 보지 못한다).
- spec이 서버/서비스를 선언하면 런타임 스모크: 기동 → 헬스체크 또는 최소 요청 1건 → 2xx 확인 → 종료. 빌드 통과는 컴파일 증명일 뿐, 뜨고 응답하는지의 증명이 아니다.

## 하네스 갱신 (완료 게이트 통과 후)

계획이 아니라 **실제로 완료·검증된 변경** 기준으로:

- `docs/tracking/STATUS.md` — 매번. built와 verified를 구분해서 기록.
- `docs/ENGINEERING_NOTES.md` — 구현 중 발견한 비자명한 함정/메커니즘 (있을 때만)
- `docs/DECISIONS.md` — 실제 트레이드오프가 있었던 결정 (있을 때만)
- 이번 변경이 ARCHITECTURE/BUSINESS_RULES/STANDARDS/SECURITY/OPERATIONS의 기존 서술을 무효화했으면 그 문서를 갱신한다. **갱신은 양방향이다** — 새 내용 추가만이 아니라 stale해진 기존 문장 수정까지.
- 변경 범위 밖의 문서/코드 불일치는 여기서 고치지 않는다 → `docs/tracking/FINDINGS.md`에 기록.

## 보고

증거와 함께 보고한다: step별 결과, 실행한 검증 명령과 exit code, 갱신한 문서 목록. 실패/blocked로 끝났으면 마지막으로 증명된 상태를 명확히 알린다.

머지/푸시는 직접 하지 않는다 — 사용자가 결정한다.
