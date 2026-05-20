# cloud.jsangho

문서·실습 코드 등을 한곳에 모아 둔 **워크스페이스**다. 하위에 `kayfabe/`(예: `gorilla/jsangho` 앱), `docs/`(Obsidian 등 노트) 등이 있다.

---

## AI 보조 코딩 하네스

이 저장소는 Cursor 등으로 LLM을 쓸 때 **규칙 + 검증 루프**를 먼저 걸어 두는 **하네스 엔지니어링**을 전제로 한다. 철학은 [Andrej Karpathy의 LLM 코딩 관찰](https://x.com/karpathy/status/2015883857489522876)과 맞춘다: **가정을 숨기지 않고**, **요청 범위의 최소 코드·최소 diff**로, **끝났다고 말할 수 있는 검증**까지 잡는다.

| 문서 | 용도 |
|------|------|
| [`../docs/README.md`](../docs/README.md) | **업무별 코딩 규칙 인덱스**(Frontend/Backend). 구현 전 필수. |
| [`CLAUDE.md`](CLAUDE.md) | 위 원칙의 **전체** 한글판(Think Before Coding, 단순성, 정밀 수정, 목표 중심 실행). |
| [`.cursorrules`](.cursorrules) | Cursor가 매 세션 읽는 **짧은 레일** + **`docs/` 읽기 의무**. |
| [`CURSOR.md`](CURSOR.md) | Cursor에서 `@` 컨텍스트·우선순위 등 **IDE에 붙이는 방법**. |

새 기여자는 **이 README → `../docs/README.md` → `CURSOR.md` → `CLAUDE.md`** 순으로 읽으면 하네스 전체를 잡을 수 있다.

---

## 관련 링크

- Karpathy 원문 맥락: <https://x.com/karpathy/status/2015883857489522876>
