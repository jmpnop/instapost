import SwiftUI

struct ConsistentTextFieldStyle: ViewModifier {
    var width: CGFloat? = nil

    func body(content: Content) -> some View {
        content
            .textFieldStyle(.plain)
            .padding(.horizontal, 6)
            .frame(width: width, height: 22)
            .background(Color(nsColor: .windowBackgroundColor))
            .border(Color(nsColor: .separatorColor), width: 1)
    }
}

extension View {
    func consistentTextField(width: CGFloat? = nil) -> some View {
        modifier(ConsistentTextFieldStyle(width: width))
    }
}

struct InfoLabel: View {
    let title: String
    let help: String

    init(_ title: String, help: String) {
        self.title = title
        self.help = help
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "info.circle")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .help(help)
            Text(title)
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            TabView {
                GeneralSettingsView()
                    .tabItem {
                        Label("General", systemImage: "gear")
                    }

                ConnectionSettingsView()
                    .tabItem {
                        Label("Connection", systemImage: "network")
                    }

                AISettingsView()
                    .tabItem {
                        Label("AI", systemImage: "sparkles")
                    }

                ScheduleSettingsView()
                    .tabItem {
                        Label("Schedule", systemImage: "calendar")
                    }

                AccountSettingsView()
                    .tabItem {
                        Label("Account", systemImage: "person.crop.circle")
                    }
            }

            Divider()

            HStack(spacing: 6) {
                if appState.isSyncing {
                    ProgressView()
                        .scaleEffect(0.5)
                        .frame(width: 12, height: 12)
                    Text("Syncing to VM...")
                        .foregroundStyle(.secondary)
                } else if appState.isConnected {
                    Circle()
                        .fill(Color.green)
                        .frame(width: 6, height: 6)
                    Text("Connected — config auto-syncs when changed")
                        .foregroundStyle(.secondary)
                } else {
                    Circle()
                        .fill(Color.red)
                        .frame(width: 6, height: 6)
                    Text("Offline")
                        .foregroundStyle(.secondary)
                }
            }
            .font(.system(size: 11))
            .padding(.vertical, 8)
        }
        .frame(width: 580)
        .fixedSize(horizontal: false, vertical: true)
    }
}

struct GeneralSettingsView: View {
    @EnvironmentObject var appState: AppState
    @AppStorage("launchAtLogin") private var launchAtLogin = false

    private let commonTimezones = [
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Paris",
        "Europe/Moscow",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Australia/Sydney",
        "Pacific/Auckland"
    ]

    var body: some View {
        VStack {
            Form {
                Section("Application") {
                    Toggle("Launch at login", isOn: $launchAtLogin)
                }

                Section("Timezone") {
                    Picker("Posting Timezone", selection: $appState.vmConfig.timezone) {
                        ForEach(commonTimezones, id: \.self) { tz in
                            Text(tz).tag(tz)
                        }
                    }
                }
            }
            .formStyle(.grouped)
            .scrollDisabled(true)

            HStack {
                Text("Version 0.2.0")
                Text("•")
                Text(TimeZone.current.identifier)
            }
            .font(.system(size: 11))
            .foregroundStyle(.secondary)
            .padding(.bottom, 12)
        }
    }
}

struct ConnectionSettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var isResolvingIP = false

    var body: some View {
        Form {
                Section("AWS / SSM") {
                    Toggle("Use SSM for IP resolution", isOn: $appState.vmConfig.useSSM)

                    if appState.vmConfig.useSSM {
                        LabeledContent {
                            TextField("", text: $appState.vmConfig.ssmInstanceId)
                                .consistentTextField(width: 180)
                        } label: {
                            InfoLabel("Instance ID", help: "AWS Console → EC2 → Instances → Instance ID (i-xxxxxxxxx)")
                        }
                        LabeledContent {
                            TextField("", text: $appState.vmConfig.awsProfile)
                                .consistentTextField(width: 150)
                        } label: {
                            InfoLabel("Profile", help: "AWS CLI profile name from ~/.aws/credentials")
                        }
                        LabeledContent {
                            TextField("", text: $appState.vmConfig.awsRegion)
                                .consistentTextField(width: 150)
                        } label: {
                            InfoLabel("Region", help: "AWS region where EC2 instance is running (e.g., us-east-1)")
                        }
                        Text("Resolves dynamic IP when instance restarts")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }

                Section("SSH Connection") {
                    LabeledContent {
                        if appState.vmConfig.useSSM {
                            HStack(spacing: 8) {
                                Text(appState.vmConfig.sshHost.isEmpty ? "Not resolved" : appState.vmConfig.sshHost)
                                    .foregroundStyle(appState.vmConfig.sshHost.isEmpty ? .secondary : .primary)
                                Button {
                                    resolveIP()
                                } label: {
                                    Image(systemName: "arrow.clockwise")
                                }
                                .disabled(isResolvingIP || appState.vmConfig.ssmInstanceId.isEmpty)
                                .help("Resolve IP via SSM")
                            }
                        } else {
                            TextField("", text: $appState.vmConfig.sshHost)
                                .consistentTextField(width: 150)
                        }
                    } label: {
                        InfoLabel("Host / IP", help: "EC2 public IP or hostname. Auto-resolved when using SSM.")
                    }
                    LabeledContent {
                        TextField("", text: $appState.vmConfig.sshUser)
                            .consistentTextField(width: 150)
                    } label: {
                        InfoLabel("User", help: "SSH username (e.g., ec2-user, ubuntu, or custom user)")
                    }
                    LabeledContent {
                        HStack(spacing: 8) {
                            TextField("", text: $appState.vmConfig.sshKeyPath)
                                .consistentTextField(width: 350)
                            Button {
                                browseForKeyFile()
                            } label: {
                                Image(systemName: "folder")
                            }
                            .help("Browse for SSH key file")
                        }
                    } label: {
                        InfoLabel("Key Path", help: "Path to .pem private key file downloaded from AWS")
                    }
                }

                Section("Status") {
                    HStack(spacing: 8) {
                        if appState.isTestingConnection || isResolvingIP {
                            ProgressView()
                                .scaleEffect(0.7)
                            Text(isResolvingIP ? "Resolving IP..." : "Connecting...")
                                .foregroundStyle(.secondary)
                        } else if !appState.connectionTested {
                            Circle()
                                .fill(Color.gray)
                                .frame(width: 10, height: 10)
                            Text("Not tested")
                                .foregroundStyle(.secondary)
                        } else if appState.isConnected {
                            Circle()
                                .fill(Color.green)
                                .frame(width: 10, height: 10)
                            Text("Connected")
                                .foregroundStyle(.green)
                        } else {
                            Circle()
                                .fill(Color.red)
                                .frame(width: 10, height: 10)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Connection failed")
                                    .foregroundStyle(.red)
                                if let error = appState.lastSyncError, !error.isEmpty {
                                    Text(error)
                                        .font(.system(size: 11))
                                        .foregroundStyle(.secondary)
                                        .lineLimit(2)
                                }
                            }
                        }

                        Spacer()

                        Button("Test") {
                            testConnection()
                        }
                        .disabled(appState.isTestingConnection || isResolvingIP)
                    }
                }

                Section("Remote Paths") {
                    LabeledContent {
                        TextField("", text: $appState.vmConfig.vmInstapostDir)
                            .consistentTextField(width: 200)
                    } label: {
                        InfoLabel("InstaPost Dir", help: "Directory on VM containing .env, schedule.json, processed.json")
                    }
                    LabeledContent {
                        TextField("", text: $appState.vmConfig.vmImagesDir)
                            .consistentTextField(width: 200)
                    } label: {
                        InfoLabel("Images Dir", help: "Directory where new images are placed for posting")
                    }
                    LabeledContent {
                        TextField("", text: $appState.vmConfig.vmProcessedDir)
                            .consistentTextField(width: 200)
                    } label: {
                        InfoLabel("Processed Dir", help: "Directory where posted images are moved after publishing")
                    }
                }

                Section("Static Hosting") {
                    LabeledContent {
                        TextField("", text: $appState.vmConfig.imageBaseURL)
                            .consistentTextField(width: 250)
                    } label: {
                        InfoLabel("Image Base URL", help: "Public URL serving images (e.g., Cloudflare tunnel to Angie)")
                    }
                    Text("Instagram fetches images from this URL when posting")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
        }
        .formStyle(.grouped)
        .scrollDisabled(true)
    }

    private func testConnection() {
        Task {
            await appState.testConnection()
        }
    }

    private func resolveIP() {
        isResolvingIP = true
        Task {
            await appState.resolveIP()
            await MainActor.run {
                isResolvingIP = false
            }
        }
    }

    private func browseForKeyFile() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.directoryURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".ssh")
        panel.showsHiddenFiles = true

        if panel.runModal() == .OK, let url = panel.url {
            // Convert to path with ~ for home directory
            let path = url.path
            let home = NSHomeDirectory()
            if path.hasPrefix(home) {
                appState.vmConfig.sshKeyPath = "~" + path.dropFirst(home.count)
            } else {
                appState.vmConfig.sshKeyPath = path
            }
        }
    }
}

struct AISettingsView: View {
    @EnvironmentObject var appState: AppState
    @AppStorage("autoGenerateCaptions") private var autoGenerateCaptions = true
    @AppStorage("useIPTCMetadata") private var useIPTCMetadata = true

    var body: some View {
        Form {
            Section("Caption Generation") {
                Toggle("Auto-generate captions for new images", isOn: $autoGenerateCaptions)
                Toggle("Store captions in IPTC metadata", isOn: $useIPTCMetadata)
            }

            Section("Caption Prompt") {
                VStack(alignment: .leading, spacing: 4) {
                    Text("System prompt sent to AI when generating captions:")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                    Text(appState.vmConfig.captionPrompt.isEmpty ? " \n \n \n \n \n " : appState.vmConfig.captionPrompt + "\n ")
                        .hidden()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .overlay {
                            TextEditor(text: $appState.vmConfig.captionPrompt)
                                .font(.body)
                                .scrollContentBackground(.hidden)
                                .scrollDisabled(true)
                        }
                        .padding(.horizontal, 6)
                        .padding(.vertical, 4)
                        .background(Color(nsColor: .windowBackgroundColor))
                        .border(Color(nsColor: .separatorColor), width: 1)
                }
            }
        }
        .formStyle(.grouped)
        .scrollDisabled(true)
    }
}

struct ScheduleSettingsView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Form {
                Section("Weekly Schedule") {
                    ForEach($appState.scheduleSlots) { $slot in
                        ScheduleSlotRow(slot: $slot, isDuplicate: isDuplicate(slot)) {
                            appState.removeScheduleSlot(slot)
                        }
                    }
                }
            }
            .formStyle(.grouped)
            .scrollDisabled(true)
            .fixedSize(horizontal: false, vertical: true)

            Button {
                appState.addScheduleSlot()
            } label: {
                Label("Add Time Slot", systemImage: "plus")
            }
            .padding(.horizontal, 20)

            Text("Posts will be scheduled to these time slots in order. Each new image gets the next available slot.")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 20)
                .padding(.bottom, 16)
        }
        .fixedSize(horizontal: false, vertical: true)
    }

    private func isDuplicate(_ slot: ScheduleSlot) -> Bool {
        appState.scheduleSlots.filter { other in
            other.id != slot.id &&
            other.day == slot.day &&
            other.hour == slot.hour &&
            other.minute == slot.minute
        }.count > 0
    }
}

struct ScheduleSlotRow: View {
    @Binding var slot: ScheduleSlot
    var isDuplicate: Bool = false
    var onDelete: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Toggle("", isOn: $slot.isEnabled)
                .labelsHidden()
                .toggleStyle(.checkbox)

            Picker("Day", selection: $slot.day) {
                ForEach(Weekday.allCases) { day in
                    Text(day.name).tag(day)
                }
            }
            .labelsHidden()
            .frame(width: 120)

            DatePicker("", selection: Binding(
                get: { slot.date },
                set: { slot.date = $0 }
            ), displayedComponents: .hourAndMinute)
            .labelsHidden()
            .frame(width: 90)

            if isDuplicate {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .help("Duplicate time slot")
            }

            Spacer()

            Button(role: .destructive) {
                onDelete()
            } label: {
                Image(systemName: "trash")
                    .foregroundStyle(.red.opacity(0.7))
            }
            .buttonStyle(.plain)
        }
        .opacity(slot.isEnabled ? 1 : 0.5)
    }
}

struct AccountSettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var showAppSecret = false
    @State private var showAccessToken = false
    @State private var showAwsSecretKey = false
    @State private var isValidatingToken = false
    @State private var tokenStatus: String?
    @State private var tokenStatusIsError = false
    @State private var headerStatus: String?
    @State private var headerStatusOpacity: Double = 1.0

    var body: some View {
        Form {
            Section("AWS Credentials") {
                LabeledContent {
                    TextField("", text: $appState.vmConfig.awsAccessKeyId)
                        .consistentTextField(width: 200)
                } label: {
                    InfoLabel("Access Key ID", help: "AWS Console → IAM → Users → Security credentials → Create access key")
                }

                LabeledContent {
                    if showAwsSecretKey {
                        TextField("", text: $appState.vmConfig.awsSecretAccessKey)
                            .consistentTextField(width: 340)
                    } else {
                        SecureField("", text: $appState.vmConfig.awsSecretAccessKey)
                            .consistentTextField(width: 340)
                    }
                } label: {
                    HStack(spacing: 6) {
                        InfoLabel("Secret Access Key", help: "Shown once when creating access key in AWS IAM")
                        Button {
                            showAwsSecretKey.toggle()
                        } label: {
                            Image(systemName: showAwsSecretKey ? "eye" : "eye.slash")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }

                Text("Credentials synced to VM for S3 access")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

            Section("Instagram Account") {
                HStack(spacing: 12) {
                    ZStack {
                        Circle()
                            .fill(LinearGradient(
                                colors: [
                                    Color(red: 0.51, green: 0.23, blue: 0.71),
                                    Color(red: 0.99, green: 0.11, blue: 0.11),
                                    Color(red: 0.99, green: 0.69, blue: 0.27)
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ))
                            .frame(width: 48, height: 48)

                        Image(systemName: "person.fill")
                            .font(.system(size: 20))
                            .foregroundStyle(.white)
                    }

                    VStack(alignment: .leading, spacing: 2) {
                        Text(appState.accountName)
                            .font(.system(size: 14, weight: .semibold))
                        Text(appState.accountDisplayName)
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.vertical, 4)

                LabeledContent {
                    TextField("", text: $appState.vmConfig.instagramBusinessAccountId)
                        .consistentTextField(width: 180)
                } label: {
                    InfoLabel("Business Account ID", help: "Graph API: GET /me/accounts → instagram_business_account.id")
                }
            }

            Section {
                LabeledContent {
                    TextField("", text: $appState.vmConfig.facebookAppId)
                        .consistentTextField(width: 180)
                } label: {
                    InfoLabel("App ID", help: "developers.facebook.com → My Apps → Select app → App ID at top")
                }
            } header: {
                HStack {
                    Text("Facebook API")
                    if let status = headerStatus {
                        Text("✓ \(status)")
                            .foregroundStyle(.green)
                            .opacity(headerStatusOpacity)
                    }
                }
            }

            Section {

                LabeledContent {
                    if showAppSecret {
                        TextField("", text: $appState.vmConfig.facebookAppSecret)
                            .consistentTextField(width: 270)
                    } else {
                        SecureField("", text: $appState.vmConfig.facebookAppSecret)
                            .consistentTextField(width: 270)
                    }
                } label: {
                    HStack(spacing: 6) {
                        InfoLabel("App Secret", help: "developers.facebook.com → My Apps → Settings → Basic → App Secret")
                        Button {
                            showAppSecret.toggle()
                        } label: {
                            Image(systemName: showAppSecret ? "eye" : "eye.slash")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }

                LabeledContent {
                    if showAccessToken {
                        TextField("", text: $appState.vmConfig.facebookAccessToken)
                            .consistentTextField(width: 340)
                    } else {
                        SecureField("", text: $appState.vmConfig.facebookAccessToken)
                            .consistentTextField(width: 340)
                    }
                } label: {
                    HStack(spacing: 6) {
                        InfoLabel("Access Token", help: "Graph API Explorer → Generate token with pages_read_engagement, instagram_basic, instagram_content_publish")
                        Button {
                            showAccessToken.toggle()
                        } label: {
                            Image(systemName: showAccessToken ? "eye" : "eye.slash")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Section {
                HStack {
                    Button("Validate Token") {
                        validateToken()
                    }
                    .disabled(isValidatingToken || appState.vmConfig.facebookAccessToken.isEmpty)

                    if isValidatingToken {
                        ProgressView()
                            .scaleEffect(0.5)
                            .frame(width: 16, height: 16)
                    }

                    Text("Check if token is valid and view expiration")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }

                if let status = tokenStatus {
                    Text(status)
                        .font(.system(size: 11))
                        .foregroundStyle(tokenStatusIsError ? .red : .green)
                }
            }
        }
        .formStyle(.grouped)
        .scrollDisabled(true)
    }

    private func validateToken() {
        isValidatingToken = true
        tokenStatus = nil

        Task {
            let token = appState.vmConfig.facebookAccessToken
            let appId = appState.vmConfig.facebookAppId
            let appSecret = appState.vmConfig.facebookAppSecret

            var components = URLComponents(string: "https://graph.facebook.com/debug_token")!
            components.queryItems = [
                URLQueryItem(name: "input_token", value: token),
                URLQueryItem(name: "access_token", value: "\(appId)|\(appSecret)")
            ]

            guard let url = components.url else {
                await MainActor.run {
                    tokenStatus = "Invalid URL"
                    tokenStatusIsError = true
                    isValidatingToken = false
                }
                return
            }

            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

                if let error = json?["error"] as? [String: Any],
                   let message = error["message"] as? String {
                    await MainActor.run {
                        tokenStatus = "✗ \(message)"
                        tokenStatusIsError = true
                        isValidatingToken = false
                    }
                    return
                }

                if let dataObj = json?["data"] as? [String: Any] {
                    let isValid = dataObj["is_valid"] as? Bool ?? false
                    let expiresAt = dataObj["expires_at"] as? Int ?? 0

                    await MainActor.run {
                        if isValid {
                            if expiresAt == 0 {
                                tokenStatus = nil
                                showHeaderStatus("Token is valid (never expires)")
                            } else {
                                let date = Date(timeIntervalSince1970: TimeInterval(expiresAt))
                                let formatter = DateFormatter()
                                formatter.dateStyle = .medium
                                formatter.timeStyle = .short
                                tokenStatus = nil
                                showHeaderStatus("Valid until \(formatter.string(from: date))")
                            }
                            tokenStatusIsError = false
                        } else {
                            tokenStatus = "✗ Token is invalid or expired"
                            tokenStatusIsError = true
                        }
                        isValidatingToken = false
                    }
                } else {
                    await MainActor.run {
                        tokenStatus = "✗ Unexpected response format"
                        tokenStatusIsError = true
                        isValidatingToken = false
                    }
                }
            } catch {
                await MainActor.run {
                    tokenStatus = "Error: \(error.localizedDescription)"
                    tokenStatusIsError = true
                    isValidatingToken = false
                }
            }
        }
    }

    private func showHeaderStatus(_ message: String) {
        headerStatus = message
        headerStatusOpacity = 1.0

        // Fade out after 5 seconds
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
            withAnimation(.easeOut(duration: 1.0)) {
                headerStatusOpacity = 0.0
            }
            // Clear the status after fade completes
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                headerStatus = nil
                headerStatusOpacity = 1.0
            }
        }
    }
}

#Preview {
    SettingsView()
        .environmentObject(AppState())
}
