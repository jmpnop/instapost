import SwiftUI
import Combine

struct VMConfig: Codable, Equatable {
    // SSH Connection
    var sshHost: String = "54.242.9.15"
    var sshUser: String = "ironsirens"
    var sshKeyPath: String = "~/PycharmProjects/instapost/AWSCelestialKeyPair.pem"

    // SSM for IP resolution (optional)
    var useSSM: Bool = true
    var ssmInstanceId: String = "i-0db574a38acd30088"
    var awsProfile: String = "default"
    var awsRegion: String = "us-east-1"

    // AWS Credentials (synced to VM)
    var awsAccessKeyId: String = ""
    var awsSecretAccessKey: String = ""

    // Remote paths
    var vmInstapostDir: String = "/home/ironsirens/instapost"
    var vmImagesDir: String = "/mnt/s3/images"
    var vmProcessedDir: String = "/mnt/s3/processed"

    // Static hosting (Cloudflare tunnel)
    var imageBaseURL: String = "https://instapost.celestialtech.io"

    // Facebook/Instagram API (stored on VM)
    var facebookAppId: String = ""
    var facebookAppSecret: String = ""
    var facebookAccessToken: String = ""
    var instagramBusinessAccountId: String = ""

    // Application settings
    var timezone: String = "America/New_York"
    var captionPrompt: String = "Describe this image for Instagram."

}

@MainActor
class AppState: ObservableObject {
    @Published var isConnected = false
    @Published var isTestingConnection = false
    @Published var connectionTested = false
    @Published var isSyncing = false
    @Published var lastSyncError: String?
    @Published var queueCount = 0
    @Published var postedCount = 0
    @Published var todayCount = 0
    @Published var queue: [QueueItem] = []
    @Published var history: [HistoryItem] = []

    @Published var accountName = "@ironsirens"
    @Published var accountDisplayName = "Iron Sirens MC"

    @Published var vmConfig = VMConfig() {
        didSet { scheduleSyncToVM() }
    }

    @Published var scheduleSlots: [ScheduleSlot] = [
        ScheduleSlot(day: .monday, hour: 7, minute: 0, isEnabled: true),
        ScheduleSlot(day: .wednesday, hour: 11, minute: 0, isEnabled: true),
        ScheduleSlot(day: .friday, hour: 17, minute: 0, isEnabled: true),
        ScheduleSlot(day: .saturday, hour: 9, minute: 0, isEnabled: true),
        ScheduleSlot(day: .sunday, hour: 18, minute: 0, isEnabled: true),
    ] {
        didSet { scheduleSyncToVM() }
    }

    private var syncTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    init() {
        loadFromDisk()
        Task {
            await testConnection()
        }
    }

    func testConnection() async {
        let host = vmConfig.sshHost
        let user = vmConfig.sshUser
        guard !host.isEmpty, !user.isEmpty else {
            isConnected = false
            connectionTested = true
            lastSyncError = "Host and user are required"
            return
        }

        isTestingConnection = true

        do {
            let keyPath = (vmConfig.sshKeyPath as NSString).expandingTildeInPath
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/ssh")
            process.arguments = [
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                "-i", keyPath,
                "\(user)@\(host)",
                "echo", "ok"
            ]

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe

            try process.run()
            process.waitUntilExit()

            isConnected = process.terminationStatus == 0

            if !isConnected {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
                lastSyncError = output.trimmingCharacters(in: .whitespacesAndNewlines)
            } else {
                lastSyncError = nil
                await refresh()
            }
        } catch {
            isConnected = false
            lastSyncError = error.localizedDescription
        }

        isTestingConnection = false
        connectionTested = true
    }

    func resolveIP() async {
        let instanceId = vmConfig.ssmInstanceId
        guard !instanceId.isEmpty else {
            lastSyncError = "Instance ID required for IP resolution"
            return
        }

        if let ip = await resolveIPViaSSM() {
            if !ip.isEmpty {
                vmConfig.sshHost = ip
                lastSyncError = nil
            } else {
                lastSyncError = "Could not resolve IP (instance may not have public IP)"
            }
        }
    }

    func addScheduleSlot() {
        scheduleSlots.append(ScheduleSlot(day: .monday, hour: 12, minute: 0, isEnabled: true))
    }

    func removeScheduleSlot(_ slot: ScheduleSlot) {
        scheduleSlots.removeAll { $0.id == slot.id }
    }

    func refresh() async {
        guard isConnected else { return }

        let instapostDir = vmConfig.vmInstapostDir

        // Fetch .env for config values
        if let envData = await runRemoteCommand("cat \(instapostDir)/.env 2>/dev/null || echo ''") {
            parseEnvFile(envData)
        }

        // Fetch schedule.json
        if let scheduleData = await runRemoteCommand("cat \(instapostDir)/schedule.json 2>/dev/null || echo '[]'") {
            parseSchedule(scheduleData)
        }

        // Fetch processed.json
        // Fetch processed.json
        if let processedData = await runRemoteCommand("cat \(instapostDir)/processed.json 2>/dev/null || echo '[]'") {
            parseProcessed(processedData)
        }
    }

    private func runRemoteCommand(_ command: String) async -> String? {
        return await runSSHCommand(command: command)
    }

    private func parseEnvFile(_ content: String) {
        let lines = content.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty, !trimmed.hasPrefix("#") else { continue }

            let parts = trimmed.split(separator: "=", maxSplits: 1)
            guard parts.count == 2 else { continue }

            let key = String(parts[0]).trimmingCharacters(in: .whitespaces)
            var value = String(parts[1]).trimmingCharacters(in: .whitespaces)
            // Remove quotes
            if (value.hasPrefix("\"") && value.hasSuffix("\"")) || (value.hasPrefix("'") && value.hasSuffix("'")) {
                value = String(value.dropFirst().dropLast())
            }

            switch key {
            case "FACEBOOK_APP_ID":
                vmConfig.facebookAppId = value
            case "FACEBOOK_APP_SECRET":
                vmConfig.facebookAppSecret = value
            case "FACEBOOK_ACCESS_TOKEN":
                vmConfig.facebookAccessToken = value
            case "INSTAGRAM_BUSINESS_ACCOUNT_ID":
                vmConfig.instagramBusinessAccountId = value
            case "IMAGE_BASE_URL":
                vmConfig.imageBaseURL = value
            case "TIMEZONE":
                vmConfig.timezone = value
            case "CAPTION_PROMPT":
                vmConfig.captionPrompt = value
            default:
                break
            }
        }
    }

    private func runSSHCommand(command: String) async -> String? {
        let host = vmConfig.sshHost
        let user = vmConfig.sshUser
        let keyPath = (vmConfig.sshKeyPath as NSString).expandingTildeInPath

        do {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/ssh")
            process.arguments = [
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=5",
                "-o", "StrictHostKeyChecking=no",
                "-i", keyPath,
                "\(user)@\(host)",
                command
            ]

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = FileHandle.nullDevice

            try process.run()
            process.waitUntilExit()

            if process.terminationStatus == 0 {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                return String(data: data, encoding: .utf8)
            }
        } catch {
            print("SSH command failed: \(error)")
        }
        return nil
    }

    private func runSSMCommand(command: String) async -> String? {
        let instanceId = vmConfig.ssmInstanceId
        let profile = vmConfig.awsProfile
        let region = vmConfig.awsRegion

        do {
            // Send command via SSM
            let sendProcess = Process()
            sendProcess.executableURL = URL(fileURLWithPath: "/usr/local/bin/aws")
            sendProcess.arguments = [
                "ssm", "send-command",
                "--instance-ids", instanceId,
                "--document-name", "AWS-RunShellScript",
                "--parameters", "commands=[\"\(command.replacingOccurrences(of: "\"", with: "\\\""))\"]",
                "--output", "text",
                "--query", "Command.CommandId",
                "--profile", profile,
                "--region", region
            ]

            let sendPipe = Pipe()
            sendProcess.standardOutput = sendPipe
            sendProcess.standardError = FileHandle.nullDevice

            try sendProcess.run()
            sendProcess.waitUntilExit()

            guard sendProcess.terminationStatus == 0 else {
                lastSyncError = "SSM send-command failed"
                return nil
            }

            let commandIdData = sendPipe.fileHandleForReading.readDataToEndOfFile()
            let commandId = String(data: commandIdData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

            guard !commandId.isEmpty else {
                lastSyncError = "Failed to get SSM command ID"
                return nil
            }

            // Wait for command to complete and get output
            try await Task.sleep(nanoseconds: 1_000_000_000) // Wait 1 second

            let getProcess = Process()
            getProcess.executableURL = URL(fileURLWithPath: "/usr/local/bin/aws")
            getProcess.arguments = [
                "ssm", "get-command-invocation",
                "--command-id", commandId,
                "--instance-id", instanceId,
                "--output", "text",
                "--query", "StandardOutputContent",
                "--profile", profile,
                "--region", region
            ]

            let getPipe = Pipe()
            getProcess.standardOutput = getPipe
            getProcess.standardError = FileHandle.nullDevice

            try getProcess.run()
            getProcess.waitUntilExit()

            if getProcess.terminationStatus == 0 {
                let data = getPipe.fileHandleForReading.readDataToEndOfFile()
                return String(data: data, encoding: .utf8)
            }
        } catch {
            print("SSM command failed: \(error)")
            lastSyncError = error.localizedDescription
        }
        return nil
    }

    private func parseSchedule(_ json: String) {
        guard let data = json.data(using: .utf8) else { return }

        struct ScheduleEntry: Decodable {
            let filename: String
            let scheduled_time: String
            let status: String?
        }

        do {
            let entries = try JSONDecoder().decode([ScheduleEntry].self, from: data)
            let pending = entries.filter { $0.status == nil || $0.status == "pending" }

            queueCount = pending.count

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

            let displayFormatter = DateFormatter()
            displayFormatter.dateFormat = "MMM d, h:mm a"

            let now = Date()
            let calendar = Calendar.current

            queue = pending.prefix(5).enumerated().map { index, entry in
                var displayTime = entry.scheduled_time
                if let date = formatter.date(from: entry.scheduled_time) {
                    if calendar.isDateInToday(date) {
                        displayFormatter.dateFormat = "'Today,' h:mm a"
                    } else if calendar.isDateInTomorrow(date) {
                        displayFormatter.dateFormat = "'Tomorrow,' h:mm a"
                    } else {
                        displayFormatter.dateFormat = "MMM d, h:mm a"
                    }
                    displayTime = displayFormatter.string(from: date)
                }
                return QueueItem(filename: entry.filename, scheduledTime: displayTime, isNext: index == 0)
            }
        } catch {
            print("Failed to parse schedule: \(error)")
        }
    }

    private func parseProcessed(_ json: String) {
        guard let data = json.data(using: .utf8) else { return }

        struct ProcessedEntry: Decodable {
            let filename: String?
            let posted_at: String?
        }

        do {
            let entries = try JSONDecoder().decode([ProcessedEntry].self, from: data)
            postedCount = entries.count

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let calendar = Calendar.current
            let today = calendar.startOfDay(for: Date())

            let displayFormatter = DateFormatter()

            todayCount = entries.filter { entry in
                guard let postedAt = entry.posted_at,
                      let date = formatter.date(from: postedAt) else { return false }
                return calendar.isDate(date, inSameDayAs: today)
            }.count

            // Populate history (most recent first)
            history = entries.compactMap { entry in
                guard let filename = entry.filename,
                      let postedAt = entry.posted_at,
                      let date = formatter.date(from: postedAt) else { return nil }

                if calendar.isDateInToday(date) {
                    displayFormatter.dateFormat = "'Today,' h:mm a"
                } else if calendar.isDateInYesterday(date) {
                    displayFormatter.dateFormat = "'Yesterday,' h:mm a"
                } else {
                    displayFormatter.dateFormat = "MMM d, h:mm a"
                }
                return HistoryItem(filename: filename, postedTime: displayFormatter.string(from: date))
            }
        } catch {
            print("Failed to parse processed: \(error)")
        }
    }

    // MARK: - Persistence

    private var configFileURL: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("InstaPost")
            .appendingPathComponent("config.json")
    }

    private func loadFromDisk() {
        do {
            let dir = configFileURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

            if FileManager.default.fileExists(atPath: configFileURL.path) {
                let data = try Data(contentsOf: configFileURL)
                let saved = try JSONDecoder().decode(SavedConfig.self, from: data)
                self.vmConfig = saved.vmConfig
                self.scheduleSlots = saved.scheduleSlots
            }
        } catch {
            print("Failed to load config: \(error)")
        }
    }

    private func saveToDisk() {
        do {
            let saved = SavedConfig(vmConfig: vmConfig, scheduleSlots: scheduleSlots)
            let data = try JSONEncoder().encode(saved)
            try data.write(to: configFileURL)
        } catch {
            print("Failed to save config: \(error)")
        }
    }

    // MARK: - VM Sync

    private func scheduleSyncToVM() {
        saveToDisk()

        // Debounce: cancel previous sync, wait 1 second before syncing
        syncTask?.cancel()
        syncTask = Task {
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            if !Task.isCancelled && isConnected {
                await syncToVM()
            }
        }
    }

    func syncToVM() async {
        guard isConnected else { return }

        isSyncing = true
        lastSyncError = nil

        let schedule = scheduleSlots
            .filter { $0.isEnabled }
            .map { slot in
                let dayIndex = (slot.day.rawValue + 5) % 7
                return "\(dayIndex):\(String(format: "%02d", slot.hour)):\(String(format: "%02d", slot.minute))"
            }
            .joined(separator: ",")

        let envContent = """
        # InstaPost VM Configuration
        # Auto-synced from InstaPost.app

        IMAGE_BASE_URL=\(vmConfig.imageBaseURL)
        FACEBOOK_APP_ID=\(vmConfig.facebookAppId)
        FACEBOOK_APP_SECRET=\(vmConfig.facebookAppSecret)
        FACEBOOK_ACCESS_TOKEN=\(vmConfig.facebookAccessToken)
        INSTAGRAM_BUSINESS_ACCOUNT_ID=\(vmConfig.instagramBusinessAccountId)
        TIMEZONE=\(vmConfig.timezone)
        WEEKLY_SCHEDULE="\(schedule)"
        CAPTION_PROMPT="\(vmConfig.captionPrompt)"
        AWS_ACCESS_KEY_ID=\(vmConfig.awsAccessKeyId)
        AWS_SECRET_ACCESS_KEY=\(vmConfig.awsSecretAccessKey)
        AWS_DEFAULT_REGION=\(vmConfig.awsRegion)
        """

        do {
            let tempFile = FileManager.default.temporaryDirectory.appendingPathComponent(".env.vm")
            try envContent.write(to: tempFile, atomically: true, encoding: .utf8)

            let host = vmConfig.sshHost
            let user = vmConfig.sshUser
            let keyPath = (vmConfig.sshKeyPath as NSString).expandingTildeInPath
            let remotePath = "\(vmConfig.vmInstapostDir)/.env"

            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/scp")
            process.arguments = [
                "-o", "StrictHostKeyChecking=no",
                "-i", keyPath,
                tempFile.path,
                "\(user)@\(host):\(remotePath)"
            ]

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe

            try process.run()
            process.waitUntilExit()

            try? FileManager.default.removeItem(at: tempFile)

            if process.terminationStatus != 0 {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? "Unknown error"
                lastSyncError = output.trimmingCharacters(in: .whitespacesAndNewlines)
            }
        } catch {
            lastSyncError = error.localizedDescription
        }

        isSyncing = false
    }

    func resolveIPViaSSM() async -> String? {
        // Get public IP from EC2 describe-instances (more reliable than metadata)
        let instanceId = vmConfig.ssmInstanceId
        let profile = vmConfig.awsProfile
        let region = vmConfig.awsRegion

        do {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/local/bin/aws")
            process.arguments = [
                "ec2", "describe-instances",
                "--instance-ids", instanceId,
                "--query", "Reservations[0].Instances[0].PublicIpAddress",
                "--output", "text",
                "--profile", profile,
                "--region", region
            ]

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = FileHandle.nullDevice

            try process.run()
            process.waitUntilExit()

            if process.terminationStatus == 0 {
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let ip = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                return (ip == "None" || ip?.isEmpty == true) ? nil : ip
            }
        } catch {
            print("Failed to resolve IP: \(error)")
        }
        return nil
    }
}

// MARK: - Models

struct SavedConfig: Codable {
    var vmConfig: VMConfig
    var scheduleSlots: [ScheduleSlot]
}

struct QueueItem: Identifiable {
    let id = UUID()
    let filename: String
    let scheduledTime: String
    let isNext: Bool
}

struct HistoryItem: Identifiable {
    let id = UUID()
    let filename: String
    let postedTime: String
}

enum Weekday: Int, CaseIterable, Identifiable, Codable {
    case sunday = 1, monday, tuesday, wednesday, thursday, friday, saturday

    var id: Int { rawValue }

    var name: String {
        switch self {
        case .sunday: return "Sunday"
        case .monday: return "Monday"
        case .tuesday: return "Tuesday"
        case .wednesday: return "Wednesday"
        case .thursday: return "Thursday"
        case .friday: return "Friday"
        case .saturday: return "Saturday"
        }
    }

    var shortName: String {
        String(name.prefix(3))
    }
}

struct ScheduleSlot: Identifiable, Codable, Equatable {
    var id = UUID()
    var day: Weekday
    var hour: Int
    var minute: Int
    var isEnabled: Bool

    var timeString: String {
        String(format: "%02d:%02d", hour, minute)
    }

    var date: Date {
        get {
            Calendar.current.date(from: DateComponents(hour: hour, minute: minute)) ?? Date()
        }
        set {
            let components = Calendar.current.dateComponents([.hour, .minute], from: newValue)
            hour = components.hour ?? 0
            minute = components.minute ?? 0
        }
    }
}
