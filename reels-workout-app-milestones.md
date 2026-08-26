# 릴스 운동 앱 — 프로젝트 마일스톤

## 프로젝트 개요
인스타그램 릴스를 앱에 공유하면 AI가 운동 루틴(세트/횟수/분할)을 자동 분석해 저장하고,
릴스 출처별/시기별로 루틴을 모아 트래킹·비교할 수 있는 개인용 모바일 앱.

**확정된 방향**
- 백엔드: AWS 기반
- MVP 범위: 처음부터 AI 자동 분석(음성 STT + 캡션 텍스트 파싱) 포함
- 수익성 고려 안 함 (본인 사용 목적, 추후 검토)
- 데이터 확보 전략: 영상 다운로드(yt-dlp) → 실패 시 캡션 텍스트 → 그것도 부족하면 수동 입력, 3단 폴백

---

## Phase 0. 백엔드 실현 가능성 검증 (Baseline)
> 목표: 앱을 만들기 전에 핵심 리스크(영상 다운로드 가능 여부)부터 확인

- [x] 릴스 URL 1개로 시작하는 테스트 스크립트 작성
- [x] `yt-dlp`로 릴스 다운로드 가능 여부 확인 (가장 큰 리스크 지점)
- [x] `ffmpeg`로 오디오 추출
- [x] STT (AWS Transcribe 또는 Whisper API)로 음성 → 텍스트 변환 확인
- [x] oEmbed API로 캡션 텍스트 별도 확보 확인
- [x] STT 텍스트 + 캡션을 LLM(OpenAI/Whisper/GPT-4o)에 넣어 세트/횟수/분할 JSON 파싱 테스트
- [x] 결과 판단: 다운로드 안정성, 파싱 정확도, 실패율 정리 → Phase 1 진행 준비 완료

**Exit 조건**: 릴스 URL → 구조화된 운동 데이터(JSON)까지 최소 몇 개 샘플로 성공적으로 나오는지 확인

---

## Phase 1. 백엔드 코어 파이프라인 (AWS Serverless Framework v4)
> 목표: Phase 0에서 검증한 로직을 정식 AWS 인프라(Serverless v4 + SQS + DynamoDB + S3)로 구축

- [x] Serverless Framework v4 매니페스트 (`serverless.yml`, AWS profile: `developer-dongik`, region: `ap-northeast-2`)
- [x] API Gateway + Lambda(ingest): `POST /reels` (202 비동기 즉시 응답)
- [x] SQS 기반 비동기 백그라운드 워커 Lambda (`processor.py`: yt-dlp → Whisper STT → gpt-5.4-mini → DynamoDB/S3)
- [x] S3: 미디어(오디오, 원본 JSON) 저장소 버킷 정의
- [x] DynamoDB: Single-Table Design (`ReelsWorkoutTable`, GSI1 Creator/Date, GSI2 Series/Day)
- [x] App Store 보안 가드 & 유저 화이트리스트 검증 모듈 (`src/auth/guard.py`)
- [x] Job 상태 조회 API (`GET /jobs/{job_id}`) 및 운동 프로그램 조회 API (`GET /programs/{id}`, `GET /programs`)
- [x] 맞춤형 루틴 수정/확정 API (`PUT /programs/{program_id}`)
- [x] 실시간 운동 세션 기록 및 히스토리 조회 API (`POST /sessions`, `GET /sessions`)
- [x] Boto3 DynamoDB/S3 클라이언트 및 Float-Decimal 변환기 테스트 통과 (11/11 pytest 통과)
- [x] 모바일 개발자 인수인계 문서 및 Swift 모델 정의 완료 (`docs/API_SPECIFICATION.md`, `docs/SWIFT_MODELS.swift`, `docs/IOS_SHARE_EXTENSION_GUIDE.md`)
- [ ] AWS 클라우드 배포 (`serverless deploy`) 및 E2E 라이브 엔드포인트 검증

---

## Phase 2. iOS 앱 스켈레톤
> 목표: 공유 → 서버 전송까지의 최소 플로우

- [ ] iOS Share Extension 구현 (릴스 URL 수신)
- [ ] Share Extension → 백엔드 API 호출
- [ ] 기본 앱 셸: 로그인(Cognito), 홈 화면, 릴스 리스트

---

## Phase 3. 부족 정보 입력 & 트래킹 UI
> 목표: AI 분석 결과를 사용자가 검토/보완하고 실제로 기록하는 흐름

- [ ] 파싱 결과 리뷰 화면 (빈 필드 하이라이트, 탭해서 채우기)
- [ ] 운동 세션 기록 UI (실제 수행한 세트/횟수/무게 입력)
- [ ] 릴스 메타데이터(계정, URL, 날짜) 저장 확인

---

## Phase 4. 시리즈/비교 기능
> 목표: 여러 릴스 루틴을 시기별로 묶어 비교

- [ ] 릴스를 시리즈로 그룹핑하는 UX (자동/수동 방식 결정 필요)
- [ ] 월별/시리즈별 루틴 비교 뷰
- [ ] 트래킹 기록과 연동한 진행 상황 시각화

---

## Phase 5. 안정화
- [ ] 인스타그램 구조 변경 대응 모니터링 (다운로드 실패율 추적)
- [ ] 에러 핸들링 및 폴백 UX 다듬기
- [ ] 실사용 테스트 및 버그 수정

---

## 미해결 질문 (진행하며 결정 필요)
- 시리즈 그룹핑을 자동(계정 단위)으로 할지, 사용자가 수동으로 묶을지
- 다운로드 실패 시 사용자에게 어떻게 안내할지 (즉시 알림 vs 조용히 캡션 폴백)
- Android 버전 확장 여부 및 시점
