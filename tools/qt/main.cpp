#include "session.h"
#include <csignal>
#include <cmath>

using namespace ez80;
static void signalHandler(int) { interrupted = 1; }

int main(int argc, char **argv) {
    bool cli = false;
    for (int i = 1; i < argc; ++i) {
        QString arg = QString::fromLocal8Bit(argv[i]);
        cli = cli || arg == "--help" || arg == "-h" || arg == "--help-all" || arg == "--version" ||
              arg == "-v" || arg == "--headless" || arg == "--session" || arg == "--prepare-only" ||
              arg == "--test" || arg == "--serial" || arg.startsWith("--serial=");
    }
    if (cli && !qEnvironmentVariableIsSet("QT_QPA_PLATFORM"))
        qputenv("QT_QPA_PLATFORM", "offscreen");
    QApplication app(argc, argv);
    app.setApplicationName("ez80-platform");
    app.setApplicationVersion("1.0");
    app.setDesktopFileName("ez80-kit");
    QIcon kitIcon;
    for (int size : {16, 24, 32, 48, 64, 128, 256, 512})
        kitIcon.addFile(QString(":/icons/ez80-kit-%1.png").arg(size), QSize(size, size));
    app.setWindowIcon(kitIcon);
    QCommandLineParser parser;
    parser.setApplicationDescription(
        "Native Qt 6 platform tools for QEMU/eZ80F91: start, kit, demo, f24, zds-launch.");
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addPositionalArgument("command", "start (default), kit, demo, f24, zds-launch",
                                 "[command]");
    parser.addPositionalArgument("state", "Kit telemetry JSON (kit command only).", "[state]");
    auto value = [&](const QStringList &names, const QString &description,
                     const QString &placeholder, const QString &fallback = {}) {
        parser.addOption(QCommandLineOption(names, description, placeholder, fallback));
    };
    auto flag = [&](const QStringList &names, const QString &description) {
        parser.addOption(QCommandLineOption(names, description));
    };
    value({"qemu"}, "QEMU executable; default: QEMU_EZ80 or checkout build.", "path");
    value({"zds"}, "ZDS installation; default: ZDS_HOME or Wine installation.", "path");
    value({"port", "dbgport"}, "Debug port (1..65535); demo: enable debugger.", "port", "4040");
    value({"wd2797a", "devport"}, "WD2797A base port (decimal or 0x...).", "port", "0x1000");
    value({"dev"}, "Writable CP/M disk directory.", "directory");
    value({"fs-root"}, "Directory containing CP/M drive directories A/..P/ or image files A.img..P.img.", "directory");
    value({"hostname"}, "DHCP hostname; default: ez80<port>.", "name");
    value({"bridge"}, "Existing bridge, or none for offline operation.", "name", "br0");
    value({"bridge-helper"}, "QEMU bridge helper.", "path", "/usr/libexec/qemu-bridge-helper");
    value({"dhcp-server"}, "Expected DHCP server for demo lease checks.", "IPv4", "192.168.77.1");
    value({"out"}, "Demo/F24 build directory.", "directory");
    value({"wine-prefix"}, "F24 Wine prefix.", "directory", "/tmp/qemuez80f91-zds-wine");
    value({"nic"}, "F24/ZDS QEMU NIC backend.", "backend", "none");
    value({"bios"}, "Optional start ROM; ZDS launcher defaults to CAMEL ROM.", "path");
    value({"serial"}, "ZDS launcher: explicit QEMU serial backend instead of Qt UART.", "backend");
    value({"machine"}, "QEMU machine (start/zds-launch).", "name", "ez80f91-minimal");
    value({"seconds"}, "Stop after this many seconds (test: default 30).", "seconds");
    value({"qmp"}, "QMP Unix socket for standalone kit.", "path");
    value({"snapshot"}, "Save standalone kit preview as PNG and exit.", "path");
    for (int cs = 0; cs < 4; ++cs)
        value({QString("cs%1").arg(cs)}, "Chip-select type: ram, flash, none.", "type");
    flag({"run"}, "Resume CPU after bridge forwarding; default: wait for debugger.");
    flag({"kit"}, "Open kit with UART and guest terminal tabs.");
    flag({"camel24"}, "Select the CAMEL24 tab in a standalone kit window.");
    flag({"headless", "session"}, "UART on this terminal; no Qt windows.");
    flag({"launch"}, "Open native Qt UART window (default).");
    flag({"rebuild"}, "Rebuild firmware before starting demo/F24.");
    flag({"prepare-only"}, "Prepare demo/F24 firmware and project, then exit.");
    flag({"test"}, "Verify DHCP and UDP/TCP echo in demo; no windows.");
    flag({"no-views"}, "Do not open additional F24 debugger views.");
    flag({"verbose"}, "Enable Qt debug logging.");
    // Old launchers accepted these endpoints; native UART/GDB use private sockets.
    value({"gdb-port"}, "Legacy option; native debugger uses a private socket.", "port");
    value({"uart-port"}, "Legacy option; native UART uses a private socket.", "port");
    parser.process(app);
    try {
        Options o;
        auto args = parser.positionalArguments();
        if (!args.isEmpty())
            o.mode = args.takeFirst();
        if (!QStringList{"start", "kit", "demo", "f24", "zds-launch"}.contains(o.mode))
            fail("Unbekannter Befehl: " + o.mode);
        if (o.mode == "kit") {
            if (args.size() != 1)
                fail("kit benötigt die Telemetrie-JSON-Datei");
            o.state = args.takeFirst();
        }
        if (!args.isEmpty())
            fail("Unerwartete Positionsargumente: " + args.join(' '));
        if (parser.isSet("camel24") && o.mode != "kit")
            fail("--camel24 benötigt kit");
        bool ok;
        o.port = parser.value("port").toInt(&ok);
        if (!ok || o.port < 1 || o.port > 65535)
            fail("Debugport muss zwischen 1 und 65535 liegen.");
        o.devport = parser.value("wd2797a").toInt(&ok, 0);
        if (!ok || (o.devport < 0x100 && o.devport != 0x18) || o.devport > 0xfff8 ||
            (o.devport >= 0xfef9 && o.devport <= 0xff4b))
            fail("--wd2797a: Basis 0x18 (8 Bit) oder 0x100..0xfff8; 0xff00..0xff4b reserviert.");
        o.hostname =
            parser.isSet("hostname") ? parser.value("hostname") : QString("ez80%1").arg(o.port);
        if (!QRegularExpression("^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
                 .match(o.hostname)
                 .hasMatch())
            fail("--hostname: 1..63 ASCII-Buchstaben/Ziffern, Bindestriche nur im Inneren.");
        for (int cs = 0; cs < 4; ++cs) {
            o.cs[cs] = parser.value(QString("cs%1").arg(cs));
            if (!o.cs[cs].isEmpty() && !QStringList{"ram", "flash", "none"}.contains(o.cs[cs]))
                fail("--cs: ram, flash oder none benötigt");
        }
        if (parser.isSet("qemu"))
            o.qemu = parser.value("qemu");
        if (parser.isSet("zds"))
            o.zds = QFileInfo(parser.value("zds")).absoluteFilePath();
        o.dev = parser.value("dev");
        if (parser.isSet("fs-root"))
            o.fsRoot = QFileInfo(parser.value("fs-root")).absoluteFilePath();
        o.out = parser.value("out");
        o.bridge = parser.value("bridge");
        o.helper = parser.value("bridge-helper");
        o.server = parser.value("dhcp-server");
        if (QHostAddress(o.server).protocol() != QAbstractSocket::IPv4Protocol)
            fail("--dhcp-server benötigt eine IPv4-Adresse");
        o.nic = parser.value("nic");
        o.bios = parser.value("bios");
        o.machine = parser.value("machine");
        o.serial = parser.value("serial");
        if (parser.isSet("serial") && (o.serial.isEmpty() || o.mode != "zds-launch"))
            fail("--serial benötigt zds-launch und einen UART-Backendnamen");
        o.winePrefix = parser.value("wine-prefix");
        o.noViews = parser.isSet("no-views");
        o.run = parser.isSet("run");
        o.kit = parser.isSet("kit");
        o.headless = cli;
        o.rebuild = parser.isSet("rebuild");
        o.prepareOnly = parser.isSet("prepare-only");
        o.test = parser.isSet("test");
        o.debug = parser.isSet("port");
        if (parser.isSet("verbose"))
            QLoggingCategory::setFilterRules("*.debug=true");
        if (o.mode == "demo") {
            if (o.test && o.debug)
                fail("--test und --dbgport sind nicht kombinierbar");
            if (o.bridge == "none")
                fail("demo benötigt eine Netzwerkbridge");
            o.run = !o.debug;
        }
        if (o.mode == "zds-launch" && o.bios.isEmpty())
            o.bios = rootPath() + "/examples/camelf91/camel.bin";
        if ((o.prepareOnly || o.rebuild) && o.mode != "demo" && o.mode != "f24")
            fail("Build-Optionen benötigen demo oder f24");
        if (o.test && o.mode != "demo")
            fail("--test benötigt demo");
        if (parser.isSet("seconds")) {
            o.seconds = parser.value("seconds").toDouble(&ok);
            if (!ok || !std::isfinite(o.seconds) || o.seconds <= 0)
                fail("--seconds muss größer als null sein");
        } else if (o.test)
            o.seconds = 30;
        if (o.mode == "f24" && o.port != 4040)
            fail("ZDS Ethernet Smart Cable verwendet Port 4040");
        std::signal(SIGINT, signalHandler);
        std::signal(SIGTERM, signalHandler);
        std::signal(SIGHUP, signalHandler);
        if (o.mode == "kit") {
            Qmp qmp;
            QString path = parser.isSet("qmp") ? parser.value("qmp")
                                               : o.state.left(o.state.lastIndexOf('.')) + ".qmp";
            Kit kit(o.state, o.port, &qmp, o.hostname);
            kit.setDiskDirectory(o.fsRoot);
            if (!parser.isSet("snapshot"))
                kit.hideUart();
            kit.show();
            if (parser.isSet("camel24")) {
                auto *tabs = kit.findChild<QTabWidget *>("consoleTabs");
                tabs->setCurrentWidget(kit.findChild<CamelTerminal *>());
            }
            qmp.open(path);
            QTimer retry;
            QObject::connect(&retry, &QTimer::timeout, &app, [&] {
                if (!qmp.ready)
                    qmp.open(path);
            });
            retry.start(500);
            QTimer timer;
            QObject::connect(&timer, &QTimer::timeout, &app, [&] {
                if (interrupted) {
                    kit.release();
                    app.quit();
                }
            });
            timer.start(50);
            if (parser.isSet("snapshot"))
                QTimer::singleShot(200, &app, [&] {
                    if (!kit.grab().save(parser.value("snapshot"), "PNG")) {
                        qCritical("Snapshot konnte nicht gespeichert werden");
                        app.exit(1);
                    } else
                        app.quit();
                });
            return app.exec();
        }
        Session session(o);
        QTimer::singleShot(0, &session, [&] {
            try {
                session.start();
            } catch (const std::exception &e) {
                session.finish(1, QString::fromUtf8(e.what()));
            }
        });
        return app.exec();
    } catch (const std::exception &e) {
        qCritical().noquote() << e.what();
        return 2;
    }
}
