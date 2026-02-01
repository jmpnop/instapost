import SwiftUI

@main
struct InstaPostApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        // Menu Bar Extra
        MenuBarExtra {
            MenuBarDropdown()
                .environmentObject(appState)
        } label: {
            Label("InstaPost", systemImage: "camera.fill")
        }
        .menuBarExtraStyle(.window)

        // Settings Window
        Settings {
            SettingsView()
                .environmentObject(appState)
        }
    }
}
