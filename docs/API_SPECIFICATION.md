# Instagram Reels Workout App — Complete REST API Specification

**Base URL**: `https://<api-id>.execute-api.ap-northeast-2.amazonaws.com` (AWS HTTP API)  
**Stage**: `/dev` (or `/prod`)  
**Protocol**: HTTPS  
**Content-Type**: `application/json`

---

## 1. Authentication & Security Headers

Every request from the iOS App and Share Extension must include:

| Header Name | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `Content-Type` | **Yes** | Payload format | `application/json` |
| `x-app-secret` | **Yes** | Shared client secret token configured in your app bundle | `your-private-app-secret-token` |
| `x-user-email` | **Yes** | Authenticated user email (from Sign in with Apple) | `dongik@example.com` |

> [!NOTE]
> If `x-user-email` is not in the server-side authorized whitelist (`ALLOWED_USER_EMAILS`), or if `x-app-secret` is invalid, the API immediately returns `403 Forbidden` without consuming OpenAI or AWS compute.

---

## 2. API Endpoints Catalog

| # | Method | Endpoint | Purpose | Lifecycle Stage |
| :-: | :---: | :--- | :--- | :--- |
| **1** | `POST` | `/reels` | Ingests Instagram Reel URL, starts background analysis | Ingestion |
| **2** | `GET` | `/jobs/{job_id}` | Polls AI background processing status | Polling |
| **3** | `GET` | `/programs/{program_id}` | Fetches full hierarchical workout program | Routine Detail |
| **4** | `GET` | `/programs` | Lists all saved routines (filter by `?creator=...`) | Library |
| **5** | `PUT` | `/programs/{program_id}` | Updates user-confirmed sets, weights, and rest timers | Customization |
| **6** | `DELETE` | `/programs/{program_id}` | Deletes a workout routine from database & storage | Library Cleanup |
| **7** | `POST` | `/programs/merge` | Merges multi-part series (Part 1, 2, 3) into 1 split | Series Stitching |
| **8** | `GET` | `/programs/{program_id}/next-session` | AI recommended working weights & progressive overload | Pre-Workout |
| **9** | `POST` | `/programs/{program_id}/coach-query` | Contextual AI strength coach Q&A and form guidance | Live Coaching |
| **10** | `POST` | `/exercises/substitute` | 3 AI biomechanically matched exercise alternatives | Mid-Workout Swap |
| **11** | `POST` | `/sessions` | Logs completed workout session (weight, reps, RPE) | Workout Tracking |
| **12** | `GET` | `/sessions` | Lists past workout session logs | Overload History |

---

## 3. Detailed Endpoint Specs

### 1. Ingest Instagram Reel (Asynchronous)
* **Method**: `POST`
* **Path**: `/reels`
* **Request Body**:
  ```json
  { "url": "https://www.instagram.com/reel/DccqEKJPPqR/" }
  ```
* **Response (`202 Accepted`)**:
  ```json
  {
    "success": true,
    "job_id": "job_a1b2c3d4e5f6",
    "reel_id": "DccqEKJPPqR",
    "status": "PROCESSING",
    "status_url": "/jobs/job_a1b2c3d4e5f6"
  }
  ```

---

### 2. Poll Ingestion Job Status
* **Method**: `GET`
* **Path**: `/jobs/{job_id}`
* **Response (`200 OK`)**:
  ```json
  {
    "job_id": "job_a1b2c3d4e5f6",
    "reel_id": "DccqEKJPPqR",
    "status": "COMPLETED",
    "program_id": "che-dan-sil-ppl-routine-part2",
    "confidence_score": 0.98,
    "created_at": 1771977000,
    "updated_at": 1771977014
  }
  ```

---

### 3. Get Hierarchical Workout Program
* **Method**: `GET`
* **Path**: `/programs/{program_id}`
* **Response (`200 OK`)**:
  ```json
  {
    "program_id": "che-dan-sil-ppl-routine-part2",
    "creator": "이정훈 | 운동루틴",
    "title": "체단실 루틴 2탄",
    "split_type": "PPL (Push/Pull/Legs)",
    "cycle_frequency": "6일 운동 1일 휴식",
    "program_data": {
      "days": [ ... ],
      "progression": { "overload_strategy": "..." },
      "audit": { "confidence_score": 0.98, "user_action_items": [ ... ] }
    }
  }
  ```

---

### 4. List Saved Programs
* **Method**: `GET`
* **Path**: `/programs?creator=이정훈&limit=20`
* **Response (`200 OK`)**:
  ```json
  {
    "count": 1,
    "programs": [
      {
        "program_id": "che-dan-sil-ppl-routine-part2",
        "title": "체단실 루틴 2탄",
        "creator": "이정훈 | 운동루틴",
        "split_type": "PPL (Push/Pull/Legs)",
        "created_at": 1771977014
      }
    ]
  }
  ```

---

### 5. Update / Confirm Custom Program
* **Method**: `PUT`
* **Path**: `/programs/{program_id}`
* **Request Body**: Full or partial `WorkoutProgram` JSON.
* **Response (`200 OK`)**: `{ "success": true, "program": { ... } }`

---

### 6. Delete Program
* **Method**: `DELETE`
* **Path**: `/programs/{program_id}`
* **Response (`200 OK`)**: `{ "success": true, "message": "Program deleted successfully." }`

---

### 7. Merge Series Programs (Part 1, Part 2, Part 3)
* **Method**: `POST`
* **Path**: `/programs/merge`
* **Request Body**:
  ```json
  {
    "program_ids": ["che-dan-sil-part1", "che-dan-sil-part2", "che-dan-sil-part3"],
    "title": "체단실 통합 3분할 루틴 (Part 1-3 완결)"
  }
  ```
* **Response (`201 Created`)**:
  ```json
  {
    "success": true,
    "merged_program_id": "merged_a1b2c3d4e5",
    "program": { ... }
  }
  ```

---

### 8. AI Progressive Overload & Weight Calculator
* **Method**: `GET`
* **Path**: `/programs/{program_id}/next-session?day_number=1`
* **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "program_id": "che-dan-sil-ppl-routine-part2",
    "day_number": 1,
    "day_title": "Day 1: 푸쉬",
    "overload_summary": "지난주 벤치프레스 12회 완료로 +2.5kg 증량 추천",
    "exercise_recommendations": [
      {
        "exercise_id": "bench_press",
        "exercise_name": "벤치프레스",
        "last_weight_kg": 80.0,
        "recommended_weight_kg": 82.5,
        "target_sets": 5,
        "target_reps": "8-10 reps",
        "target_rpe": 8.5,
        "progression_note": "지난 세션 80kg x 12회 RPE 7.5를 초과 달성했으므로 +2.5kg 증량합니다."
      }
    ]
  }
  ```

---

### 9. In-Routine AI Coaching Query
* **Method**: `POST`
* **Path**: `/programs/{program_id}/coach-query`
* **Request Body**:
  ```json
  {
    "question": "어깨 충돌 증후군이 약간 있는데, 오늘 1일차 루틴에서 사레레 할 때 주의할 점이나 대체할 각도가 있나요?"
  }
  ```
* **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "program_id": "che-dan-sil-ppl-routine-part2",
    "question": "어깨 충돌 증후군...",
    "answer": "견봉 하 공간을 확보하기 위해 팔을 완전한 측면(0도)이 아닌 견갑골 평면(Scaption, 전방 30도) 방향으로 들어 올리세요. 덤벨을 엄지가 살짝 위를 향하게 잡으면 극상근 건의 마찰을 줄일 수 있습니다.",
    "suggested_action_items": [
      "스캡션(전방 30도) 각도로 사이드 레터럴 레이즈 수행",
      "팔꿈치 높이를 어깨 높이 이하로 제한"
    ]
  }
  ```

---

### 10. AI Exercise Substitution (Swap)
* **Method**: `POST`
* **Path**: `/exercises/substitute`
* **Request Body**:
  ```json
  {
    "exercise_name": "인클라인 해머 스트렝스 프레스",
    "target_muscle": "가슴 (상부 대흉근)",
    "preferred_equipment": ["Dumbbell", "Cable"]
  }
  ```
* **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "original_exercise": "인클라인 해머 스트렝스 프레스",
    "target_muscle": "가슴 (상부 대흉근)",
    "substitutes": [
      {
        "exercise_name": "인클라인 덤벨 프레스 (Incline Dumbbell Press)",
        "equipment": "Dumbbell (덤벨)",
        "target_muscle": "가슴 (상부 대흉근)",
        "rationale": "30도 벤치 각도로 동일한 상부 쇄골두 섬유 방향을 타겟합니다.",
        "recommended_volume": "3-4세트 × 8-12회"
      },
      {
        "exercise_name": "케이블 로우-투-하이 플라이 (Low-to-High Cable Fly)",
        "equipment": "Cable (케이블)",
        "target_muscle": "가슴 (상부 대흉근)",
        "rationale": "케이블의 지속적인 수렴 장력으로 상부 가슴 안쪽 자극을 극대화합니다.",
        "recommended_volume": "3-4세트 × 12-15회"
      }
    ]
  }
  ```

---

### 11. Log Live Workout Session
* **Method**: `POST`
* **Path**: `/sessions`
* **Request Body**:
  ```json
  {
    "program_id": "che-dan-sil-ppl-routine-part2",
    "day_number": 1,
    "logged_at": 1771979000,
    "duration_seconds": 3600,
    "completed_exercises": [
      {
        "exercise_id": "bench_press",
        "exercise_name": "벤치프레스",
        "sets": [
          { "set_number": 1, "weight_kg": 80.0, "reps": 10, "rpe": 8.0, "completed": true },
          { "set_number": 2, "weight_kg": 80.0, "reps": 10, "rpe": 8.5, "completed": true }
        ]
      }
    ],
    "session_notes": "컨디션 좋았음."
  }
  ```
* **Response (`201 Created`)**: `{ "success": true, "session_id": "session_8f9e0d1c2b3a" }`

---

### 12. List Workout History
* **Method**: `GET`
* **Path**: `/sessions?program_id=che-dan-sil-ppl-routine-part2&limit=50`
* **Response (`200 OK`)**: List of logged workout sessions.
