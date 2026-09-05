# iOS Share Extension Implementation Guide

This guide provides the complete Swift implementation for the **Workout App Share Extension** (supporting Instagram Reels & YouTube Shorts).

When a user taps **Share $\rightarrow$ Workout App** inside Instagram or YouTube, this extension intercepts the video URL, calls the backend `POST /reels` endpoint, stores the `job_id` in the shared App Group, and dismisses smoothly in **< 300ms**.

---

## 1. Xcode Project & Target Configuration

### A. Add Share Extension Target
1. In Xcode: `File` $\rightarrow$ `New` $\rightarrow$ `Target...` $\rightarrow$ **Share Extension**.
2. Name: `ReelsShareExtension`.

### B. Configure `Info.plist`
In `ReelsShareExtension/Info.plist`, configure `NSExtensionActivationRule` to accept URLs and plain text:

```xml
<key>NSExtension</key>
<dict>
    <key>NSExtensionAttributes</key>
    <dict>
        <key>NSExtensionActivationRule</key>
        <dict>
            <key>NSExtensionActivationSupportsWebURLWithMaxCount</key>
            <integer>1</integer>
            <key>NSExtensionActivationSupportsText</key>
            <true/>
        </dict>
    </dict>
    <key>NSExtensionPointIdentifier</key>
    <string>com.apple.share-services</string>
    <key>NSExtensionPrincipalClass</key>
    <string>$(PRODUCT_MODULE_NAME).ShareViewController</string>
</dict>
```

### C. Enable App Groups (For Shared Storage with Main App)
1. Select your Main App Target $\rightarrow$ `Signing & Capabilities` $\rightarrow$ `+ Capability` $\rightarrow$ **App Groups**.
2. Select your Share Extension Target $\rightarrow$ `Signing & Capabilities` $\rightarrow$ `+ Capability` $\rightarrow$ **App Groups**.
3. Create App Group ID: `group.com.yourname.reelsworkout`.

---

## 2. Complete `ShareViewController.swift` Implementation

```swift
//
//  ShareViewController.swift
//  ReelsShareExtension
//

import UIKit
import Social
import UniformTypeIdentifiers

class ShareViewController: UIViewController {
    
    // MARK: - Configuration Constants
    private let apiBaseURL = "https://szcr4meit6.execute-api.ap-northeast-2.amazonaws.com"
    private let appSecretKey = "reels-workout-dev-secret-2026"
    private let userEmail = "dongik@example.com"
    private let appGroupID = "group.com.dongik.repreel"
    
    // MARK: - UI Components
    private let containerView: UIView = {
        let view = UIView()
        view.backgroundColor = UIColor.systemBackground.withAlphaComponent(0.95)
        view.layer.cornerRadius = 20
        view.layer.shadowColor = UIColor.black.cgColor
        view.layer.shadowOpacity = 0.2
        view.layer.shadowRadius = 15
        view.translatesAutoresizingMaskIntoConstraints = false
        return view
    }()
    
    private let spinner: UIActivityIndicatorView = {
        let indicator = UIActivityIndicatorView(style: .medium)
        indicator.translatesAutoresizingMaskIntoConstraints = false
        indicator.startAnimating()
        return indicator
    }()
    
    private let statusLabel: UILabel = {
        let label = UILabel()
        label.text = "운동 영상 AI 분석 요청 중..."
        label.font = UIFont.systemFont(ofSize: 15, weight: .semibold)
        label.textColor = .label
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()
    
    // MARK: - Lifecycle
    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        extractAndSendReelURL()
    }
    
    // MARK: - UI Setup
    private func setupUI() {
        view.backgroundColor = UIColor.black.withAlphaComponent(0.4)
        view.addSubview(containerView)
        containerView.addSubview(spinner)
        containerView.addSubview(statusLabel)
        
        NSLayoutConstraint.activate([
            containerView.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            containerView.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            containerView.widthAnchor.constraint(equalToConstant: 260),
            containerView.heightAnchor.constraint(equalToConstant: 120),
            
            spinner.centerXAnchor.constraint(equalTo: containerView.centerXAnchor),
            spinner.topAnchor.constraint(equalTo: containerView.topAnchor, constant: 25),
            
            statusLabel.leadingAnchor.constraint(equalTo: containerView.leadingAnchor, constant: 16),
            statusLabel.trailingAnchor.constraint(equalTo: containerView.trailingAnchor, constant: -16),
            statusLabel.topAnchor.constraint(equalTo: spinner.bottomAnchor, constant: 15)
        ])
    }
    
    // MARK: - URL Extraction Logic
    private func extractAndSendReelURL() {
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem,
              let attachments = extensionItem.attachments else {
            dismissWithError("공유 항목을 찾을 수 없습니다.")
            return
        }
        
        for itemProvider in attachments {
            // 1. Try URL Provider
            if itemProvider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                itemProvider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] (item, _) in
                    if let url = item as? URL {
                        self?.sendReelURLToBackend(url.absoluteString)
                    }
                }
                return
            }
            
            // 2. Try Plain Text Provider (Instagram sometimes shares as string)
            if itemProvider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                itemProvider.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] (item, _) in
                    if let text = item as? String, let url = self?.extractURLFromString(text) {
                        self?.sendReelURLToBackend(url)
                    }
                }
                return
            }
        }
    }
    
    private func extractURLFromString(_ text: String) -> String? {
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let matches = detector?.matches(in: text, options: [], range: NSRange(location: 0, length: text.utf16.count))
        return matches?.first?.url?.absoluteString
    }
    
    // MARK: - Network Request (POST /reels)
    private func sendReelURLToBackend(_ reelURL: String) {
        guard let endpoint = URL(string: "\(apiBaseURL)/reels") else {
            dismissWithError("API URL 오류")
            return
        }
        
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(appSecretKey, forHTTPHeaderField: "x-app-secret")
        request.setValue(userEmail, forHTTPHeaderField: "x-user-email")
        request.timeoutInterval = 10.0
        
        let payload: [String: String] = ["url": reelURL]
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        
        URLSession.shared.dataTask(with: request) { [weak self] (data, response, error) in
            DispatchQueue.main.async {
                if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 202,
                   let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let jobId = json["job_id"] as? String {
                    
                    // Store Job in App Group UserDefaults
                    self?.savePendingJobToAppGroup(jobId: jobId, reelURL: reelURL)
                    self?.dismissWithSuccess()
                } else {
                    self?.dismissWithError("서버 전송 실패")
                }
            }
        }.resume()
    }
    
    // MARK: - App Group Persistence
    private func savePendingJobToAppGroup(jobId: String, reelURL: String) {
        if let sharedDefaults = UserDefaults(suiteName: appGroupID) {
            var pendingJobs = sharedDefaults.stringArray(forKey: "pending_job_ids") ?? []
            pendingJobs.append(jobId)
            sharedDefaults.set(pendingJobs, forKey: "pending_job_ids")
            sharedDefaults.synchronize()
        }
    }
    
    // MARK: - Dismiss Helpers
    private func dismissWithSuccess() {
        statusLabel.text = "✅ 분석 시작 완료!"
        spinner.stopAnimating()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            self.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
        }
    }
    
    private func dismissWithError(_ message: String) {
        statusLabel.text = "❌ \(message)"
        spinner.stopAnimating()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            self.extensionContext?.cancelRequest(withError: NSError(domain: "ShareError", code: 1, userInfo: nil))
        }
    }
}
```

---

## 3. Main App Listening for Pending Jobs

In your SwiftUI Main App (`App.swift` or Dashboard View):

```swift
import SwiftUI

struct DashboardView: View {
    @State private var pendingJobIds: [String] = []
    private let appGroupID = "group.com.yourname.reelsworkout"
    
    var body: some View {
        NavigationStack {
            List {
                // Active Processing Banner
                if !pendingJobIds.isEmpty {
                    Section("분석 중인 릴스") {
                        ForEach(pendingJobIds, id: \.self) { jobId in
                            HStack {
                                ProgressView()
                                    .padding(.trailing, 8)
                                Text("AI가 운동 루틴을 분석하고 있습니다...")
                                    .font(.subheadline)
                            }
                            .task {
                                await pollJobStatus(jobId: jobId)
                            }
                        }
                    }
                }
                
                // Saved Routines List
                Section("저장된 운동 프로그램") {
                    // ...
                }
            }
            .navigationTitle("내 릴스 루틴")
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
                loadPendingJobsFromAppGroup()
            }
        }
    }
    
    private func loadPendingJobsFromAppGroup() {
        if let sharedDefaults = UserDefaults(suiteName: appGroupID) {
            self.pendingJobIds = sharedDefaults.stringArray(forKey: "pending_job_ids") ?? []
        }
    }
    
    private func pollJobStatus(jobId: String) async {
        // Poll GET /jobs/{jobId} every 2.0s until completed
    }
}
```
