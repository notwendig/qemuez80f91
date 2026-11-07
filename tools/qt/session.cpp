#include "session.h"
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>

namespace ez80 {
Session::Session(Options options) : o(std::move(options)) {
    connect(&poll, &QTimer::timeout, this, [this] {
        try {
            tick();
        } catch (const std::exception &e) {
            finish(1, QString::fromUtf8(e.what()));
        }
    });
    connect(&qmp, &Qmp::error, this, [this](const QString &error) {
        if (stopping)
            return;
        qmpOpening = false;
        if (resumePending) {
            finish(1, "CPU-Start fehlgeschlagen: " + error);
            return;
        }
        if (resumed)
            message("QMP: " + error);
    });
    connect(&process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError e) {
        if (e == QProcess::FailedToStart)
            finish(1, process.errorString());
    });
    connect(&process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
            [this](int code, QProcess::ExitStatus exit) {
                if (!stopping)
                    finish(exit == QProcess::NormalExit ? code : 1,
                           code || exit != QProcess::NormalExit ? "QEMU beendet; siehe Protokoll."
                                                                : QString());
            });
    connect(&process, &QProcess::readyReadStandardError, this,
            [this] { message(QString::fromLocal8Bit(process.readAllStandardError())); });
    connect(&process, &QProcess::readyReadStandardOutput, this, [this] {
        auto bytes = process.readAllStandardOutput();
        if (o.serial == "stdio")
            data(bytes);
        else
            message(QString::fromLocal8Bit(bytes));
    });
    connect(&uartServer, &QLocalServer::newConnection, this, [this] {
        if (uart) {
            uartServer.nextPendingConnection()->deleteLater();
            return;
        }
        uart = uartServer.nextPendingConnection();
        connect(uart, &QLocalSocket::readyRead, this, [this] { data(uart->readAll()); });
    });
}
Session::~Session() {
    stopping = true;
    status = nullptr;
    terminal = nullptr;
    if (window)
        window->removeEventFilter(this);
    if (kit)
        kit->removeEventFilter(this);
    if (kit)
        kit->release();
    stopProcess(views);
    stopProcess(ide);
    stopProcess(process);
    if (rawTerminal) {
        tcsetattr(STDIN_FILENO, TCSADRAIN, savedTerminal);
        delete savedTerminal;
    }
    uartServer.close();
    if (!qmpPath.isEmpty())
        QFile::remove(qmpPath);
    if (!uartPath.isEmpty())
        QFile::remove(uartPath);
    if (!kitPath.isEmpty())
        QFile::remove(kitPath);
}
void Session::message(const QString &text) {
    if (text.isEmpty())
        return;
    fprintf(stderr, "%s\n", qPrintable(text));
    fflush(stderr);
    if (status)
        status->setText(text.section('\n', 0, 0));
}
void Session::data(const QByteArray &bytes) {
    if (terminal)
        terminal->feed(bytes);
    else {
        fwrite(bytes.constData(), 1, size_t(bytes.size()), stdout);
        fflush(stdout);
    }
    uartLog.write(bytes);
    uartLog.flush();
    if (o.test)
        output += bytes;
}
void Session::start() {
    if (!QFileInfo(o.qemu).isExecutable())
        fail("QEMU nicht ausführbar: " + o.qemu);
    o.qemu = QFileInfo(o.qemu).absoluteFilePath();
    runtime = QString("/tmp/ez80f91-%1").arg(getuid());
    if (!QDir().mkpath(runtime))
        fail("Laufzeitverzeichnis fehlt: " + runtime);
    chmod(QFile::encodeName(runtime).constData(), 0700);
    if (o.mode == "demo" || o.mode == "f24") {
        if (o.out.isEmpty())
            o.out = rootPath() + (o.mode == "demo" ? "/build/ztp-tcpudp-ram" : "/build/f24");
        o.out = QFileInfo(o.out).absoluteFilePath();
        projectLock = std::make_unique<PortLock>(o.out + "/start.lock");
        if (o.mode == "f24")
            for (const auto &name : {"Zds2Ide.exe", "nxEz80EthernetSC.dll"})
                if (!QFileInfo(o.zds + "/bin/" + name).isFile())
                    fail("ZDS-Datei fehlt: " + o.zds + "/bin/" + name);
        if (o.mode == "demo")
            prepareDemo(o);
        else
            prepareF24(o);
        if (o.prepareOnly) {
            message(o.out);
            QCoreApplication::quit();
            return;
        }
    }
    bool debug = o.mode != "demo" || o.debug;
    if (debug) {
        portLock = std::make_unique<PortLock>(runtime + QString("/%1.lock").arg(o.port));
        checkPort(o.port);
    }
    const auto base = (o.mode == "demo") ? o.out + "/demo" : runtime + QString("/%1").arg(o.port);
    qmpPath = base + ".qmp";
    uartPath = base + ".uart.sock";
    if (o.kit)
        kitPath = base + ".kit.json";
    uartLog.setFileName(o.mode == "demo" ? o.out + "/uart.log" : base + ".uart.log");
    if (!uartLog.open(QIODevice::WriteOnly | QIODevice::Truncate))
        fail(uartLog.errorString());
    QFile::remove(qmpPath);
    QLocalServer::removeServer(uartPath);
    if (!kitPath.isEmpty())
        QFile::remove(kitPath);
    uartServer.setSocketOptions(QLocalServer::UserAccessOption);
    if (!uartServer.listen(uartPath))
        fail(uartServer.errorString());
    QString machine =
        o.mode == "f24" || o.mode == "demo" ? "ez80f91-freertos,ram-boot=on" : o.machine;
    if (o.mode == "demo")
        machine += ",osc-frequency=5000000";
    if (o.mode == "start")
        machine += ",cs3=none";
    for (int i = 0; i < 4; ++i)
        if (!o.cs[i].isEmpty())
            machine += QString(",cs%1=%2").arg(i).arg(o.cs[i]);
    QStringList args = {"-M",
                        machine,
                        "-S",
                        "-display",
                        "none",
                        "-monitor",
                        "none",
                        "-qmp",
                        "unix:" + qmpPath + ",server=on,wait=off",
                        "-rtc",
                        "base=utc,clock=host"};
    if (o.serial.isEmpty())
        args << "-chardev" << "socket,id=uart,path=" + uartPath << "-serial" << "chardev:uart";
    else
        args << "-serial" << o.serial;
    if (o.serial == "stdio")
        process.setInputChannelMode(QProcess::ForwardedInputChannel);
    if (debug)
        args << QString("--dbgport=%1").arg(o.port) << "--scan-dev";
    if (o.mode == "f24")
        args << "-kernel" << o.out + "/camel.bin";
    else if (o.mode == "demo")
        args << "-kernel" << o.out + "/tcpudp.bin";
    else if (!o.bios.isEmpty())
        args << "-bios" << QFileInfo(o.bios).absoluteFilePath();
    if (o.mode == "start") {
        QProcess check;
        check.start(o.qemu, {"-M", "ez80f91-minimal,help"});
        if (!check.waitForFinished(10000) || check.exitCode())
            fail("QEMU-Maschinenprüfung fehlgeschlagen");
        auto help = check.readAllStandardOutput() + check.readAllStandardError();
        if (!help.contains("wd2797a=") || !help.contains("hostname="))
            fail("QEMU unterstützt WD2797A/Hostname nicht; QEMU aktualisieren.");
        auto dir = diskDirectory(o.port, o.dev);
        args << "-global" << "ez80f91-memory.dev-dir=" + dir << "-global"
             << QString("ez80f91-memory.wd2797a=%1").arg(o.devport) << "-global"
             << "ez80f91-memory.hostname=" + o.hostname;
        message(QString("CP/M: %1; WD2797A %2; Hostname: %3")
                    .arg(dir)
                    .arg(o.devport, 0, 16)
                    .arg(o.hostname));
    }
    if (o.kit)
        args << "-global" << "ez80f91-memory.kit-led-state=" + kitPath;
    if (o.mode == "f24" || o.mode == "zds-launch") {
        args << "-nic" << o.nic;
    } else if (o.bridge == "none")
        args << "-nic" << "none";
    else {
        previousPorts = bridgeMembers(o.bridge);
        args << "-nic" << QString("bridge,id=wire,br=%1,helper=%2").arg(o.bridge, o.helper)
             << "-global" << "ez80f91-emac.phy-addr=31";
        args << qemuHostLinkOptions(o.qemu, o.bridge);
    }
    if (o.mode == "start" || o.mode == "demo")
        args << "-icount" << "shift=5,sleep=off";
    if (o.mode == "demo") {
        args << "-object"
             << "filter-dump,id=demo-capture,netdev=wire,file=" + o.out + "/network.pcap" << "-d"
             << "unimp,guest_errors" << "-D" << o.out + "/devices.log";
    }
    if (o.mode == "demo" || o.mode == "f24") {
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.setStandardOutputFile(o.out + "/qemu.log");
    }
    if (!o.headless) {
        QWidget *mainWindow;
        if (o.kit) {
            kit = std::make_unique<Kit>(kitPath, o.port, &qmp, o.hostname);
            kit->setDiskDirectory(o.fsRoot);
            terminal = kit->uartTerminal();
            status = kit->statusLabel();
            mainWindow = kit.get();
        } else {
            window = std::make_unique<QWidget>();
            window->setWindowTitle(QString("eZ80f91.%1 — UART0").arg(o.port));
            auto *layout = new QVBoxLayout(window.get());
            terminal = new Terminal;
            terminal->setCarriageReturnOnLinefeed(true);
            status = new QLabel;
            layout->addWidget(terminal);
            layout->addWidget(status);
            mainWindow = window.get();
        }
        connect(terminal, &Terminal::input, this, [this](const QByteArray &bytes) {
            if (uart)
                uart->write(bytes);
        });
        connect(terminal, &Terminal::stopRequested, this, [this] { finish(); });
        mainWindow->show();
        terminal->setFocus();
        connect(qApp, &QGuiApplication::lastWindowClosed, this, [this] { finish(); });
        mainWindow->installEventFilter(this);
    } else if (!o.test && o.serial.isEmpty()) {
        stdinNotifier =
            std::make_unique<QSocketNotifier>(STDIN_FILENO, QSocketNotifier::Read, this);
        connect(stdinNotifier.get(), &QSocketNotifier::activated, this, [this] {
            char buffer[4096];
            auto n = ::read(STDIN_FILENO, buffer, sizeof buffer);
            if (n <= 0) {
                stdinNotifier->setEnabled(false);
                return;
            }
            auto bytes = QByteArray(buffer, n);
            if (bytes.contains('\x03') || bytes.contains('\x1d'))
                finish();
            else if (uart)
                uart->write(bytes);
        });
        if (isatty(STDIN_FILENO)) {
            auto *saved = new termios;
            if (!tcgetattr(STDIN_FILENO, saved)) {
                auto raw = *saved;
                cfmakeraw(&raw);
                if (!tcsetattr(STDIN_FILENO, TCSANOW, &raw)) {
                    rawTerminal = true;
                    savedTerminal = saved;
                } else
                    delete saved;
            } else
                delete saved;
        }
    }
    if (o.test) {
        networkTest = std::make_unique<NetworkTest>(o.server);
        connect(networkTest.get(), &NetworkTest::failed, this,
                [this](const QString &e) { finish(1, e); });
    }
    const int lockFd = portLock ? portLock->handle() : -1;
    process.setChildProcessModifier([lockFd] {
        if (lockFd >= 0)
            fcntl(lockFd, F_SETFD, 0);
    });
    process.start(o.qemu, args);
    elapsed.start();
    poll.start(50);
    message(QString("eZ80f91.%1 — %2; Strg+C beendet QEMU und speichert Flash.")
                .arg(o.port)
                .arg(o.run ? "CPU startet" : "CPU wartet auf Debugger"));
}
void Session::startIde() {
    ideStarted = true;
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("WINEPREFIX", QFileInfo(o.winePrefix).absoluteFilePath());
    env.insert("WINEDEBUG", "-all");
    ide.setProcessEnvironment(env);
    ide.setWorkingDirectory(o.out);
    ide.setProcessChannelMode(QProcess::MergedChannels);
    ide.setStandardOutputFile(o.out + "/ide.log");
    QFile::remove(o.out + "/zds-session.log");
    writeFile(o.out + "/start.pid", QByteArray::number(QCoreApplication::applicationPid()) + '\n');
    ide.start("wine", {o.zds + "/bin/Zds2Ide.exe", "@" + windowsPath(o.out + "/start.cmd")});
    message("ZDS II startet mit Quellcode; CPU wartet auf F5.");
}
void Session::tick() {
    if (interrupted) {
        finish();
        return;
    }
    if (stopping)
        return;
    if (!qmp.ready && !qmpOpening && QFileInfo::exists(qmpPath)) {
        qmpOpening = true;
        qmp.open(qmpPath);
    }
    if (!resumed && elapsed.elapsed() > 35000) {
        finish(1, "QMP/Bridge-Startzeit überschritten");
        return;
    }
    if (!resumed && !resumePending && qmp.ready) {
        bool bridge = o.mode != "f24" && o.mode != "zds-launch" && o.bridge != "none";
        if (bridge && !bridgeForwarding(o.bridge, previousPorts))
            return;
        if (o.run) {
            resumePending = true;
            qmp.call("cont", {}, [this](QJsonValue) {
                if (stopping)
                    return;
                resumePending = false;
                resumed = true;
                running.start();
                message("CPU läuft; UART verbunden.");
            });
        } else {
            resumed = true;
            running.start();
            message("CPU wartet auf ZDS II.");
        }
    }
    if (o.mode == "f24" && resumed) {
        if (!ideStarted)
            startIde();
        else if (ide.state() == QProcess::NotRunning) {
            finish(1, "ZDS II beendet; siehe ide.log");
            return;
        }
        if (!ideReady) {
            QFile log(o.out + "/zds-session.log");
            auto text = log.open(QIODevice::ReadOnly) ? log.readAll() : QByteArray();
            if (text.contains("[ERROR]")) {
                finish(1, "ZDS meldet einen Fehler; siehe zds-session.log");
                return;
            }
            const QRegularExpression ready("^F24_READY PC=[0-9a-fA-F]+\\r?$",
                                           QRegularExpression::MultilineOption);
            if (ready.match(QString::fromLocal8Bit(text)).hasMatch() &&
                text.contains("Loading file ") && text.contains(" successful.")) {
                ideReady = true;
                message("CAMEL24 bereit: F5 startet, F11 schaltet einzeln.");
                if (!o.noViews) {
                    auto source = rootPath() + "/tools/zds/views.c", helper = o.out + "/views.exe";
                    if (!QFileInfo::exists(helper) ||
                        QFileInfo(helper).lastModified() < QFileInfo(source).lastModified())
                        runCommand("i686-w64-mingw32-gcc",
                                   {"-Wall", "-Wextra", source, "-o", helper});
                    views.setProcessEnvironment(ide.processEnvironment());
                    views.setStandardOutputFile(o.out + "/views.log");
                    views.start("wine",
                                {helper, "--open", windowsPath(o.zds + "/bin/Zds2Ide.exe")});
                }
            } else if (running.elapsed() > 90000) {
                finish(1, "ZDS-Debugstart nach 90 Sekunden nicht bestätigt");
                return;
            }
        }
    }
    if (o.mode == "demo" && resumed) {
        auto leases = dhcpLeases(o.out + "/network.pcap");
        for (auto lease : leases) {
            auto l = lease.toObject();
            if (l["mac"] == "00:90:23:00:01:01" && l["server"] != o.server) {
                finish(1, "Falscher DHCP-Server: " + l["server"].toString());
                return;
            }
        }
        if (networkTest && uart) {
            networkTest->advance(output, leases, [this](QByteArray bytes) { uart->write(bytes); });
            if (networkTest->done()) {
                message("PASS: DHCP, 1000 Byte UDP und 4000 Byte TCP");
                finish();
                return;
            }
        }
    }
    if (o.seconds > 0 && running.isValid() && running.elapsed() >= o.seconds * 1000)
        finish();
}
void Session::finish(int code, const QString &error) {
    if (stopping)
        return;
    stopping = true;
    poll.stop();
    if (!error.isEmpty())
        message(error);
    if (kit)
        kit->release();
    stopProcess(views);
    stopProcess(ide);
    stopProcess(process);
    if (o.mode == "demo" && !o.prepareOnly) {
        QJsonObject report{{"bridge", o.bridge},
                           {"expected_dhcp_server", o.server},
                           {"leases", dhcpLeases(o.out + "/network.pcap")}};
        if (networkTest) {
            auto result = networkTest->report();
            for (auto i = result.begin(); i != result.end(); ++i)
                report[i.key()] = i.value();
            if (!networkTest->done()) {
                code = 1;
                message("Netzwerktest nicht abgeschlossen; siehe network.json");
            }
        }
        try {
            writeFile(o.out + "/network.json", QJsonDocument(report).toJson());
        } catch (const std::exception &e) {
            message(e.what());
            code = 1;
        }
    }
    QCoreApplication::exit(code);
}
bool Session::eventFilter(QObject *object, QEvent *event) {
    if ((object == window.get() || object == kit.get()) && event->type() == QEvent::Close)
        finish();
    return QObject::eventFilter(object, event);
}
} // namespace ez80
