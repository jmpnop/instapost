import SwiftUI
import UniformTypeIdentifiers

struct UploadView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var selectedImage: NSImage?
    @State private var selectedURL: URL?
    @State private var caption = ""
    @State private var isGeneratingCaption = false
    @State private var isUploading = false
    @State private var uploadProgress: Double = 0
    @State private var uploadComplete = false
    @State private var isDragging = false

    var body: some View {
        VStack(spacing: 0) {
            // Title bar
            titleBar

            // Content
            if uploadComplete {
                successView
            } else if isUploading {
                uploadingView
            } else if selectedImage != nil {
                fileSelectedView
            } else {
                dropZoneView
            }
        }
        .frame(width: 580, height: 440)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    // MARK: - Title Bar

    private var titleBar: some View {
        ZStack {
            Text("Upload to InstaPost")
                .font(.system(size: 13, weight: .medium))

            HStack {
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 13))
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .padding(.leading, 12)

                Spacer()
            }
        }
        .frame(height: 44)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    // MARK: - Drop Zone

    private var dropZoneView: some View {
        VStack(spacing: 16) {
            Spacer()

            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(
                        Color.blue.opacity(isDragging ? 0.6 : 0.3),
                        style: StrokeStyle(lineWidth: 2, dash: [8])
                    )
                    .background {
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.blue.opacity(isDragging ? 0.08 : 0.03))
                    }

                VStack(spacing: 16) {
                    ZStack {
                        Circle()
                            .fill(LinearGradient(
                                colors: [.blue, .blue.opacity(0.7)],
                                startPoint: .top,
                                endPoint: .bottom
                            ))
                            .frame(width: 64, height: 64)

                        Image(systemName: "arrow.up")
                            .font(.system(size: 26, weight: .semibold))
                            .foregroundStyle(.white)
                    }

                    VStack(spacing: 6) {
                        Text("Drop image here")
                            .font(.system(size: 16, weight: .semibold))
                        Text("or click to browse files")
                            .font(.system(size: 13))
                            .foregroundStyle(.secondary)
                    }

                    Button("Choose File") {
                        selectFile()
                    }
                    .buttonStyle(.bordered)

                    Text("JPEG, PNG  •  Max 8MB  •  320–1440px")
                        .font(.system(size: 11))
                        .foregroundStyle(.tertiary)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .padding(20)
            .onDrop(of: [.image], isTargeted: $isDragging) { providers in
                handleDrop(providers)
            }

            Spacer()
        }
    }

    // MARK: - File Selected

    private var fileSelectedView: some View {
        VStack(spacing: 0) {
            HStack(alignment: .top, spacing: 20) {
                // Image preview
                VStack(spacing: 10) {
                    if let image = selectedImage {
                        Image(nsImage: image)
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 180, height: 180)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                            .shadow(color: .black.opacity(0.2), radius: 10, y: 4)
                    }

                    if let url = selectedURL {
                        VStack(spacing: 2) {
                            Text(url.lastPathComponent)
                                .font(.system(size: 12, weight: .medium))
                            Text("1080 × 1080  •  2.4 MB")
                                .font(.system(size: 11))
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                // Caption & scheduling
                VStack(alignment: .leading, spacing: 12) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("CAPTION")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(.secondary)
                            .tracking(0.5)

                        TextEditor(text: $caption)
                            .font(.system(size: 13))
                            .frame(height: 80)
                            .scrollContentBackground(.hidden)
                            .padding(8)
                            .background {
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(Color(nsColor: .controlBackgroundColor))
                            }
                    }

                    Button {
                        generateCaption()
                    } label: {
                        HStack {
                            Image(systemName: "sparkles")
                            Text("Generate AI Caption")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .tint(.purple)
                    .disabled(isGeneratingCaption)

                    // Schedule info
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("SCHEDULED FOR")
                                .font(.system(size: 9, weight: .semibold))
                                .foregroundStyle(.tertiary)
                                .tracking(0.3)
                            Text("Today, 5:00 PM")
                                .font(.system(size: 14, weight: .semibold))
                        }

                        Spacer()

                        Text("Next slot")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(.green)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background {
                                RoundedRectangle(cornerRadius: 6)
                                    .fill(Color.green.opacity(0.12))
                            }
                    }
                    .padding(12)
                    .background {
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color(nsColor: .controlBackgroundColor))
                    }
                }
                .frame(maxWidth: .infinity)
            }
            .padding(20)

            Spacer()

            // Action buttons
            HStack {
                Spacer()

                Button("Cancel") {
                    selectedImage = nil
                    selectedURL = nil
                    caption = ""
                }
                .buttonStyle(.bordered)

                Button("Upload & Schedule") {
                    startUpload()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(20)
        }
    }

    // MARK: - Uploading

    private var uploadingView: some View {
        VStack(spacing: 20) {
            Spacer()

            ProgressView()
                .scaleEffect(1.5)

            VStack(spacing: 4) {
                Text("Uploading to VM...")
                    .font(.system(size: 16, weight: .semibold))
                Text(selectedURL?.lastPathComponent ?? "")
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
            }

            ProgressView(value: uploadProgress)
                .frame(width: 250)

            Text("\(Int(uploadProgress * 100))% complete")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)

            Spacer()
        }
    }

    // MARK: - Success

    private var successView: some View {
        VStack(spacing: 20) {
            Spacer()

            ZStack {
                Circle()
                    .fill(LinearGradient(
                        colors: [.green, .green.opacity(0.8)],
                        startPoint: .top,
                        endPoint: .bottom
                    ))
                    .frame(width: 72, height: 72)

                Image(systemName: "checkmark")
                    .font(.system(size: 32, weight: .bold))
                    .foregroundStyle(.white)
            }

            VStack(spacing: 6) {
                Text("Successfully Scheduled!")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(.green)
                Text("\(selectedURL?.lastPathComponent ?? "") will be posted Today at 5:00 PM")
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
            }

            // Details
            VStack(spacing: 0) {
                detailRow(label: "Queue Position", value: "#1 (Next)")
                Divider()
                detailRow(label: "Scheduled Time", value: "Today, 5:00 PM", valueColor: .orange)
                Divider()
                detailRow(label: "Caption", value: "✓ Added", valueColor: .green)
            }
            .background {
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color(nsColor: .controlBackgroundColor))
            }
            .frame(width: 240)

            Button("Done") {
                dismiss()
            }
            .buttonStyle(.borderedProminent)

            Spacer()
        }
    }

    private func detailRow(label: String, value: String, valueColor: Color = .primary) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(valueColor)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    // MARK: - Actions

    private func selectFile() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.image]
        panel.allowsMultipleSelection = false

        if panel.runModal() == .OK, let url = panel.url {
            loadImage(from: url)
        }
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        guard let provider = providers.first else { return false }

        provider.loadObject(ofClass: NSImage.self) { image, _ in
            DispatchQueue.main.async {
                if let nsImage = image as? NSImage {
                    self.selectedImage = nsImage
                }
            }
        }
        return true
    }

    private func loadImage(from url: URL) {
        if let image = NSImage(contentsOf: url) {
            selectedImage = image
            selectedURL = url
        }
    }

    private func generateCaption() {
        isGeneratingCaption = true
        // Simulate AI caption generation
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            caption = "Nothing beats the feeling of the open road at golden hour. 🌅 #RideOrDie #BikerLife"
            isGeneratingCaption = false
        }
    }

    private func startUpload() {
        isUploading = true
        uploadProgress = 0

        // Simulate upload
        Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { timer in
            uploadProgress += 0.02
            if uploadProgress >= 1 {
                timer.invalidate()
                isUploading = false
                uploadComplete = true
            }
        }
    }
}

#Preview {
    UploadView()
        .environmentObject(AppState())
}
