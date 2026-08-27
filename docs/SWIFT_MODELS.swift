//
//  SWIFT_MODELS.swift
//  Instagram Reels Workout App - Swift 6 Codable Domain Models
//

import Foundation

// MARK: - Enums

public enum SplitType: String, Codable, Sendable, CaseIterable {
    case ppl = "PPL (Push/Pull/Legs)"
    case upperLower = "Upper/Lower (상체/하체)"
    case broSplit = "Bro Split (부위별 4-5분할)"
    case fullBody = "Full Body (무분할/전신)"
    case custom = "Custom Routine"
}

public enum EquipmentType: String, Codable, Sendable, CaseIterable {
    case barbell = "Barbell (바벨)"
    case dumbbell = "Dumbbell (덤벨)"
    case cable = "Cable (케이블)"
    case machine = "Machine (머신)"
    case bodyweight = "Bodyweight (맨몸)"
    case kettlebell = "Kettlebell (케틀벨)"
    case other = "Other (기타)"
    
    public var iconName: String {
        switch self {
        case .barbell: return "figure.strengthtraining.traditional"
        case .dumbbell: return "dumbbell.fill"
        case .cable: return "cable.connector"
        case .machine: return "gearshape.2.fill"
        case .bodyweight: return "figure.walk"
        case .kettlebell: return "circle.grid.cross.fill"
        case .other: return "questionmark.circle"
        }
    }
}

public enum GroupCategory: String, Codable, Sendable, CaseIterable {
    case mainCompound = "Main Compound (메인 복합 다관절 운동)"
    case accessory = "Accessory (보조 복합/단일 운동)"
    case isolation = "Isolation (고립/레이즈 운동)"
    case coreFinisher = "Core / Finisher (코어 및 마무리 운동)"
    
    public var badgeColorHex: String {
        switch self {
        case .mainCompound: return "#FF3B30" // Red
        case .accessory: return "#007AFF"    // Blue
        case .isolation: return "#FF9500"    // Orange
        case .coreFinisher: return "#34C759" // Green
        }
    }
}

public enum RepType: String, Codable, Sendable {
    case repsRange = "Reps Range (반복 횟수 범위)"
    case fixedReps = "Fixed Reps (고정 횟수)"
    case toFailure = "To Failure (실패 지점까지)"
    case timedSeconds = "Timed Seconds (시간/초 단위)"
}

public enum JobStatus: String, Codable, Sendable {
    case processing = "PROCESSING"
    case completed = "COMPLETED"
    case failed = "FAILED"
}

// MARK: - API Response Wrappers

public struct IngestResponse: Codable, Sendable {
    public let success: Bool
    public let jobId: String
    public let reelId: String
    public let status: JobStatus
    public let message: String
    public let statusUrl: String
    
    enum CodingKeys: String, CodingKey {
        case success
        case jobId = "job_id"
        case reelId = "reel_id"
        case status
        case message
        case statusUrl = "status_url"
    }
}

public struct JobStatusResponse: Codable, Sendable {
    public let jobId: String
    public let reelId: String
    public let status: JobStatus
    public let programId: String?
    public let confidenceScore: Double?
    public let error: String?
    public let createdAt: Int
    public let updatedAt: Int
    
    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case reelId = "reel_id"
        case status
        case programId = "program_id"
        case confidenceScore = "confidence_score"
        case error
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

public struct WorkoutProgramResponse: Codable, Sendable {
    public let programId: String
    public let reelId: String
    public let creator: String
    public let title: String
    public let splitType: SplitType
    public let cycleFrequency: String?
    public let overview: String?
    public let programData: WorkoutProgram
    public let s3Uri: String?
    public let createdAt: Int
    
    enum CodingKeys: String, CodingKey {
        case programId = "program_id"
        case reelId = "reel_id"
        case creator
        case title
        case splitType = "split_type"
        case cycleFrequency = "cycle_frequency"
        case overview
        case programData = "program_data"
        case s3Uri = "s3_uri"
        case createdAt = "created_at"
    }
}

// MARK: - Hierarchical Domain Models

public struct WorkoutProgram: Codable, Identifiable, Sendable {
    public var id: String { programId }
    
    public let programId: String
    public var title: String
    public let splitType: SplitType
    public let overview: String
    public let cycleFrequency: String
    public var days: [WorkoutDay]
    public let progression: ProgressionRule
    public let audit: DataQualityAudit
    
    enum CodingKeys: String, CodingKey {
        case programId = "program_id"
        case title
        case splitType = "split_type"
        case overview
        case cycleFrequency = "cycle_frequency"
        case days
        case progression
        case audit
    }
}

public struct WorkoutDay: Codable, Identifiable, Sendable {
    public var id: Int { dayNumber }
    
    public let dayNumber: Int
    public var dayTitle: String
    public let dayFocus: String
    public let targetMuscleGroups: [String]
    public var exerciseGroups: [ExerciseGroup]
    
    enum CodingKeys: String, CodingKey {
        case dayNumber = "day_number"
        case dayTitle = "day_title"
        case dayFocus = "day_focus"
        case targetMuscleGroups = "target_muscle_groups"
        case exerciseGroups = "exercise_groups"
    }
}

public struct ExerciseGroup: Codable, Identifiable, Sendable {
    public var id: String { "\(category.rawValue)_\(targetRegion ?? "general")" }
    
    public let category: GroupCategory
    public let targetRegion: String?
    public var exercises: [StructuredExercise]
    
    enum CodingKeys: String, CodingKey {
        case category
        case targetRegion = "target_region"
        case exercises
    }
}

public struct StructuredExercise: Codable, Identifiable, Sendable {
    public var id: String { exerciseId }
    
    public let exerciseId: String
    public var canonicalNameKo: String
    public var canonicalNameEn: String
    public let equipment: EquipmentType
    public let primaryMuscle: String
    public let secondaryMuscles: [String]
    public let isMainLift: Bool
    public var volume: PrescribedVolume
    public let guide: CoachingGuide
    
    enum CodingKeys: String, CodingKey {
        case exerciseId = "exercise_id"
        case canonicalNameKo = "canonical_name_ko"
        case canonicalNameEn = "canonical_name_en"
        case equipment
        case primaryMuscle = "primary_muscle"
        case secondaryMuscles = "secondary_muscles"
        case isMainLift = "is_main_lift"
        case volume
        case guide
    }
}

public struct PrescribedVolume: Codable, Sendable {
    public var minSets: Int
    public var maxSets: Int
    public var minReps: Int
    public var maxReps: Int?
    public var repType: RepType
    public var restSeconds: Int?
    public var weightGuidance: String?
    public var rpeTarget: Double?
    
    public var volumeDisplayString: String {
        let setsStr = minSets == maxSets ? "\(minSets)세트" : "\(minSets)-\(maxSets)세트"
        let repsStr: String
        if let max = maxReps {
            repsStr = minReps == max ? "\(minReps)회" : "\(minReps)-\(max)회"
        } else {
            repsStr = "\(minReps)회+"
        }
        return "\(setsStr) × \(repsStr)"
    }
    
    enum CodingKeys: String, CodingKey {
        case minSets = "min_sets"
        case maxSets = "max_sets"
        case minReps = "min_reps"
        case maxReps = "max_reps"
        case repType = "rep_type"
        case restSeconds = "rest_seconds"
        case weightGuidance = "weight_guidance"
        case rpeTarget = "rpe_target"
    }
}

public struct CoachingGuide: Codable, Sendable {
    public let formCues: [String]
    public let commonMistakesToAvoid: [String]
    public let tempoNotes: String?
    
    enum CodingKeys: String, CodingKey {
        case formCues = "form_cues"
        case commonMistakesToAvoid = "common_mistakes_to_avoid"
        case tempoNotes = "tempo_notes"
    }
}

public struct ProgressionRule: Codable, Sendable {
    public let overloadStrategy: String
    public let frequencySchedule: String
    public let recoveryGuidance: String?
    
    enum CodingKeys: String, CodingKey {
        case overloadStrategy = "overload_strategy"
        case frequencySchedule = "frequency_schedule"
        case recoveryGuidance = "recovery_guidance"
    }
}

public struct DataQualityAudit: Codable, Sendable {
    public let confidenceScore: Double
    public let setsAmbiguous: Bool
    public let weightMissing: Bool
    public let restMissing: Bool
    public let userActionItems: [String]
    public let auditNotes: String
    
    enum CodingKeys: String, CodingKey {
        case confidenceScore = "confidence_score"
        case setsAmbiguous = "sets_ambiguous"
        case weightMissing = "weight_missing"
        case restMissing = "rest_missing"
        case userActionItems = "user_action_items"
        case auditNotes = "audit_notes"
    }
}

// MARK: - AI Exercise Substitution Models

public struct ExerciseSubstituteRequest: Codable, Sendable {
    public let exerciseName: String
    public let targetMuscle: String
    public let preferredEquipment: [String]?
    
    public init(exerciseName: String, targetMuscle: String, preferredEquipment: [String]? = nil) {
        self.exerciseName = exerciseName
        self.targetMuscle = targetMuscle
        self.preferredEquipment = preferredEquipment
    }
    
    enum CodingKeys: String, CodingKey {
        case exerciseName = "exercise_name"
        case targetMuscle = "target_muscle"
        case preferredEquipment = "preferred_equipment"
    }
}

public struct ExerciseSubstituteItem: Codable, Identifiable, Sendable {
    public var id: String { exerciseName }
    
    public let exerciseName: String
    public let equipment: String
    public let targetMuscle: String
    public let rationale: String
    public let recommendedVolume: String
    
    enum CodingKeys: String, CodingKey {
        case exerciseName = "exercise_name"
        case equipment
        case targetMuscle = "target_muscle"
        case rationale
        case recommendedVolume = "recommended_volume"
    }
}

public struct ExerciseSubstituteResponse: Codable, Sendable {
    public let success: Bool
    public let originalExercise: String
    public let targetMuscle: String
    public let substitutes: [ExerciseSubstituteItem]
    
    enum CodingKeys: String, CodingKey {
        case success
        case originalExercise = "original_exercise"
        case targetMuscle = "target_muscle"
        case substitutes
    }
}

// MARK: - Multi-Reel Series Merge Models

public struct ProgramMergeRequest: Codable, Sendable {
    public let programIds: [String]
    public let title: String?
    
    public init(programIds: [String], title: String? = nil) {
        self.programIds = programIds
        self.title = title
    }
    
    enum CodingKeys: String, CodingKey {
        case programIds = "program_ids"
        case title
    }
}

public struct ProgramMergeResponse: Codable, Sendable {
    public let success: Bool
    public let mergedProgramId: String
    public let program: WorkoutProgramResponse
    
    enum CodingKeys: String, CodingKey {
        case success
        case mergedProgramId = "merged_program_id"
        case program
    }
}

// MARK: - AI Progressive Overload & Next-Session Models

public struct NextSessionRecommendationItem: Codable, Identifiable, Sendable {
    public var id: String { exerciseId }
    
    public let exerciseId: String
    public let exerciseName: String
    public let lastWeightKg: Double?
    public let recommendedWeightKg: Double
    public let targetSets: Int
    public let targetReps: String
    public let targetRpe: Double
    public let progressionNote: String
    
    enum CodingKeys: String, CodingKey {
        case exerciseId = "exercise_id"
        case exerciseName = "exercise_name"
        case lastWeightKg = "last_weight_kg"
        case recommendedWeightKg = "recommended_weight_kg"
        case targetSets = "target_sets"
        case targetReps = "target_reps"
        case targetRpe = "target_rpe"
        case progressionNote = "progression_note"
    }
}

public struct NextSessionRecommendationResponse: Codable, Sendable {
    public let success: Bool
    public let programId: String
    public let dayNumber: Int
    public let dayTitle: String
    public let overloadSummary: String
    public let exerciseRecommendations: [NextSessionRecommendationItem]
    
    enum CodingKeys: String, CodingKey {
        case success
        case programId = "program_id"
        case dayNumber = "day_number"
        case dayTitle = "day_title"
        case overloadSummary = "overload_summary"
        case exerciseRecommendations = "exercise_recommendations"
    }
}

// MARK: - In-Routine AI Coaching Query Models

public struct CoachQueryRequest: Codable, Sendable {
    public let question: String
    
    public init(question: String) {
        self.question = question
    }
}

public struct CoachQueryResponse: Codable, Sendable {
    public let success: Bool
    public let programId: String
    public let question: String
    public let answer: String
    public let suggestedActionItems: [String]
    
    enum CodingKeys: String, CodingKey {
        case success
        case programId = "program_id"
        case question
        case answer
        case suggestedActionItems = "suggested_action_items"
    }
}

// MARK: - Planfit-Style Live Workout Session & Volume Tracking Models

public struct LoggedSet: Codable, Identifiable, Sendable {
    public var id: Int { setNumber }
    
    public let setNumber: Int
    public var weightKg: Double      // Customizable per-set weight (e.g. Set 1: 60kg, Set 2: 70kg)
    public var reps: Int              // Executed reps
    public var rpe: Double?           // Rate of Perceived Exertion (1.0 - 10.0)
    public var completed: Bool        // ✅ Checkbox state (checked upon set completion)
    
    public var setVolumeKg: Double {
        return completed ? (weightKg * Double(reps)) : 0.0
    }
    
    public init(setNumber: Int, weightKg: Double, reps: Int, rpe: Double? = nil, completed: Bool = false) {
        self.setNumber = setNumber
        self.weightKg = weightKg
        self.reps = reps
        self.rpe = rpe
        self.completed = completed
    }
    
    enum CodingKeys: String, CodingKey {
        case setNumber = "set_number"
        case weightKg = "weight_kg"
        case reps
        case rpe
        case completed
    }
}

public struct ExecutedExerciseLog: Codable, Identifiable, Sendable {
    public var id: String { exerciseId }
    
    public let exerciseId: String
    public let exerciseName: String
    public var sets: [LoggedSet]
    
    public var totalExerciseVolumeKg: Double {
        return sets.reduce(0.0) { $0 + $1.setVolumeKg }
    }
    
    public init(exerciseId: String, exerciseName: String, sets: [LoggedSet]) {
        self.exerciseId = exerciseId
        self.exerciseName = exerciseName
        self.sets = sets
    }
    
    enum CodingKeys: String, CodingKey {
        case exerciseId = "exercise_id"
        case exerciseName = "exercise_name"
        case sets
    }
}

public struct ExerciseVolumeAnalytics: Codable, Identifiable, Sendable {
    public var id: String { exerciseId }
    
    public let exerciseId: String
    public let exerciseName: String
    public let volumeKg: Double
    public let completedSets: Int
    public let completedReps: Int
    public let topSetWeightKg: Double
    public let estimated1rmKg: Double
    
    enum CodingKeys: String, CodingKey {
        case exerciseId = "exercise_id"
        case exerciseName = "exercise_name"
        case volumeKg = "volume_kg"
        case completedSets = "completed_sets"
        case completedReps = "completed_reps"
        case topSetWeightKg = "top_set_weight_kg"
        case estimated1rmKg = "estimated_1rm_kg"
    }
}

public struct WorkoutVolumeAnalytics: Codable, Sendable {
    public let totalVolumeKg: Double          // e.g. 5,420.0 kg (Total Tonnage)
    public let totalSetsCompleted: Int        // e.g. 18 sets
    public let totalRepsCompleted: Int        // e.g. 165 reps
    public let exerciseBreakdown: [ExerciseVolumeAnalytics]
    
    public var volumeSummaryString: String {
        return "\(String(format: "%.1f", totalVolumeKg)) kg (\(totalSetsCompleted)세트 · \(totalRepsCompleted)회)"
    }
    
    enum CodingKeys: String, CodingKey {
        case totalVolumeKg = "total_volume_kg"
        case totalSetsCompleted = "total_sets_completed"
        case totalRepsCompleted = "total_reps_completed"
        case exerciseBreakdown = "exercise_breakdown"
    }
}

public struct WorkoutSessionLog: Codable, Identifiable, Sendable {
    public var id: String { sessionId ?? UUID().uuidString }
    
    public let sessionId: String?
    public let programId: String
    public let dayNumber: Int
    public let loggedAt: Int?
    public let durationSeconds: Int?
    public var completedExercises: [ExecutedExerciseLog]
    public var volumeAnalytics: WorkoutVolumeAnalytics?
    public var sessionNotes: String?
    
    public init(
        sessionId: String? = nil,
        programId: String,
        dayNumber: Int,
        loggedAt: Int? = Int(Date().timeIntervalSince1970),
        durationSeconds: Int? = nil,
        completedExercises: [ExecutedExerciseLog],
        sessionNotes: String? = nil
    ) {
        self.sessionId = sessionId
        self.programId = programId
        self.dayNumber = dayNumber
        self.loggedAt = loggedAt
        self.durationSeconds = durationSeconds
        self.completedExercises = completedExercises
        self.sessionNotes = sessionNotes
    }
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case programId = "program_id"
        case dayNumber = "day_number"
        case loggedAt = "logged_at"
        case durationSeconds = "duration_seconds"
        case completedExercises = "completed_exercises"
        case volumeAnalytics = "volume_analytics"
        case sessionNotes = "session_notes"
    }
}

// MARK: - Active In-Progress Workout Draft Models (Resume Prompt)

public struct ActiveWorkoutDraft: Codable, Sendable {
    public let userId: String
    public let programId: String?
    public let dayNumber: Int
    public let startedAt: Int
    public let lastUpdatedAt: Int
    public var sessionData: WorkoutSessionLog
    public var volumeAnalytics: WorkoutVolumeAnalytics?
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case programId = "program_id"
        case dayNumber = "day_number"
        case startedAt = "started_at"
        case lastUpdatedAt = "last_updated_at"
        case sessionData = "session_data"
        case volumeAnalytics = "volume_analytics"
    }
}

public struct ActiveSessionResponse: Codable, Sendable {
    public let hasActiveSession: Bool
    public let activeSession: ActiveWorkoutDraft?
    public let message: String?
    
    enum CodingKeys: String, CodingKey {
        case hasActiveSession = "has_active_session"
        case activeSession = "active_session"
        case message
    }
}
