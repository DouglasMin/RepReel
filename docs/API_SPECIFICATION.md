# Instagram Reels Workout App — Complete REST API Specification

**Base URL**: `https://szcr4meit6.execute-api.ap-northeast-2.amazonaws.com` (AWS HTTP API)  
**Path Prefix**: None (Routes are served directly at the root `/`, e.g. `/programs`, `/reels`, `/sessions/active`)  
**Protocol**: HTTPS  
**Content-Type**: `application/json`

---

## 1. Authentication & Security Headers

Every request from the iOS App and Share Extension must include:

| Header Name | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `Content-Type` | **Yes** | Payload format | `application/json` |
| `x-app-secret` | **Yes** | Shared client secret token configured in your app bundle | `reels-workout-dev-secret-2026` |
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
| **11** | `PUT` | `/sessions/active` | Saves/updates in-progress workout draft (real-time checklists) | Live Tracking |
| **12** | `GET` | `/sessions/active` | Retrieves unfinished workout draft to prompt resume dialog | App Launch |
| **13** | `DELETE`| `/sessions/active` | Discards or cancels unfinished workout draft | Live Tracking |
| **14** | `POST` | `/sessions` | Logs completed workout session (auto-calculates total volume) | Workout Finish |
| **15** | `GET` | `/sessions` | Lists past workout session logs & volume history | Analytics |

---

## 3. Detailed Endpoint Specs

### 1. Ingest Instagram Reel (Asynchronous)
* **Method**: `POST`
* **Path**: `/reels`
* **Request Body**: `{ "url": "https://www.instagram.com/reel/DccqEKJPPqR/" }`
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
* **Response (`200 OK`)**: Full `WorkoutProgram` JSON.

---

### 4. List Saved Programs
* **Method**: `GET`
* **Path**: `/programs?creator=이정훈&limit=20`

---

### 5. Update / Confirm Custom Program
* **Method**: `PUT`
* **Path**: `/programs/{program_id}`
* **Request Body**: Updated `WorkoutProgram` JSON.

---

### 6. Delete Program
* **Method**: `DELETE`
* **Path**: `/programs/{program_id}`

---

### 7. Merge Series Programs (Part 1, 2, 3)
* **Method**: `POST`
* **Path**: `/programs/merge`
* **Request Body**:
  ```json
  {
    "program_ids": ["che-dan-sil-part1", "che-dan-sil-part2", "che-dan-sil-part3"],
    "title": "체단실 통합 3분할 루틴 (Part 1-3 완결)"
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
* **Request Body**: `{ "question": "어깨 충돌 증후군이 약간 있는데 사레레 시 주의점?" }`

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

---

### 11. Save In-Progress Workout Draft (Real-Time Checklist Sync)
* **Method**: `PUT`
* **Path**: `/sessions/active`
* **Headers**: `x-user-email: dongik@example.com`
* **Trigger**: Called in background whenever user checks a set or adjusts weights during gym workout.
* **Request Body**:
  ```json
  {
    "program_id": "che-dan-sil-ppl-routine-part2",
    "day_number": 1,
    "started_at": 1771979000,
    "completed_exercises": [
      {
        "exercise_id": "bench_press",
        "exercise_name": "벤치프레스",
        "sets": [
          { "set_number": 1, "weight_kg": 80.0, "reps": 10, "rpe": 8.0, "completed": true },
          { "set_number": 2, "weight_kg": 82.5, "reps": 8, "rpe": 8.5, "completed": true },
          { "set_number": 3, "weight_kg": 85.0, "reps": 8, "rpe": null, "completed": false }
        ]
      }
    ]
  }
  ```
* **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "active_session": {
      "user_id": "dongik@example.com",
      "program_id": "che-dan-sil-ppl-routine-part2",
      "day_number": 1,
      "volume_analytics": {
        "total_volume_kg": 1460.0,
        "total_sets_completed": 2,
        "total_reps_completed": 18
      }
    }
  }
  ```

---

### 12. Check / Resume In-Progress Workout Draft
* **Method**: `GET`
* **Path**: `/sessions/active`
* **Trigger**: Called upon app launch to show *"You have an unfinished workout. Resume?"*
* **Response (`200 OK` - Active Workout Found)**:
  ```json
  {
    "has_active_session": true,
    "active_session": {
      "user_id": "dongik@example.com",
      "program_id": "che-dan-sil-ppl-routine-part2",
      "day_number": 1,
      "started_at": 1771979000,
      "session_data": { ... }
    }
  }
  ```
* **Response (`404 Not Found` - No Workout In Progress)**:
  ```json
  {
    "has_active_session": false,
    "message": "No active workout in progress."
  }
  ```

---

### 13. Discard In-Progress Workout Draft
* **Method**: `DELETE`
* **Path**: `/sessions/active`
* **Trigger**: User clicks "운동 취소 / 삭제 (Discard Workout)".
* **Response (`200 OK`)**: `{ "success": true, "deleted": true }`

---

### 14. Log Completed Workout Session (Planfit Total Volume Report)
* **Method**: `POST`
* **Path**: `/sessions`
* **Trigger**: User taps "운동 끝내기 (Finish Workout)". Automatically computes total volume and deletes active draft.
* **Request Body**:
  ```json
  {
    "program_id": "che-dan-sil-ppl-routine-part2",
    "day_number": 1,
    "logged_at": 1771982600,
    "duration_seconds": 3600,
    "completed_exercises": [
      {
        "exercise_id": "bench_press",
        "exercise_name": "벤치프레스",
        "sets": [
          { "set_number": 1, "weight_kg": 80.0, "reps": 10, "rpe": 8.0, "completed": true },
          { "set_number": 2, "weight_kg": 82.5, "reps": 8, "rpe": 8.5, "completed": true },
          { "set_number": 3, "weight_kg": 85.0, "reps": 8, "rpe": 9.0, "completed": true },
          { "set_number": 4, "weight_kg": 85.0, "reps": 7, "rpe": 9.5, "completed": true },
          { "set_number": 5, "weight_kg": 80.0, "reps": 9, "rpe": 9.5, "completed": true }
        ]
      }
    ],
    "session_notes": "가슴 펌핑 최고였음. 85kg 2세트 성공."
  }
  ```
* **Response (`201 Created`)**:
  ```json
  {
    "success": true,
    "session_id": "session_8f9e0d1c2b3a",
    "session": {
      "session_id": "session_8f9e0d1c2b3a",
      "program_id": "che-dan-sil-ppl-routine-part2",
      "day_number": 1,
      "duration_seconds": 3600,
      "volume_analytics": {
        "total_volume_kg": 3555.0,
        "total_sets_completed": 5,
        "total_reps_completed": 42,
        "exercise_breakdown": [
          {
            "exercise_id": "bench_press",
            "exercise_name": "벤치프레스",
            "volume_kg": 3555.0,
            "completed_sets": 5,
            "completed_reps": 42,
            "top_set_weight_kg": 85.0,
            "estimated_1rm_kg": 107.7
          }
        ]
      }
    }
  }
  ```

---

### 15. List Workout History
* **Method**: `GET`
* **Path**: `/sessions?program_id=che-dan-sil-ppl-routine-part2&limit=50`
* **Response (`200 OK`)**: List of logged workout sessions with volume analytics.
