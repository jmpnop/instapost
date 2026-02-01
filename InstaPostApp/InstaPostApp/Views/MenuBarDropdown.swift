import SwiftUI

struct MenuBarDropdown: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.openSettings) private var openSettings
    @State private var selectedTab = 0
    @State private var isCyberduckInstalled = false
    @State private var isInstallingCyberduck = false
    @State private var installProgress: String = ""
    @State private var progressValue: Double = 0.0

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView

            Divider()

            // Stats
            statsRow

            Divider()

            // Tab picker
            tabPicker

            // Content based on tab
            if selectedTab == 0 {
                upcomingSection
            } else {
                historySection
            }

            Divider()

            // Actions
            actionsRow

            Divider()

            // Quit
            quitButton
        }
        .frame(width: 300)
        .onAppear {
            checkCyberduckInstalled()
        }
    }

    private func checkCyberduckInstalled() {
        isCyberduckInstalled = FileManager.default.fileExists(atPath: "/Applications/Cyberduck.app")
    }

    private func installCyberduck() {
        isInstallingCyberduck = true
        installProgress = "Starting..."
        progressValue = 0.0

        Task.detached(priority: .userInitiated) {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/local/bin/brew")
            process.arguments = ["install", "--cask", "cyberduck"]

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe

            // Read output in real-time
            pipe.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                    Task { @MainActor in
                        // Parse brew output for progress
                        if output.contains("Downloading") {
                            installProgress = "Downloading..."
                            progressValue = 0.3
                        } else if output.contains("Downloaded") || output.contains("Already downloaded") {
                            installProgress = "Downloaded"
                            progressValue = 0.5
                        } else if output.contains("Installing") {
                            installProgress = "Installing..."
                            progressValue = 0.7
                        } else if output.contains("Moving App") {
                            installProgress = "Finishing..."
                            progressValue = 0.9
                        } else if output.contains("successfully installed") {
                            installProgress = "Complete!"
                            progressValue = 1.0
                        }
                    }
                }
            }

            var success = false
            do {
                try process.run()
                process.waitUntilExit()
                success = process.terminationStatus == 0
            } catch {
                print("Failed to run brew: \(error)")
            }

            pipe.fileHandleForReading.readabilityHandler = nil

            await MainActor.run {
                isInstallingCyberduck = false
                installProgress = ""
                progressValue = 0.0
                if success {
                    checkCyberduckInstalled()
                }
            }
        }
    }

    // MARK: - Header

    private var headerView: some View {
        HStack(spacing: 10) {
            // Instagram gradient icon
            RoundedRectangle(cornerRadius: 7)
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.51, green: 0.23, blue: 0.71),
                            Color(red: 0.99, green: 0.11, blue: 0.11),
                            Color(red: 0.99, green: 0.69, blue: 0.27)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 28, height: 28)
                .overlay {
                    Image(systemName: "camera")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.white)
                }

            VStack(alignment: .leading, spacing: 1) {
                Text("InstaPost")
                    .font(.system(size: 13, weight: .semibold))
                Text(appState.accountName)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // Status badge
            StatusBadge(isConnected: appState.isConnected, isTesting: appState.isTestingConnection, tested: appState.connectionTested)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    // MARK: - Stats

    private var statsRow: some View {
        HStack(spacing: 8) {
            StatCard(value: "\(appState.queueCount)", label: "Queue", color: .blue)
            StatCard(value: "\(appState.postedCount)", label: "Posted", color: .green)
            StatCard(value: "\(appState.todayCount)", label: "Today", color: .orange)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    // MARK: - Tab Picker

    private var tabPicker: some View {
        Picker("", selection: $selectedTab) {
            Text("Upcoming").tag(0)
            Text("History").tag(1)
        }
        .pickerStyle(.segmented)
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    // MARK: - Upcoming

    private var upcomingSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            if appState.queue.isEmpty {
                Text("No upcoming posts")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            } else {
                ForEach(appState.queue) { item in
                    QueueItemRow(item: item)
                }
            }
        }
    }

    // MARK: - History

    private var historySection: some View {
        VStack(alignment: .leading, spacing: 0) {
            if appState.history.isEmpty {
                Text("No posts yet")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            } else {
                ForEach(appState.history.prefix(5)) { item in
                    HistoryItemRow(item: item)
                }
            }
        }
    }

    // MARK: - Actions

    private var actionsRow: some View {
        VStack(spacing: 8) {
            if isCyberduckInstalled {
                // SFTP buttons
                HStack(spacing: 8) {
                    Button {
                        openSFTP(path: appState.vmConfig.vmImagesDir)
                    } label: {
                        Label("Images", systemImage: "photo.on.rectangle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)

                    Button {
                        openSFTP(path: appState.vmConfig.vmProcessedDir)
                    } label: {
                        Label("Processed", systemImage: "checkmark.rectangle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
            } else {
                // Install Cyberduck button
                VStack(spacing: 6) {
                    Button {
                        installCyberduck()
                    } label: {
                        if isInstallingCyberduck {
                            HStack(spacing: 8) {
                                ProgressView()
                                    .scaleEffect(0.7)
                                    .frame(width: 14, height: 14)
                                Text(installProgress.isEmpty ? "Starting..." : installProgress)
                                    .font(.system(size: 11))
                            }
                            .frame(maxWidth: .infinity)
                        } else {
                            Label("Install Cyberduck for SFTP", systemImage: "arrow.down.circle")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .disabled(isInstallingCyberduck)

                    if isInstallingCyberduck {
                        ProgressView(value: progressValue)
                            .progressViewStyle(.linear)
                    }
                }
            }

            // Settings button
            Button {
                NSApp.activate(ignoringOtherApps: true)
                openSettings()
            } label: {
                Label("Settings", systemImage: "gear")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    private func openSFTP(path: String) {
        Task {
            // Resolve IP via SSM if enabled
            if appState.vmConfig.useSSM {
                await appState.resolveIP()
            }

            let host = appState.vmConfig.sshHost
            let user = appState.vmConfig.sshUser
            let originalKeyPath = (appState.vmConfig.sshKeyPath as NSString).expandingTildeInPath
            let sshKeyPath = (("~/.ssh/instapost_key.pem") as NSString).expandingTildeInPath

            // Copy key to ~/.ssh/ for Cyberduck compatibility
            let fileManager = FileManager.default
            if fileManager.fileExists(atPath: originalKeyPath) {
                try? fileManager.removeItem(atPath: sshKeyPath)
                try? fileManager.copyItem(atPath: originalKeyPath, toPath: sshKeyPath)
                try? fileManager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: sshKeyPath)
            }

            // Update SSH config with current IP
            let sshConfigPath = (("~/.ssh/config") as NSString).expandingTildeInPath
            let sshConfig = """
            Host *
                AddKeysToAgent yes
                UseKeychain yes

            Host \(host)
                User \(user)
                IdentityFile \(sshKeyPath)
            """
            try? sshConfig.write(toFile: sshConfigPath, atomically: true, encoding: .utf8)

            // Add key to ssh-agent
            let addKey = Process()
            addKey.executableURL = URL(fileURLWithPath: "/usr/bin/ssh-add")
            addKey.arguments = [sshKeyPath]
            addKey.standardOutput = FileHandle.nullDevice
            addKey.standardError = FileHandle.nullDevice
            try? addKey.run()
            addKey.waitUntilExit()

            // Open SFTP URL - Cyberduck will handle it
            let urlString = "sftp://\(user)@\(host)\(path)"
            if let url = URL(string: urlString) {
                NSWorkspace.shared.open(url)
            }
        }
    }

    // MARK: - Quit

    private var quitButton: some View {
        Button {
            NSApplication.shared.terminate(nil)
        } label: {
            HStack {
                Text("Quit InstaPost")
                Spacer()
                Text("⌘Q")
                    .foregroundStyle(.secondary)
            }
            .font(.system(size: 12))
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .contentShape(Rectangle())
    }
}

// MARK: - Components

struct StatusBadge: View {
    let isConnected: Bool
    var isTesting: Bool = false
    var tested: Bool = false

    private var statusColor: Color {
        if isTesting { return .orange }
        if !tested { return .gray }
        return isConnected ? .green : .red
    }

    private var statusText: String {
        if isTesting { return "Connecting..." }
        if !tested { return "Not connected" }
        return isConnected ? "Connected" : "Connection failed"
    }

    var body: some View {
        HStack(spacing: 5) {
            if isTesting {
                ProgressView()
                    .scaleEffect(0.5)
                    .frame(width: 6, height: 6)
            } else {
                Circle()
                    .fill(statusColor)
                    .frame(width: 6, height: 6)
            }

            Text(statusText)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(statusColor)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background {
            Capsule()
                .fill(statusColor.opacity(0.12))
        }
    }
}

struct StatCard: View {
    let value: String
    let label: String
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundStyle(color)
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background {
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(nsColor: .controlBackgroundColor))
        }
    }
}

struct QueueItemRow: View {
    let item: QueueItem

    var body: some View {
        HStack(spacing: 10) {
            // Thumbnail placeholder
            RoundedRectangle(cornerRadius: 6)
                .fill(
                    LinearGradient(
                        colors: [.purple, .indigo],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 36, height: 36)
                .overlay {
                    Image(systemName: "photo")
                        .font(.system(size: 14))
                        .foregroundStyle(.white.opacity(0.8))
                }

            VStack(alignment: .leading, spacing: 2) {
                Text(item.filename)
                    .font(.system(size: 12, weight: .medium))
                Text(item.scheduledTime)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if item.isNext {
                Text("NEXT")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.orange)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.orange.opacity(0.12))
                    }
            } else {
                Circle()
                    .fill(Color.blue.opacity(0.6))
                    .frame(width: 6, height: 6)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .contentShape(Rectangle())
    }
}

struct HistoryItemRow: View {
    let item: HistoryItem

    var body: some View {
        HStack(spacing: 10) {
            // Thumbnail placeholder
            RoundedRectangle(cornerRadius: 6)
                .fill(
                    LinearGradient(
                        colors: [.green.opacity(0.7), .green],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 36, height: 36)
                .overlay {
                    Image(systemName: "checkmark")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.white)
                }

            VStack(alignment: .leading, spacing: 2) {
                Text(item.filename)
                    .font(.system(size: 12, weight: .medium))
                Text(item.postedTime)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 14))
                .foregroundStyle(.green)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .contentShape(Rectangle())
    }
}

#Preview {
    MenuBarDropdown()
        .environmentObject(AppState())
}
