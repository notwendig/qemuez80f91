#include "consoles.h"
#include "common.h"
#include <tuple>

namespace ez80 {
CamelTerminal::CamelTerminal(QWidget *parent) : QWidget(parent), display(new Terminal(this)) {
    setObjectName("camel24Console");
    display->setObjectName("camel24Terminal");
    display->setInterruptStopsSession(false);
    display->setCarriageReturnOnLinefeed(true);
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(display);
    connect(display, &Terminal::input, this, [this](const QByteArray &bytes) {
        if (ready && process.state() == QProcess::Running)
            process.write(bytes);
    });
    connect(&process, &QProcess::readyReadStandardOutput, this,
            [this] { output(process.readAllStandardOutput()); });
    connect(&process, &QProcess::readyReadStandardError, this,
            [this] { display->feed(process.readAllStandardError()); });
    connect(&process, &QProcess::errorOccurred, this,
            [this] { changed("CAMEL24: " + process.errorString()); });
    connect(&process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
            [this](int code, QProcess::ExitStatus) {
                changed(QString("CAMEL24 beendet (%1) · Neustart möglich").arg(code));
            });
}
CamelTerminal::~CamelTerminal() {
    process.disconnect(this);
    stopProcess(process);
}
void CamelTerminal::changed(const QString &message) {
    statusText = message;
    emit stateChanged();
}
void CamelTerminal::output(const QByteArray &bytes) {
    if (ready) {
        display->feed(bytes);
        return;
    }
    bootOutput += bytes;
    if (!bootStarted) {
        auto start = bootOutput.indexOf("Camel FORTH");
        auto end = start < 0 ? -1 : bootOutput.indexOf('\n', start);
        if (end < 0)
            return;
        banner = bootOutput.left(end + 1);
        bootStarted = true;
    } else if (!bootOutput.contains("\r\nOK "))
        return;
    bootOutput.clear();
    if (!bootstrap.isEmpty())
        process.write(bootstrap.takeFirst() + '\r');
    else {
        ready = true;
        display->feed(banner + "\r\n3 S\" F24ALL.F24\" LOAD  |  3 S\" NAME.F24\" SAVE\r\n");
        changed("CAMEL24 · Laufwerke · " + disks);
    }
}
static QStringList nativeArguments(const QString &image, const QString &root) {
    return {"-M", "ez80f91-freertos,ram-boot=on", "-kernel", image,
            "-display", "none", "-monitor", "none", "-serial", "none", "-nic", "none",
            "-chardev", "stdio,id=native-console", "-global", "ez80f91-hostfs.chardev=native-console",
            "-global", "ez80f91-hostfs.root=" + root,
            "-global", "ez80f91-memory.dev-dir=" + root,
            "-global", "ez80f91-memory.wd2797a=24", "-icount", "shift=5,sleep=off"};
}
void CamelTerminal::start() {
    if (process.state() != QProcess::NotRunning)
        return;
    const auto image = rootPath() + "/examples/camelf91/camel-hostfs.bin";
    if (!workspace.isValid() || !QFileInfo(image).isFile() || !QDir(disks).exists()) {
        changed("CAMEL24: ROM oder Laufwerksverzeichnis fehlt");
        return;
    }
    process.setWorkingDirectory(workspace.path());
    ready = bootStarted = false;
    bootOutput.clear();
    bootstrap.clear();
    for (const auto &line : readFile(rootPath() + "/examples/camelf91/file-words.f24").split('\n'))
        if (!line.trimmed().isEmpty())
            bootstrap << line;
    changed("CAMEL24 startet …");
    process.start(defaultQemu(), nativeArguments(image, disks));
}
void CamelTerminal::restart() {
    stopProcess(process);
    display->feed("\x1b[2J\x1b[H");
    start();
}

CpmTerminal::CpmTerminal(QWidget *parent) : QWidget(parent), display(new Terminal(this)) {
    setObjectName("nativeCpmConsole");
    display->setInterruptStopsSession(false);
    display->setCarriageReturnOnLinefeed(true);
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(display);
    connect(display, &Terminal::input, this, [this](const QByteArray &bytes) {
        if (process.state() == QProcess::Running)
            process.write(bytes);
    });
    connect(&process, &QProcess::readyReadStandardOutput, this,
            [this] { display->feed(process.readAllStandardOutput()); });
    connect(&process, &QProcess::readyReadStandardError, this,
            [this] { display->feed(process.readAllStandardError()); });
    connect(&process, &QProcess::started, this, [this] {
        statusText = "CP/M 2.2 · Laufwerke · " + root;
        emit stateChanged();
    });
    connect(&process, &QProcess::errorOccurred, this, [this] {
        statusText = process.errorString(); emit stateChanged();
    });
    connect(&process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
            [this](int code, QProcess::ExitStatus) {
                statusText = QString("CP/M beendet (%1)").arg(code); emit stateChanged();
            });
}
CpmTerminal::~CpmTerminal() {
    process.disconnect(this);
    stopProcess(process);
}
void CpmTerminal::start() {
    if (process.state() != QProcess::NotRunning)
        return;
    process.setWorkingDirectory(workspace.path());
    process.start(defaultQemu(), nativeArguments(rootPath() + "/examples/cpm_hostfs/cpm.bin", root));
}
void CpmTerminal::restart() {
    stopProcess(process);
    display->feed("\x1b[2J\x1b[H");
    start();
}

NetworkTerminal::NetworkTerminal(Protocol mode, quint16 service, QWidget *parent)
    : QWidget(parent), protocol(mode), port(service),
      display(new Terminal(this)),
      socket(mode == Tcp ? static_cast<QAbstractSocket *>(new QTcpSocket(this))
                         : static_cast<QAbstractSocket *>(new QUdpSocket(this))) {
    display->setInterruptStopsSession(false);
    display->setCarriageReturnOnLinefeed(true);
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setAlignment(Qt::AlignTop);
    layout->addWidget(display);
    retry.setSingleShot(true);
    retry.setInterval(2000);
    probe.setInterval(1000);
    connect(&probe, &QTimer::timeout, this, [this] {
        if (active && connected())
            socket->write("\n");
        else
            probe.stop();
    });
    connect(&retry, &QTimer::timeout, this, [this] {
        if (active && wanted)
            connectHost();
    });
    connect(display, &Terminal::input, this, &NetworkTerminal::input);
    connect(socket, &QAbstractSocket::connected, this, [this] {
        retry.stop();
        changed(QString("%1:%2 · %3").arg(host).arg(port).arg(
            protocol == Tcp ? "Verbunden" : "UDP bereit"));
        if (protocol == Monitor) {
            socket->write("\n");
            probe.start();
        }
        else if (protocol == Cli) {
            line.clear();
            display->feed("\r\nFreeRTOS CLI - help zeigt die Befehle\r\n> ");
        }
    });
    connect(socket, &QAbstractSocket::readyRead, this, &NetworkTerminal::receive);
    connect(socket, &QAbstractSocket::stateChanged, this, [this] { emit stateChanged(); });
    connect(socket, &QAbstractSocket::disconnected, this, [this] {
        changed("Verbindung beendet");
        if (active && wanted)
            retry.start();
    });
    connect(socket, &QAbstractSocket::errorOccurred, this, [this] {
        changed(socket->errorString());
        if (active && wanted)
            retry.start();
    });
}
NetworkTerminal::~NetworkTerminal() {
    retry.stop();
    probe.stop();
    // Child sockets close after C++ members are destroyed unless closed here.
    // Their disconnected/error callbacks must not touch those members then.
    socket->disconnect(this);
    socket->abort();
}
bool NetworkTerminal::connected() const {
    return socket->state() == QAbstractSocket::ConnectedState;
}
bool NetworkTerminal::connecting() const {
    return socket->state() == QAbstractSocket::HostLookupState ||
           socket->state() == QAbstractSocket::ConnectingState;
}
void NetworkTerminal::changed(const QString &message) {
    statusText = message;
    emit stateChanged();
}
void NetworkTerminal::setHost(const QString &value) {
    if (host == value.trimmed())
        return;
    disconnectHost();
    host = value.trimmed();
    visited = false;
}
void NetworkTerminal::setActive(bool value) {
    active = value;
    if (!active) {
        retry.stop();
        probe.stop();
    } else if (!visited || (wanted && !connected() && !connecting()))
        connectHost();
    else if (protocol == Monitor && connected()) {
        socket->write("\n");
        probe.start();
    }
}
void NetworkTerminal::connectHost() {
    retry.stop();
    probe.stop();
    if (host.isEmpty()) {
        changed("Gastadresse eingeben");
        return;
    }
    wanted = visited = true;
    socket->abort();
    changed(QString("Verbinde mit %1:%2 …").arg(host).arg(port));
    socket->connectToHost(host, port);
}
void NetworkTerminal::disconnectHost() {
    wanted = false;
    retry.stop();
    probe.stop();
    socket->abort();
    line.clear();
    changed("Getrennt");
}
void NetworkTerminal::receive() {
    if (protocol == Tcp) {
        display->feed(socket->readAll());
        return;
    }
    auto *udp = static_cast<QUdpSocket *>(socket);
    while (udp->hasPendingDatagrams()) {
        const auto data = udp->receiveDatagram().data();
        probe.stop();
        display->feed(data);
        if (protocol == Cli && data == "\r\n")
            display->feed("> ");
    }
}
void NetworkTerminal::input(const QByteArray &bytes) {
    if (!connected()) {
        changed("Nicht verbunden · Verbinden wählen");
        return;
    }
    if (protocol == Tcp) {
        socket->write(bytes);
        return;
    }
    if (protocol == Monitor) {
        if (bytes.contains('\r') || bytes.contains('\n'))
            socket->write("\n");
        return;
    }
    if (bytes.startsWith('\x1b'))
        return;
    for (unsigned char ch : bytes) {
        if (ch == '\r' || ch == '\n') {
            display->feed("\r\n");
            socket->write(line + '\n');
            line.clear();
        } else if (ch == 3 || ch == 21) {
            while (!line.isEmpty()) {
                line.chop(1);
                display->feed("\b \b");
            }
        } else if (ch == 8 || ch == 127) {
            if (!line.isEmpty()) {
                line.chop(1);
                display->feed("\b \b");
            }
        } else if (ch >= 32 && ch < 127 && line.size() < 4096) {
            line += char(ch);
            display->feed(QByteArray(1, char(ch)));
        }
    }
}

ConsoleTabs::ConsoleTabs(const QString &guestHost, QWidget *parent) : QWidget(parent) {
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    auto *address = new QHBoxLayout;
    address->addWidget(new QLabel("Gast:", this));
    host = new QLineEdit(guestHost, this);
    host->setObjectName("guestHost");
    host->setPlaceholderText("Hostname oder IP-Adresse");
    host->setMaximumWidth(230);
    address->addWidget(host);
    connection = new QPushButton("Verbinden", this);
    connection->setObjectName("connectionButton");
    connection->setFocusPolicy(Qt::NoFocus);
    address->addWidget(connection);
    status = new QLabel(this);
    status->setObjectName("connectionStatus");
    status->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
    status->setMinimumWidth(150);
    address->addWidget(status, 1);
    layout->addLayout(address);
    tabs = new QTabWidget(this);
    tabs->setObjectName("consoleTabs");
    uart = new Terminal(this);
    uart->setObjectName("uartTerminal");
    uart->setCarriageReturnOnLinefeed(true);
    tabs->addTab(uart, "UART0");
    cpm = new CpmTerminal(tabs);
    cpm->setRoot(rootPath() + "/cpm-files");
    tabs->addTab(cpm, "CP/M 2.2");
    connect(cpm, &CpmTerminal::stateChanged, this, &ConsoleTabs::refresh);
    const QList<std::tuple<QString, NetworkTerminal::Protocol, quint16>> services = {
        {"Monitor", NetworkTerminal::Monitor, 4060},
        {"CLI", NetworkTerminal::Cli, 4030},
        {"Diagnose", NetworkTerminal::Tcp, 4040}};
    for (const auto &[name, protocol, port] : services) {
        auto *page = new NetworkTerminal(protocol, port, tabs);
        page->setObjectName(name);
        page->setHost(guestHost);
        guests << page;
        tabs->addTab(page, name);
        connect(page, &NetworkTerminal::stateChanged, this, &ConsoleTabs::refresh);
    }
    camel = new CamelTerminal(tabs);
    camel->setDiskDirectory(rootPath() + "/cpm-files");
    tabs->addTab(camel, "CAMEL24");
    connect(camel, &CamelTerminal::stateChanged, this, &ConsoleTabs::refresh);
    layout->addWidget(tabs);
    connect(tabs, &QTabWidget::currentChanged, this, [this] {
        for (auto *guest : guests)
            guest->setActive(guest == current());
        refresh();
        if (tabs->currentWidget() == camel) {
            camel->start();
            camel->terminal()->setFocus();
        } else if (tabs->currentWidget() == cpm) {
            cpm->start();
            cpm->terminal()->setFocus();
        } else if (auto *guest = current())
            guest->terminal()->setFocus();
        else
            uart->setFocus();
    });
    connect(host, &QLineEdit::editingFinished, this, &ConsoleTabs::changeHost);
    connect(connection, &QPushButton::clicked, this, [this] {
        if (tabs->currentWidget() == camel) {
            camel->restart();
            camel->terminal()->setFocus();
            return;
        }
        if (tabs->currentWidget() == cpm) {
            cpm->restart();
            cpm->terminal()->setFocus();
            return;
        }
        auto *page = current();
        if (!page)
            return;
        if (page->connected() || page->connecting())
            page->disconnectHost();
        else {
            changeHost();
            if (!page->connected() && !page->connecting())
                page->connectHost();
        }
        page->terminal()->setFocus();
        refresh();
    });
    refresh();
}
void ConsoleTabs::hideUart() {
    tabs->removeTab(tabs->indexOf(uart));
    uart->hide();
}
NetworkTerminal *ConsoleTabs::current() const {
    return qobject_cast<NetworkTerminal *>(tabs->currentWidget());
}
void ConsoleTabs::changeHost() {
    for (auto *guest : guests)
        guest->setHost(host->text());
    if (auto *guest = current())
        guest->setActive(true);
    refresh();
}
void ConsoleTabs::refresh() {
    auto *page = current();
    bool forth = tabs->currentWidget() == camel;
    bool nativeCpm = tabs->currentWidget() == cpm;
    bool local = forth || nativeCpm;
    host->setEnabled(!local);
    connection->setEnabled(local || page != nullptr);
    connection->setText(local ? "Neustart" : !page ? "Verbinden" : page->connected() ? "Trennen" :
                        page->connecting() ? "Abbrechen" : "Verbinden");
    status->setText(forth ? camel->status() : nativeCpm ? cpm->status() : page ? page->status() : "UART0 · lokaler Emulator");
    status->setToolTip(status->text());
}
} // namespace ez80
