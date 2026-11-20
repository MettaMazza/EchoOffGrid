import AppKit
import SwiftUI
import UniformTypeIdentifiers
import PDFKit
import WebKit
import Network

enum Section: String, CaseIterable, Identifiable {
    case home = "Home"
    case radio = "Radio & sharing"
    case maps = "Maps"
    case reference = "Reference"
    case entertainment = "Entertainment"
    case files = "Files & backup"

    var id: Self { self }

    var icon: String {
        switch self {
        case .home: "house"
        case .radio: "antenna.radiowaves.left.and.right"
        case .maps: "map"
        case .reference: "books.vertical"
        case .entertainment: "play.rectangle"
        case .files: "folder"
        }
    }

    var summary: String {
        switch self {
        case .home: "Open the tools you need without searching through folders."
        case .radio: "Use HackRF mode for SDRangel or MeshRF. One app can use the radio at a time."
        case .maps: "Browse the UK and world offline, or open a map to print."
        case .reference: "Search your local library or open a practical guide."
        case .entertainment: "Watch, read, listen or play from files on this Mac."
        case .files: "Find the original files, installers and private folder."
        }
    }
}

struct Destination: Identifiable {
    let title: String
    let detail: String
    let icon: String
    let path: String
    var application: String?
    var arguments: [String] = []
    var startsLocalServer = false
    var bundledResource = false
    var id: String { path }

    static let echoOffGrid = Self(title: "EchoOffGrid", detail: "Public sources, offline search and evidence",
                                 icon: "tray.full", path: "EchoOffGrid/dashboard.py",
                                 arguments: ["--port", "0"], startsLocalServer: true, bundledResource: true)
    static let atlas = Self(title: "Offline atlas", detail: "UK street detail, Aberdeen and the world", icon: "map", path: "03-Maps/Atlas/server.py", arguments: ["--no-browser"], startsLocalServer: true)
    static let sdr = Self(title: "ScotMesh receiver", detail: "SDRangel and saved Aberdeen preset", icon: "waveform", path: "Apps/SDRangel.app", arguments: ["--api-address", "127.0.0.1", "--api-port", "18891"])
    static let wikipedia = Self(title: "Wikipedia", detail: "Full English edition in Kiwix", icon: "book", path: "02-Reference/wikipedia_en_all_nopic_2026-06.zim", application: "Apps/Kiwix.app")
    static let emergency = Self(title: "Household card", detail: "Contacts, check-ins and FM stations", icon: "list.clipboard", path: "01-Comms/Household card.txt")
    static let films = Self(title: "Films", detail: "10 films in VLC", icon: "film", path: "04-Entertainment/Films.m3u8", application: "Apps/VLC.app")

    static func entries(for section: Section) -> [Self] {
        switch section {
        case .home:
            return [.emergency, .echoOffGrid, .atlas, .sdr, .wikipedia, .films,
                    .init(title: "Outage checklist", detail: "What to do in the first 15 minutes", icon: "checklist", path: "START HERE.txt")]
        case .radio:
            return [.sdr,
                    .init(title: "MeshRF", detail: "Meshtastic receive on the HackRF", icon: "dot.radiowaves.left.and.right", path: "Apps/MeshRF.app"),
                    .init(title: "LocalSend", detail: "Send files over local Wi-Fi", icon: "arrow.left.arrow.right", path: "Apps/LocalSend.app"),
                    .init(title: "Voice radio", detail: "Two-way setup and testing notes", icon: "mic", path: "01-Comms/H4M two-way voice setup.txt"),
                    .init(title: "Local bulletin", detail: "A shareable message template", icon: "note.text", path: "01-Comms/Local bulletin.txt"),
                    .init(title: "Aberdeen radio presets", detail: "Public FM frequencies for the PortaPack", icon: "radio", path: "01-Comms/H4M SD card/FREQMAN"),
                    .init(title: "ScotMesh instructions", detail: "Settings, audio monitor and decoder", icon: "doc.text", path: "01-Comms/ScotMesh in SDRangel.txt"),
                    .emergency]
        case .maps:
            return [.atlas,
                    .init(title: "Aberdeen street map", detail: "Printable PDF", icon: "mappin.and.ellipse", path: "03-Maps/Aberdeen street map.pdf"),
                    .init(title: "Great Britain rail", detail: "All-stations map", icon: "tram", path: "03-Maps/Great Britain rail map.pdf"),
                    .init(title: "Northern Ireland rail", detail: "Map in Appendix 2", icon: "tram", path: "03-Maps/Northern Ireland rail map (appendix 2).pdf")]
        case .reference:
            return [.echoOffGrid, .wikipedia,
                    .init(title: "Simple English Wikipedia", detail: "Compact edition for a grab copy", icon: "book.closed", path: "02-Reference/wikipedia_en-simple_all_mini_2026-09.zim", application: "Apps/Kiwix.app"),
                    .init(title: "Appropedia", detail: "Practical skills and repair", icon: "hammer", path: "02-Reference/appropedia_en_all_maxi_2026-02.zim", application: "Apps/Kiwix.app"),
                    .init(title: "UK Be Ready", detail: "Official household emergency plan", icon: "doc.text", path: "02-Reference/UK Be Ready household emergency plan.pdf"),
                    .init(title: "Aberdeenshire guide", detail: "Local preparedness information", icon: "doc.text", path: "02-Reference/Aberdeenshire preparedness guide.pdf"),
                    .init(title: "All reference files", detail: "Guides and offline archives", icon: "folder", path: "02-Reference")]
        case .entertainment:
            return [.films,
                    .init(title: "Shows", detail: "Caminandes and Hubble episodes", icon: "play.rectangle.on.rectangle", path: "04-Entertainment/Shows.m3u8", application: "Apps/VLC.app"),
                    .init(title: "Books", detail: "19 local classics", icon: "books.vertical", path: "04-Entertainment/Books"),
                    .init(title: "Audio", detail: "Local audiobook", icon: "headphones", path: "04-Entertainment/Audio"),
                    .init(title: "Browser puzzles", detail: "15 games that run locally", icon: "puzzlepiece", path: "04-Entertainment/Games/Browser Puzzles/serve.py", startsLocalServer: true),
                    .init(title: "OpenTTD", detail: "Transport strategy", icon: "tram", path: "04-Entertainment/Games/OpenTTD.app"),
                    .init(title: "SuperTuxKart", detail: "Kart racing", icon: "flag.checkered", path: "04-Entertainment/Games/SuperTuxKart.app"),
                    .init(title: "Chess", detail: "The built-in Mac game", icon: "checkerboard.rectangle", path: "/System/Applications/Chess.app")]
        case .files:
            return [.init(title: "Open kit in Finder", detail: "Browse the folder layout", icon: "folder", path: "."),
                    .init(title: "Installers", detail: "Local software packages", icon: "shippingbox", path: "05-Installers"),
                    .init(title: "Private folder", detail: "Use encrypted storage for sensitive files", icon: "lock", path: "06-Private"),
                    .init(title: "Backup checklist", detail: "Keep a separate drive and paper copies", icon: "externaldrive", path: "02-Reference/Download checklist.txt"),
                    .init(title: "Full build plan", detail: "Mesh, long-range radio and outage drills", icon: "doc.text", path: "OFFGRID REBUILD.txt")]
        }
    }
}

struct HomeView: View {
    @State private var selection: Section? = .home
    @State private var alertText: String?
    @State private var document: KitDocument?
    @AppStorage("kitFolder") private var kitFolder = ""
    @AppStorage("kitBookmark") private var kitBookmark = Data()
    @StateObject private var launcher = ShortcutLauncher()
    private var root: URL {
        var stale = false
        if !kitBookmark.isEmpty, let chosen = try? URL(
            resolvingBookmarkData: kitBookmark, options: .withoutUI,
            relativeTo: nil, bookmarkDataIsStale: &stale
        ), !stale { return chosen }
        if !kitFolder.isEmpty { return URL(fileURLWithPath: kitFolder, isDirectory: true) }
        return Bundle.main.bundleURL.deletingLastPathComponent()
    }
    private let accent = Color(red: 0.09, green: 0.46, blue: 0.38)
    private var section: Section { selection ?? .home }

    var body: some View {
        NavigationSplitView {
            List(Section.allCases, selection: $selection) { item in
                Label(item.rawValue, systemImage: item.icon)
                    .padding(.vertical, 5)
                    .tag(item)
            }
            .listStyle(.sidebar)
            .navigationSplitViewColumnWidth(min: 175, ideal: 190, max: 225)
            .safeAreaInset(edge: .top) {
                HStack(spacing: 10) {
                    Image(systemName: "bolt.shield").foregroundStyle(accent)
                    Text("OffGrid").font(.title2.weight(.semibold))
                    Spacer()
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
            }
        } detail: {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(section == .home ? "Offline kit" : section.rawValue)
                            .font(.system(size: 34, weight: .semibold))
                            .accessibilityAddTraits(.isHeader)
                        Text(section.summary)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 12)], spacing: 12) {
                        ForEach(Destination.entries(for: section)) { item in
                            Button { open(item) } label: {
                                HStack(spacing: 13) {
                                    Image(systemName: item.icon)
                                        .font(.system(size: 19, weight: .medium))
                                        .foregroundStyle(accent)
                                        .frame(width: 38, height: 38)
                                        .background(accent.opacity(0.12), in: RoundedRectangle(cornerRadius: 11))
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(item.title).font(.headline)
                                        Text(item.detail).font(.callout).foregroundStyle(.secondary)
                                    }
                                    Spacer(minLength: 5)
                                    Image(systemName: "arrow.up.right")
                                        .font(.system(size: 10, weight: .medium))
                                        .foregroundStyle(.secondary)
                                }
                                .padding(13)
                                .frame(minHeight: 78)
                            }
                            .buttonStyle(.plain)
                            .background(.background, in: RoundedRectangle(cornerRadius: 13))
                            .overlay(RoundedRectangle(cornerRadius: 13).strokeBorder(.quaternary))
                            .help("Open " + item.title)
                        }
                    }
                }
                .padding(28)
                .frame(maxWidth: 940, alignment: .leading)
            }
            .background(Color(nsColor: .windowBackgroundColor))
            .navigationTitle("OffGrid Home")
        }
        .frame(minWidth: 755, minHeight: 500)
        .toolbar {
            Button("Choose Kit Folder", systemImage: "folder", action: chooseKit)
                .help("Select the OffGrid Kit folder if macOS blocks access")
        }
        .sheet(item: $document) { file in
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text(file.title).font(.headline)
                    Spacer()
                    Button(file.id.pathExtension == "pdf" ? "Open in Preview" : "Open in Editor") {
                        document = nil
                        launcher.open(file.destination, from: root) { result in
                            if case .failure(let error) = result {
                                DispatchQueue.main.async { alertText = error.localizedDescription }
                            }
                        }
                    }
                    Button("Done") { document = nil }.keyboardShortcut(.cancelAction)
                }
                .padding()
                Divider()
                switch file.content {
                case .text(let text):
                    ScrollView {
                        Text(text)
                            .font(.system(.body, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(20)
                    }
                case .pdf(let pdf):
                    KitPDFView(document: pdf)
                }
            }
            .frame(minWidth: 600, minHeight: 460)
        }
        .alert("Couldn’t open item", isPresented: Binding(
            get: { alertText != nil },
            set: { if !$0 { alertText = nil } }
        )) {
            Button("OK", role: .cancel) { alertText = nil }
        } message: {
            Text(alertText ?? "")
        }
    }

    private func chooseKit() {
        let panel = NSOpenPanel()
        panel.title = "Choose OffGrid Kit"
        panel.prompt = "Use Folder"
        panel.directoryURL = root
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard FileManager.default.fileExists(atPath: url.appendingPathComponent("START HERE.txt").path),
              FileManager.default.fileExists(atPath: url.appendingPathComponent("03-Maps").path) else {
            alertText = "Select the OffGrid Kit folder that contains START HERE and the maps folder."
            return
        }
        kitFolder = url.path
        kitBookmark = (try? url.bookmarkData(options: .minimalBookmark)) ?? Data()
    }

    private func open(_ item: Destination) {
        let url = item.url(in: root)
        do {
            if let preview = try KitDocument.load(title: item.title, url: url) {
                document = preview
                return
            }
        } catch {
            alertText = "Couldn’t read \(item.title). \(error.localizedDescription) If access is blocked, use Choose Kit Folder."
            return
        }
        launcher.open(item, from: root) { result in
            if case .failure(let error) = result {
                DispatchQueue.main.async {
                    alertText = "Couldn’t open \(item.title). \(error.localizedDescription) If access is blocked, use Choose Kit Folder."
                }
            }
        }
    }
}

extension Destination {
    func url(in root: URL) -> URL {
        let base = bundledResource ? (Bundle.main.resourceURL ?? root) : root
        return (path.hasPrefix("/") ? URL(fileURLWithPath: path)
            : base.appendingPathComponent(path)).standardizedFileURL
    }
}

struct KitDocument: Identifiable {
    enum Content { case text(String), pdf(PDFDocument) }
    let id: URL
    let title: String
    let content: Content
    var destination: Destination {
        Destination(title: title, detail: "", icon: "doc", path: id.path)
    }

    static func load(title: String, url: URL) throws -> Self? {
        switch url.pathExtension.lowercased() {
        case "txt":
            return Self(id: url, title: title, content: .text(try String(contentsOf: url, encoding: .utf8)))
        case "pdf":
            let data = try Data(contentsOf: url, options: .mappedIfSafe)
            guard let document = PDFDocument(data: data), document.pageCount > 0 else {
                throw CocoaError(.fileReadCorruptFile)
            }
            return Self(id: url, title: title, content: .pdf(document))
        default:
            return nil
        }
    }
}

struct KitPDFView: NSViewRepresentable {
    let document: PDFDocument

    func makeNSView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.document = document
        return view
    }

    func updateNSView(_ view: PDFView, context: Context) {
        if view.document !== document { view.document = document }
    }
}

final class ShortcutLauncher: ObservableObject {
    private let servers = LocalServers()

    func open(_ item: Destination, from root: URL, activates: Bool = true,
              completion: @escaping (Result<URL, Error>) -> Void) {
        let url = item.url(in: root)
        do {
            _ = try url.checkResourceIsReachable()
        } catch {
            completion(.failure(error))
            return
        }
        if item.startsLocalServer {
            servers.open(script: url, arguments: item.arguments, activates: activates, completion: completion)
            return
        }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.arguments = item.arguments
        configuration.activates = activates
        let done: (NSRunningApplication?, Error?) -> Void = { _, error in
            if let error { completion(.failure(error)) }
            else { completion(.success(url)) }
        }
        if let app = item.application {
            NSWorkspace.shared.open([url], withApplicationAt: root.appendingPathComponent(app),
                                    configuration: configuration, completionHandler: done)
        } else if url.pathExtension == "app" {
            NSWorkspace.shared.openApplication(at: url, configuration: configuration, completionHandler: done)
        } else {
            NSWorkspace.shared.open(url, configuration: configuration, completionHandler: done)
        }
    }
}

final class LocalServers {
    private var processes: [URL: Process] = [:]
    private var addresses: [URL: URL] = [:]
    private var waiting: [URL: [(Result<URL, Error>) -> Void]] = [:]

    deinit {
        for process in processes.values where process.isRunning { process.terminate() }
    }

    func open(script: URL, arguments: [String], activates: Bool, inBrowser: Bool = true,
              completion: @escaping (Result<URL, Error>) -> Void) {
        func openAddress(_ url: URL) {
            guard inBrowser else { completion(.success(url)); return }
            let configuration = NSWorkspace.OpenConfiguration()
            configuration.activates = activates
            NSWorkspace.shared.open(url, configuration: configuration) { _, error in
                if let error { completion(.failure(error)) }
                else { completion(.success(url)) }
            }
        }

        let onReady: (Result<URL, Error>) -> Void = { result in
            switch result {
            case .success(let address): openAddress(address)
            case .failure(let error): completion(.failure(error))
            }
        }
        if let process = processes[script] {
            if process.isRunning {
                if let url = addresses[script] { openAddress(url) }
                else { waiting[script, default: []].append(onReady) }
                return
            }
            failStart(script, process: process, message: "The local dashboard exited before opening.")
        }
        addresses.removeValue(forKey: script)
        let process = Process()
        let output = Pipe()
        let bundledPython = Bundle.main.resourceURL?.appendingPathComponent("PythonRuntime/bin/python3")
        if let bundledPython, FileManager.default.isExecutableFile(atPath: bundledPython.path) {
            process.executableURL = bundledPython
            var environment = ProcessInfo.processInfo.environment
            if environment["SSL_CERT_FILE"] == nil,
               FileManager.default.isReadableFile(atPath: "/etc/ssl/cert.pem") {
                environment["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"
            }
            process.environment = environment
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        }
        process.arguments = ["-E", "-s", "-B", script.path] + arguments
        process.terminationHandler = { [weak self] finished in
            DispatchQueue.main.async {
                guard let self, self.processes[script] === finished, self.waiting[script] != nil else { return }
                self.failStart(script, process: finished, message: "The local service exited during startup (status \(finished.terminationStatus)).")
            }
        }
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
        } catch {
            completion(.failure(error))
            return
        }
        processes[script] = process
        waiting[script] = [onReady]
        DispatchQueue.global(qos: .userInitiated).async {
            let bytes = output.fileHandleForReading.availableData
            let line = String(data: bytes, encoding: .utf8)?.split(whereSeparator: \.isNewline).first
            DispatchQueue.main.async {
                guard self.processes[script] === process, self.waiting[script] != nil else { return }
                guard let line, let url = URL(string: String(line)), url.scheme == "http",
                      url.host == "127.0.0.1", process.isRunning else {
                    self.failStart(script, process: process, message: "The local dashboard could not start. Check that macOS Command Line Tools Python is available.")
                    return
                }
                self.addresses[script] = url
                for launch in self.waiting.removeValue(forKey: script) ?? [] { launch(.success(url)) }
            }
        }
        // First launch can wait for macOS to authorise the selected library.
        // The readiness pipe reports the address or EOF if the helper exits.

    }

    func stop(script: URL) {
        guard let process = processes[script] else { return }
        failStart(script, process: process, message: "Dashboard restarted.")
    }

    private func failStart(_ script: URL, process: Process, message: String) {
        guard processes[script] === process else { return }
        processes.removeValue(forKey: script)
        addresses.removeValue(forKey: script)
        if process.isRunning { process.terminate() }
        let error = NSError(domain: "OffGrid Home", code: 1, userInfo: [
            NSLocalizedDescriptionKey: message
        ])
        for launch in waiting.removeValue(forKey: script) ?? [] { launch(.failure(error)) }
    }

}

#if ECHO_STANDALONE
@available(macOS 14.0, *)
final class PrivateBrowserPanel:NSView, WKNavigationDelegate {
    let tab:WKWebView
    let addressField=NSTextField()
    let progress=NSTextField(labelWithString:"")
    let back=NSButton(title:"‹ Back",target:nil,action:nil)
    let next=NSButton(title:"Forward ›",target:nil,action:nil)
    init(port:UInt16, destination:String) {
        let config=WKWebViewConfiguration()
        let store=WKWebsiteDataStore.nonPersistent()
        let endpoint=NWEndpoint.hostPort(host:"127.0.0.1",port:NWEndpoint.Port(rawValue:port)!)
        var proxy=ProxyConfiguration(httpCONNECTProxy:endpoint)
        proxy.allowFailover=false
        store.proxyConfigurations=[proxy]
        config.websiteDataStore=store
        config.preferences.javaScriptCanOpenWindowsAutomatically=false
        config.userContentController.addUserScript(WKUserScript(source:"for(const n of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport']){try{Object.defineProperty(globalThis,n,{value:undefined,configurable:false})}catch{}}",injectionTime:.atDocumentStart,forMainFrameOnly:false))
        tab=WKWebView(frame:.zero,configuration:config)
        super.init(frame:.zero)
        wantsLayer=true;layer?.backgroundColor=NSColor.windowBackgroundColor.cgColor
        tab.navigationDelegate=self
        let close=NSButton(title:"Done",target:self,action:#selector(done))
        let go=NSButton(title:"Go",target:self,action:#selector(openAddress))
        back.target=self;back.action=#selector(previous)
        next.target=self;next.action=#selector(forward)
        addressField.target=self;addressField.action=#selector(openAddress)
        addressField.placeholderString="Enter an HTTPS address"
        addressField.setContentHuggingPriority(.defaultLow,for:.horizontal)
        let bar=NSStackView(views:[back,next,addressField,go,close])
        for child in [bar,progress,tab] as [NSView]{addSubview(child);child.translatesAutoresizingMaskIntoConstraints=false}
        NSLayoutConstraint.activate([bar.leadingAnchor.constraint(equalTo:leadingAnchor,constant:10),bar.trailingAnchor.constraint(equalTo:trailingAnchor,constant:-10),bar.topAnchor.constraint(equalTo:topAnchor,constant:8),progress.topAnchor.constraint(equalTo:bar.bottomAnchor,constant:3),progress.leadingAnchor.constraint(equalTo:bar.leadingAnchor),tab.topAnchor.constraint(equalTo:progress.bottomAnchor,constant:4),tab.leadingAnchor.constraint(equalTo:leadingAnchor),tab.trailingAnchor.constraint(equalTo:trailingAnchor),tab.bottomAnchor.constraint(equalTo:bottomAnchor)])
        addressField.stringValue=destination;openAddress()
    }
    required init?(coder:NSCoder){fatalError()}
    @objc func done(){tab.stopLoading();removeFromSuperview()}
    @objc func previous(){if tab.canGoBack{tab.goBack()}else{done()}}
    @objc func forward(){if tab.canGoForward{tab.goForward()}}
    @objc func openAddress(){
        let raw=addressField.stringValue.trimmingCharacters(in:.whitespacesAndNewlines)
        guard let url=URL(string:raw.contains("://") ? raw : "https://"+raw),url.scheme=="https",url.host != nil else{progress.stringValue="Enter an HTTPS address.";return}
        tab.load(URLRequest(url:url))
    }
    func webView(_ view:WKWebView, decidePolicyFor action:WKNavigationAction, decisionHandler:@escaping(WKNavigationActionPolicy)->Void){
        guard action.request.url?.scheme=="https" || action.request.url?.absoluteString=="about:blank" else{decisionHandler(.cancel);return}
        if action.targetFrame==nil{decisionHandler(.cancel);view.load(action.request);return}
        decisionHandler(.allow)
    }
    func webView(_ view:WKWebView,didStartProvisionalNavigation navigation:WKNavigation!){progress.stringValue="Loading over Tor…"}
    func webView(_ view:WKWebView,didFinish navigation:WKNavigation!){addressField.stringValue=view.url?.absoluteString ?? "";progress.stringValue=view.title ?? "";next.isEnabled=view.canGoForward}
    func webView(_ view:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error){if (error as NSError).code != NSURLErrorCancelled{progress.stringValue="Could not load this page over Tor."}}
}

struct WorkspaceWebView: NSViewRepresentable {
    let address: URL

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        if #available(macOS 14.0, *) { configuration.applicationNameForUserAgent = "EchoOffGrid/Mac" }
        configuration.preferences.isElementFullscreenEnabled = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.userContentController.addScriptMessageHandler(context.coordinator, contentWorld: .page, name: "pdfText")
        configuration.userContentController.addScriptMessageHandler(context.coordinator, contentWorld: .page, name: "importedFile")
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.underPageBackgroundColor = NSColor(srgbRed: 0.035, green: 0.067, blue: 0.059, alpha: 1)
        view.uiDelegate = context.coordinator
        view.navigationDelegate = context.coordinator
        view.load(URLRequest(url: address))
        return view
    }

    func updateNSView(_ view: WKWebView, context: Context) {}

    static func dismantleNSView(_ view: WKWebView, coordinator: Coordinator) {
        view.configuration.userContentController.removeScriptMessageHandler(forName: "pdfText", contentWorld: .page)
        view.configuration.userContentController.removeScriptMessageHandler(forName: "importedFile", contentWorld: .page)
    }

    func makeCoordinator() -> Coordinator { Coordinator(address: address) }

    final class Coordinator: NSObject, WKUIDelegate, WKNavigationDelegate, WKDownloadDelegate, WKScriptMessageHandlerWithReply {
        let address: URL
        init(address: URL) { self.address = address }

        func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage,
                                   replyHandler: @escaping (Any?, String?) -> Void) {
            if message.name=="importedFile" {
                guard message.frameInfo.isMainFrame,let origin=message.frameInfo.request.url,
                      origin.scheme==address.scheme,origin.host==address.host,origin.port==address.port,
                      origin.path.hasPrefix("/library/"),let fields=message.body as? [String:String],
                      let key=fields["id"],key.range(of:"^personal-[0-9a-f]{64}$",options:.regularExpression) != nil,
                      let name=fields["name"],let file=pickedApps.removeValue(forKey:name),
                      let bookmark=try? file.bookmarkData(options:[.withSecurityScope,.securityScopeAllowOnlyReadAccess])
                else {replyHandler(false,nil);return}
                UserDefaults.standard.set(bookmark,forKey:"library-app-"+key);replyHandler(true,nil);return
            }
            guard message.frameInfo.isMainFrame, let origin = message.frameInfo.request.url,
                  origin.scheme == address.scheme, origin.host == address.host, origin.port == address.port,
                  let input = message.body as? String, let url = URL(string: input),
                  url.scheme == address.scheme, url.host == address.host, url.port == address.port,
                  url.path.hasPrefix("/kit-file/") || url.path.hasPrefix("/content-file/") else {
                replyHandler(nil,"Local PDF required"); return
            }
            URLSession.shared.dataTask(with: url) { bytes, response, _ in
                let text = response?.mimeType == "application/pdf" ? bytes.flatMap { PDFDocument(data: $0)?.string } : nil
                DispatchQueue.main.async { replyHandler(text, text == nil ? "No readable PDF text" : nil) }
            }.resume()
        }

        private var pickedApps:[String:URL]=[:]
        private var importStaging: URL?
        deinit {
            if let folder=importStaging {try? FileManager.default.removeItem(at:folder)}
        }
        func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
            guard frame.isMainFrame, frame.request.url?.path.hasPrefix("/library/")==true || frame.request.url?.path.hasPrefix("/content/")==true else {completionHandler(nil);return}
            let panel=NSOpenPanel()
            panel.allowsMultipleSelection=parameters.allowsMultipleSelection
            panel.canChooseDirectories=false
            panel.begin { result in
                guard result == .OK else { completionHandler(nil);return }
                let urls=panel.urls
                do {
                    let root=self.importStaging ?? FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
                    self.importStaging=root
                    let output=try urls.map { file -> URL in
                        guard file.pathExtension.lowercased()=="app" else {return file}
                        let dir=root.appendingPathComponent(UUID().uuidString)
                        try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:true)
                        let zip=dir.appendingPathComponent(file.lastPathComponent+".zip")
                        let task=Process()
                        task.executableURL=URL(fileURLWithPath:"/usr/bin/ditto")
                        task.arguments=["-c","-k","--keepParent",file.path,zip.path]
                        try task.run()
                        task.waitUntilExit()
                        guard task.terminationStatus==0 else {throw CocoaError(.fileReadUnknown)}
                        self.pickedApps[zip.lastPathComponent]=file
                        return zip
                    }
                    completionHandler(output)
                } catch {
                    completionHandler(nil)
                    NSAlert(error:error).runModal()
                }
            }
        }

        weak var echoWindow: NSWindow?
        var enteringEcho = false

        func openEcho(in parent: NSWindow) -> Bool {
            if let echoWindow {
                echoWindow.makeKeyAndOrderFront(nil)
                return true
            }
            guard !enteringEcho, let executable = Bundle.main.executableURL else { return false }
            var stale = false
            let bookmark = UserDefaults.standard.data(forKey: "echoLiteApplicationBookmark")
            let selected = bookmark.flatMap { try? URL(resolvingBookmarkData: $0, options: .withoutUI, relativeTo: nil, bookmarkDataIsStale: &stale) }
            let app = selected ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/EchoLite/EchoLite.app")
            let ui = app.deletingLastPathComponent().appendingPathComponent("bin/echolite-ui")
            guard FileManager.default.isExecutableFile(atPath: ui.path),
                  let handle = dlopen(executable.deletingLastPathComponent().appendingPathComponent("EchoInterface.dylib").path, RTLD_NOW | RTLD_LOCAL),
                  let symbol = dlsym(handle, "echolite_entry") else { return false }
            enteringEcho = true
            DispatchQueue.main.async {
                let observer = NotificationCenter.default.addObserver(forName: NSWindow.didBecomeKeyNotification, object: nil, queue: nil) { note in
                    guard let window = note.object as? NSWindow, window !== parent, window.title == "EchoLite", self.echoWindow == nil else { return }
                    self.echoWindow = window
                    parent.addTabbedWindow(window, ordered: .above)
                }
                let entry = unsafeBitCast(symbol, to: (@convention(c) (Int32, UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>) -> Int32).self)
                let previousHome = ProcessInfo.processInfo.environment["ECHOLITE_HOME"]
                let previousToken = ProcessInfo.processInfo.environment["ECHOLITE_NATIVE_TOKEN_FILE"]
                let name = strdup(ui.path)
                var args = [name, nil]
                _ = entry(1, &args)
                free(name)
                for (key, value) in [("ECHOLITE_HOME", previousHome), ("ECHOLITE_NATIVE_TOKEN_FILE", previousToken)] {
                    if let value { setenv(key, value, 1) } else { unsetenv(key) }
                }
                NotificationCenter.default.removeObserver(observer)
                self.echoWindow = nil
                self.enteringEcho = false
                parent.makeKeyAndOrderFront(nil)
            }
            return true
        }

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            let url = action.request.url
            if let url, ["http","https"].contains(url.scheme ?? ""),
               (url.host != address.host || url.port != address.port || url.scheme != address.scheme),
               action.navigationType == .linkActivated {
                decisionHandler(.cancel)
                var route=URLComponents(url:address,resolvingAgainstBaseURL:false)!
                route.path="/private-browser"
                route.queryItems=[URLQueryItem(name:"to",value:url.absoluteString)]
                if let destination=route.url { webView.load(URLRequest(url:destination)) }
                return
            }
            guard url?.scheme == "http", url?.host == address.host, url?.port == address.port else {
                decisionHandler(.cancel)
                return
            }
            if let url,url.path=="/private-open" {
                decisionHandler(.cancel)
                guard #available(macOS 14.0,*),action.sourceFrame.isMainFrame, webView.url?.path=="/private-browser", action.sourceFrame.securityOrigin.host==address.host,
                      let raw=URLComponents(url:url,resolvingAgainstBaseURL:false)?.queryItems?.first(where:{$0.name=="port"})?.value,
                      let port=UInt16(raw),port>1023 else{return}
                let destination=URLComponents(url:url,resolvingAgainstBaseURL:false)?.queryItems?.first(where:{$0.name=="url"})?.value ?? "https://duckduckgo.com/"
                let panel=PrivateBrowserPanel(port:port,destination:destination)
                panel.translatesAutoresizingMaskIntoConstraints=false
                webView.addSubview(panel)
                NSLayoutConstraint.activate([panel.leadingAnchor.constraint(equalTo:webView.leadingAnchor),panel.trailingAnchor.constraint(equalTo:webView.trailingAnchor),panel.topAnchor.constraint(equalTo:webView.topAnchor),panel.bottomAnchor.constraint(equalTo:webView.bottomAnchor)])
                return
            }
            if let url, action.navigationType == .linkActivated, url.path.hasPrefix("/personal-launch/") {
                decisionHandler(.cancel)
                var stale=false
                if let key=url.pathComponents.last,let bookmark=UserDefaults.standard.data(forKey:"library-app-"+key),
                   let file=try? URL(resolvingBookmarkData:bookmark,options:[.withSecurityScope,.withoutUI],relativeTo:nil,bookmarkDataIsStale:&stale),
                   file.pathExtension.lowercased()=="app",FileManager.default.fileExists(atPath:file.path) {
                    let access=file.startAccessingSecurityScopedResource()
                    NSWorkspace.shared.openApplication(at:file,configuration:NSWorkspace.OpenConfiguration()){_,_ in
                        if access {file.stopAccessingSecurityScopedResource()}
                    }
                } else {
                    let alert=NSAlert();alert.messageText="Select this application in Library again to reconnect it.";alert.runModal()
                }
                return
            }
            if let url, action.navigationType == .linkActivated, url.path.hasPrefix("/personal-open/"),
               let key=url.pathComponents.last, key.range(of:"^(?:personal-)?[0-9a-f]{64}$",options:.regularExpression) != nil {
                let root=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("EchoOffGrid/Content")
                if let files=try? FileManager.default.contentsOfDirectory(at:root,includingPropertiesForKeys:nil),
                   let file=files.first(where:{ $0.lastPathComponent.hasPrefix(key+".") && $0.pathExtension != "cover" }) {
                    decisionHandler(.cancel)
                    NSWorkspace.shared.activateFileViewerSelecting([file]);return
                }
            }
            if let url, url.path.hasPrefix("/player/"), action.navigationType == .linkActivated {
                decisionHandler(.cancel)
                let path = URLComponents(url: url, resolvingAgainstBaseURL: true)?.percentEncodedPath ?? ""
                let streamPath: String
                if path.hasPrefix("/player/watch/") || path.hasPrefix("/player/shows/") {
                    streamPath = "/kit-file/" + String(path.dropFirst("/player/".count))
                } else if path.hasPrefix("/player/content/") {
                    let key = String(path.dropFirst("/player/content/".count))
                    guard key.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else { return }
                    let part = URLComponents(url: url, resolvingAgainstBaseURL: true)?.queryItems?.first(where: { $0.name == "part" })?.value ?? "0"
                    guard let index = Int(part), (0...999999).contains(index) else { return }
                    streamPath = "/content-file/" + key + "?part=" + String(index)
                } else {
                    return
                }
                guard let stream = URL(string: streamPath, relativeTo: address)?.absoluteURL else { return }
                var stale = false
                let bookmark = UserDefaults.standard.data(forKey: "echoOffGridKitBookmark")
                let kit = bookmark.flatMap { try? URL(resolvingBookmarkData: $0, options: .withoutUI, relativeTo: nil, bookmarkDataIsStale: &stale) } ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/OffGrid/OffGrid Kit")
                let apps = [Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/VLC.app"), kit.appendingPathComponent("Apps/VLC.app"), URL(fileURLWithPath: "/Applications/VLC.app")]
                if !apps.contains(where: { EchoPlayMedia(webView.superview ?? webView, stream, $0) }) {
                    let alert = NSAlert()
                    alert.messageText = "The video player needs VLC."
                    alert.informativeText = "Install the signed VideoLAN VLC app in Applications or your kit’s Apps folder."
                    alert.runModal()
                }
                return
            }
            if url?.path == "/echolite", action.navigationType == .linkActivated, let window = webView.window, openEcho(in: window) {
                decisionHandler(.cancel)
                return
            }
            decisionHandler(action.shouldPerformDownload ? .download : .allow)
        }

        func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                     decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            let disposition = (response.response as? HTTPURLResponse)?
                .value(forHTTPHeaderField: "Content-Disposition")?.lowercased()
            decisionHandler(disposition?.hasPrefix("attachment") == true ? .download : .allow)
        }

        func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
            download.delegate = self
        }

        func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
            download.delegate = self
        }

        func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                      suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
            let panel = NSSavePanel()
            panel.nameFieldStringValue = suggestedFilename
            panel.begin { result in completionHandler(result == .OK ? panel.url : nil) }
        }
    }
}

private final class LibraryAccess {
    private var grants: [String: URL] = [:]

    func remember(_ url: URL, key: String) throws {
        let data = try url.bookmarkData(options: [.withSecurityScope, .securityScopeAllowOnlyReadAccess])
        UserDefaults.standard.set(data, forKey: key)
        _ = resolve(key)
    }

    func resolve(_ key: String) -> URL? {
        guard let data = UserDefaults.standard.data(forKey: key), !data.isEmpty else { return nil }
        var stale = false
        let scoped = try? URL(resolvingBookmarkData: data, options: [.withSecurityScope, .withoutUI],
                              relativeTo: nil, bookmarkDataIsStale: &stale)
        guard let url = scoped ?? (try? URL(resolvingBookmarkData: data, options: .withoutUI,
                                           relativeTo: nil, bookmarkDataIsStale: &stale)) else { return nil }
        if grants[key] != url {
            grants.removeValue(forKey: key)?.stopAccessingSecurityScopedResource()
            if url.startAccessingSecurityScopedResource() { grants[key] = url }
        }
        if stale || scoped == nil || !UserDefaults.standard.bool(forKey: key + "Scoped") {
            if let fresh = try? url.bookmarkData(options: [.withSecurityScope, .securityScopeAllowOnlyReadAccess]) {
                UserDefaults.standard.set(fresh, forKey: key)
                UserDefaults.standard.set(true, forKey: key + "Scoped")
            }
        }
        return url
    }
}

@main
struct EchoOffGridApp: App {
    @State private var servers = LocalServers()
    @State private var access = LibraryAccess()
    @State private var address: URL?
    @State private var showSetup = false
    @State private var installing = false
    @State private var setupOutput = ""
    @State private var launchError: String?
    @AppStorage("echoLiteApplicationBookmark") private var echoLiteApplicationBookmark = Data()
    @AppStorage("echoOffGridKitBookmark") private var kitBookmark = Data()

    var body: some Scene {
        WindowGroup("EchoOffGrid") {
            Group {
                if let address {
                    WorkspaceWebView(address: address).id(address)
                } else {
                    VStack(spacing: 14) {
                        if let launchError {
                            Text(launchError)
                            Button("Retry") { startDashboard() }
                        } else {
                            ProgressView("Opening EchoOffGrid…")
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(red: 0.035, green: 0.067, blue: 0.059))
                    .preferredColorScheme(.dark)
                }
            }
            .frame(minWidth: 520, minHeight: 380)
            .sheet(isPresented: $showSetup) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Set up EchoLite").font(.title2.bold())
                    Text("Connect EchoLite for local chat and visual understanding. Wikipedia and the reading dictionary are already available in EchoOffGrid.")
                    Text("The packaged EchoLite release requires about 3.45 GB of model files.").font(.caption)
                    if installing { ProgressView("Preparing local files…") }
                    if !setupOutput.isEmpty {
                        ScrollView { Text(setupOutput).font(.system(.caption, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(height: 150)
                    }
                    HStack {
                        Button("Use existing…") { chooseEchoLite() }.disabled(installing)
                        Button("Install EchoLite") { installEchoLite() }.disabled(installing)
                        Spacer()
                        Button("Browse content") { showSetup = false; if let base = address { address = URL(string: "/discover", relativeTo: base)?.absoluteURL } }
                    }
                }.padding(24).frame(width: 560).preferredColorScheme(.dark)
            }
            .task { if address == nil { startDashboard() } }
        }
        .defaultSize(width: 1060, height: 740)
        .commands {
            CommandMenu("Library") {
                Button("Choose OffGrid Kit…") { chooseKit() }
            }
            CommandMenu("EchoLite") {
                Button("Set up EchoLite…") { showSetup = true }
                Button("Choose EchoLite installation…") { chooseEchoLite() }
                Button("Show bundled EchoLite source") {
                    if let source = Bundle.main.url(forResource: "EchoLite-source", withExtension: "zip", subdirectory: "EchoOffGrid") {
                        NSWorkspace.shared.activateFileViewerSelecting([source])
                    }
                }
            }
        }
    }

    private func chooseKit() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select the OffGrid Kit folder."
        guard panel.runModal() == .OK, let folder = panel.url,
              FileManager.default.fileExists(atPath: folder.appendingPathComponent("02-Reference").path) else { return }
        do { try access.remember(folder, key: "echoOffGridKitBookmark") }
        catch { NSAlert(error: error).runModal(); return }
        servers.stop(script: Destination.echoOffGrid.url(in: Bundle.main.bundleURL))
        startDashboard()
    }

    private func echoLiteLauncher(for app: URL) -> URL? {
        guard Bundle(url: app)?.object(forInfoDictionaryKey: "CFBundleName") as? String == "EchoLite" else { return nil }
        let url = app.deletingLastPathComponent().appendingPathComponent("echolite")
        return FileManager.default.isExecutableFile(atPath: url.path) ? url : nil
    }

    private func installEchoLite() {
        guard !installing, let parent = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?.appendingPathComponent("EchoOffGrid"),
              let script = Bundle.main.url(forResource: "prepare-echolite", withExtension: "sh", subdirectory: "EchoOffGrid") else { return }
        do { try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true) }
        catch { setupOutput = error.localizedDescription; return }
        let install = parent.appendingPathComponent("EchoLite-Q4_K_M")
        guard !FileManager.default.fileExists(atPath: install.path) else {
            let app = install.appendingPathComponent("EchoLite.app")
            guard echoLiteLauncher(for: app) != nil else { setupOutput = "Existing installation is incomplete at " + install.path; return }
            echoLiteApplicationBookmark = (try? app.bookmarkData(options: .minimalBookmark)) ?? Data()
            servers.stop(script: Destination.echoOffGrid.url(in: Bundle.main.bundleURL))
            startDashboard()
            setupOutput = "Connected to the existing EchoLite installation."
            return
        }
        var stale = false
        let kit = (try? URL(resolvingBookmarkData: kitBookmark, options: .withoutUI, relativeTo: nil, bookmarkDataIsStale: &stale)) ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/OffGrid/OffGrid Kit")
        let archives = (try? FileManager.default.contentsOfDirectory(at: kit.appendingPathComponent("02-Reference"), includingPropertiesForKeys: nil)) ?? []
        let wiki = archives.filter { $0.lastPathComponent.hasPrefix("wikipedia_en") && $0.pathExtension == "zim" }.sorted { $0.lastPathComponent > $1.lastPathComponent }.first
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = [script.path, install.path, parent.appendingPathComponent("EchoLite Assets").path] + (wiki.map { [$0.path] } ?? [])
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = (env["PATH"] ?? "/usr/bin:/bin") + ":" + FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".cargo/bin").path + ":/opt/homebrew/bin"
        task.environment = env
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty else { handle.readabilityHandler = nil; return }
            let text = String(decoding: data, as: UTF8.self)
            DispatchQueue.main.async { setupOutput = String((setupOutput + text).suffix(5000)) }
        }
        task.terminationHandler = { finished in
            DispatchQueue.main.async {
                installing = false
                let app = install.appendingPathComponent("EchoLite.app")
                if finished.terminationStatus == 0, echoLiteLauncher(for: app) != nil {
                    echoLiteApplicationBookmark = (try? app.bookmarkData(options: .minimalBookmark)) ?? Data()
                    setupOutput += "\nEchoLite is ready."
                    servers.stop(script: Destination.echoOffGrid.url(in: Bundle.main.bundleURL))
                    startDashboard()
                } else {
                    setupOutput += "\nSetup stopped with exit code \(finished.terminationStatus)."
                }
            }
        }
        setupOutput = ""
        installing = true
        do { try task.run() } catch {
            installing = false
            setupOutput = error.localizedDescription
        }
    }

    private func chooseEchoLite() {
        let panel = NSOpenPanel()
        panel.message = "Select EchoLite.app inside its provisioned installation folder."
        panel.allowedContentTypes = [.applicationBundle]
        guard panel.runModal() == .OK, let selected = panel.url else { return }
        guard echoLiteLauncher(for: selected) != nil else {
            let alert = NSAlert()
            alert.messageText = "Choose a provisioned EchoLite installation."
            alert.runModal()
            return
        }
        do { try access.remember(selected, key: "echoLiteApplicationBookmark") }
        catch { NSAlert(error: error).runModal(); return }
        let script = Destination.echoOffGrid.url(in: Bundle.main.bundleURL)
        servers.stop(script: script)
        startDashboard()
    }

    private func startDashboard() {
        launchError = nil
        address = nil
        let launcher = access.resolve("echoLiteApplicationBookmark").flatMap { echoLiteLauncher(for: $0) }
        let item = Destination.echoOffGrid
        var kit = access.resolve("echoOffGridKitBookmark")
        // Older connected installations used this location without saving a grant.
        if kit == nil, kitBookmark.isEmpty, launcher != nil,
           !UserDefaults.standard.bool(forKey: "echoLegacyKitChecked") {
            let legacy = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/OffGrid/OffGrid Kit")
            if FileManager.default.isReadableFile(atPath: legacy.appendingPathComponent("02-Reference").path) {
                try? access.remember(legacy, key: "echoOffGridKitBookmark")
                kit = legacy
            }
            UserDefaults.standard.set(true, forKey: "echoLegacyKitChecked")
        }
        let arguments = item.arguments + ["--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
            + (kit.map { ["--kit", $0.path] } ?? [])
            + (launcher.map { ["--echolite", $0.path] } ?? [])
        servers.open(script: item.url(in: Bundle.main.bundleURL), arguments: arguments,
                     activates: true, inBrowser: false) { result in
            switch result {
            case .success(let url): address = url
            case .failure(let error): launchError = error.localizedDescription
            }
        }
    }
}
#elseif !SHORTCUT_AUDIT
@main
struct OffGridHomeApp: App {
    var body: some Scene {
        WindowGroup { HomeView() }
            .defaultSize(width: 920, height: 590)
    }
}
#endif
