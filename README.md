# 🏋️‍♂️ RepReel — Instagram Reels & YouTube Shorts to Structured AI Workout Routines

[![CI/CD Status](https://github.com/DouglasMin/RepReel/actions/workflows/deploy.yml/badge.svg)](https://github.com/DouglasMin/RepReel/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![AWS](https://img.shields.io/badge/AWS-ECR%20%7C%20Lambda%20%7C%20DynamoDB%20%7C%20SQS-orange.svg)](https://aws.amazon.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--5.4%20mini-green.svg)](https://openai.com/)
[![Swift](https://img.shields.io/badge/Swift-6%20%7C%20SwiftUI-red.svg)](https://developer.apple.com/swift/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-2.0%20(Swagger)-informational.svg)](docs/openapi_2.0.yaml)

**RepReel** transforms short-form fitness videos (**Instagram Reels** and **YouTube Shorts**) into structured, actionable workout routines with progressive overload tracking, real-time set checklists, Planfit-style volume analytics, and intelligent 1-tap exercise substitutions.

---

## 🌐 Live AWS Cloud Infrastructure

* **API Gateway Base URL**: `https://szcr4meit6.execute-api.ap-northeast-2.amazonaws.com`
* **Region**: `ap-northeast-2` (Seoul)
* **Architecture**: Container-based Serverless (`Amazon ECR` + `AWS Lambda` + `DynamoDB` + `SQS` + `S3`)
* **AI Engine**: `gpt-5.4-mini` (OpenAI Structured Outputs) + High-Res OCR Vision Pipeline + Whisper STT

---

## 🚀 Key Features

1. **⚡ 0.3s Share Extension Ingestion**:
   * Intercepts Instagram and YouTube Shorts share sheet in iOS, detects source platform (`INSTAGRAM_REEL`, `YOUTUBE_SHORTS`), and enqueues background processing job asynchronously via SQS.
2. **🧠 Multi-Platform AI Extraction Pipeline**:
   * **YouTube Shorts**: Vision-first High-Res OCR pipeline to read video title cards, exercise names, and rep numbers accurately without hallucinating voiceover ads or background chatter.
   * **Instagram Reels**: Sequential Whisper STT + GPT-5.4 mini normalizing Korean gym slang (`아레베` $\rightarrow$ Side Lateral Raise) into clean exercise records.
3. **📊 Planfit-Style Live Workout & Volume Tracking**:
   * Real-time set checklist sync (`PUT /sessions/active`).
   * Unfinished workout resume prompt on app open (`GET /sessions/active`).
   * Auto-computes total tonnage lifted (`total_volume_kg`), completed sets/reps, and Epley-estimated 1RM.
4. **🔄 1-Tap Biomechanical Exercise Substitution**:
   * Suggests 3 matched alternatives for crowded or missing gym equipment (`POST /exercises/substitute`).
5. **📈 AI Progressive Overload Predictor**:
   * Predicts next session working weights based on historical DynamoDB logs (`GET /programs/{id}/next-session`).
6. **🔗 Multi-Reel Series Merger**:
   * Stitches multi-part series (Part 1, 2, 3) into a single unified split (`POST /programs/merge`).
7. **🔒 Production App Store Security**:
   * Protected with `x-app-secret` and `ALLOWED_USER_EMAILS` whitelist guard.

---

## 📡 REST API Catalog (17 Endpoints)

| # | Method | Endpoint | Description | Lifecycle Stage |
| :-: | :---: | :--- | :--- | :--- |
| **1** | `POST` | `/reels` | Ingest Instagram Reel or YouTube Shorts URL | Ingestion |
| **2** | `GET` | `/jobs/{job_id}` | Poll background AI processing status | Polling |
| **3** | `GET` | `/programs/{program_id}` | Fetch extracted workout program | Routine Detail |
| **4** | `GET` | `/programs` | List routines (by creator or latest) | Library |
| **5** | `PUT` | `/programs/{program_id}` | Confirm/edit routine sets, weights, and rest times | Customization |
| **6** | `DELETE` | `/programs/{program_id}` | Delete routine from library | Library Cleanup |
| **7** | `POST` | `/programs/merge` | Merge multi-part series into 1 split | Series Stitching |
| **8** | `GET` | `/programs/{program_id}/next-session` | AI Progressive Overload weight recommendations | Pre-Workout |
| **9** | `POST` | `/programs/{program_id}/coach-query` | Contextual AI strength coach Q&A | Live Coaching |
| **10** | `POST` | `/exercises/substitute` | 3 AI biomechanically matched exercise swaps | Mid-Workout Swap |
| **11** | `PUT` | `/sessions/active` | Real-time set checklist sync & weight saving | Live Tracking |
| **12** | `GET` | `/sessions/active` | Check/resume in-progress workout draft on app open | App Launch |
| **13** | `DELETE`| `/sessions/active` | Discard/cancel in-progress workout draft | Live Tracking |
| **14** | `POST` | `/sessions` | Finish workout (Planfit total volume & 1RM calculator) | Workout Finish |
| **15** | `GET` | `/sessions` | Query past workout session volume history | Analytics |
| **16** | `PUT` | `/sessions/{session_id}` | Edit logged past workout sets, reps, weights, or notes | History Edit |
| **17** | `DELETE`| `/sessions/{session_id}` | Delete a past workout session log permanently | History Cleanup |

---

## 📱 Mobile Developer Package (`docs/`)

Everything needed for iOS & frontend clients is organized in [`docs/`](docs/):

* **[`docs/openapi_2.0.yaml`](docs/openapi_2.0.yaml)** & **[`docs/openapi_2.0.json`](docs/openapi_2.0.json)**: Official OpenAPI 2.0 (Swagger) specifications for Postman, Swagger UI, and Swift OpenAPI Generator.
* **[`docs/API_SPECIFICATION.md`](docs/API_SPECIFICATION.md)**: Exhaustive REST API contract with curl samples, error handling, and request/response payloads.
* **[`docs/SWIFT_MODELS.swift`](docs/SWIFT_MODELS.swift)**: Copy-paste-ready Swift 6 `Codable` domain models with `ContentPlatform` and full session payloads.
* **[`docs/IOS_SHARE_EXTENSION_GUIDE.md`](docs/IOS_SHARE_EXTENSION_GUIDE.md)**: Share Extension implementation guide with App Groups and 300ms toast UX.

---

## 🧪 Local Testing & Deployment

### Run Unit Tests
```bash
uv run pytest -v
```

### Build & Deploy Docker Container to AWS ECR
```bash
# 1. Authenticate Docker with ECR
aws ecr get-login-password --region ap-northeast-2 --profile developer-dongik | docker login --username AWS --password-stdin 612529367436.dkr.ecr.ap-northeast-2.amazonaws.com

# 2. Build and Push Container Image
docker buildx build --platform linux/amd64 --provenance=false --sbom=false -t 612529367436.dkr.ecr.ap-northeast-2.amazonaws.com/repreel-backend:latest --push .

# 3. Deploy Serverless Stack
npx serverless deploy --aws-profile developer-dongik --stage dev
```
