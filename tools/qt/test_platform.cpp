#include "common.h"
#include "network.h"
#include "terminal.h"
#include "qmp.h"
#include "projects.h"
#include "kit.h"
#include <QtTest>
#include <QLocalServer>
#include <QtEndian>
using namespace ez80;
class PlatformTest : public QObject {
    Q_OBJECT
  private slots:
    void terminal() {
        Terminal t;
        QCOMPARE(t.characterSize(), QSize(80, 40));
        QCOMPARE(t.text().split('\n').size(), 40);
        for (const auto &line : t.text().split('\n'))
            QCOMPARE(line.size(), 80);
        t.feed("hello\rX\x1b[2;3HY");
        QCOMPARE(t.text().section('\n', 0, 0).left(5), "Xello");
        QCOMPARE(t.text().section('\n', 1, 1).mid(2, 1), "Y");
        t.feed("\x1b[2J\x1b[Habc\bX");
        QCOMPARE(t.text().left(3), "abX");
        t.feed("\x1b[");
        t.feed("2K");
        QVERIFY(t.text().section('\n', 0, 0).trimmed().isEmpty());
        QSignalSpy input(&t, &Terminal::input);
        QTest::keyClick(&t, Qt::Key_Return);
        QCOMPARE(input.takeFirst().first().toByteArray(), QByteArray("\r"));
    }
    void camel24Tab() {
        if (!QFileInfo(defaultQemu()).isExecutable())
            QSKIP("QEMU executable unavailable");
        ConsoleTabs consoles("127.0.0.1");
        auto *tabs = consoles.findChild<QTabWidget *>("consoleTabs");
        auto *camel = consoles.findChild<CamelTerminal *>();
        QVERIFY(tabs && camel);
        QVERIFY(camel->terminal()->text().trimmed().isEmpty());
        tabs->setCurrentWidget(camel);
        QTRY_VERIFY_WITH_TIMEOUT(camel->terminal()->text().contains("Camel FORTH"), 10000);
        auto *host = consoles.findChild<QLineEdit *>("guestHost");
        QVERIFY(!host->isEnabled());
        auto *button = consoles.findChild<QPushButton *>("connectionButton");
        QCOMPARE(button->text(), QString("Neustart"));
        QTest::keyClicks(camel->terminal(), "DECIMAL 123 456 + .");
        QTest::keyClick(camel->terminal(), Qt::Key_Return);
        QTRY_VERIFY_WITH_TIMEOUT(camel->terminal()->text().contains("579"), 5000);
        // Switching consoles must preserve the Forth dictionary and stack.
        QTest::keyClicks(camel->terminal(), ": KITTEST 9876 ;");
        QTest::keyClick(camel->terminal(), Qt::Key_Return);
        QTRY_VERIFY(camel->terminal()->text().contains("KITTEST 9876"));
        tabs->setCurrentIndex(0);
        QVERIFY(host->isEnabled());
        tabs->setCurrentWidget(camel);
        QTest::keyClicks(camel->terminal(), "KITTEST .");
        QTest::keyClick(camel->terminal(), Qt::Key_Return);
        QTRY_VERIFY_WITH_TIMEOUT(camel->terminal()->text().contains("KITTEST . 9876"), 5000);
        QTest::mouseClick(button, Qt::LeftButton);
        QTRY_VERIFY_WITH_TIMEOUT(camel->terminal()->text().contains("Camel FORTH"), 10000);
        QVERIFY(!camel->terminal()->text().contains("KITTEST"));
    }
    void camel24Files() {
        if (!QFileInfo(defaultQemu()).isExecutable())
            QSKIP("QEMU unavailable");
        QTemporaryDir dir;
        QVERIFY(QDir(dir.path()).mkdir("D"));
        QVERIFY(QDir(dir.path()).mkdir("A"));
        writeFile(dir.filePath("D/keep.f24"), ": KEEP 123 ;\n");
        writeFile(dir.filePath("D/f24all.f24"), readFile(rootPath() + "/examples/camelf91/f24all.f24"));
        CamelTerminal camel;
        camel.setDiskDirectory(dir.path());
        auto send = [&](const char *text) {
            QTest::keyClicks(camel.terminal(), text);
            QTest::keyClick(camel.terminal(), Qt::Key_Return);
        };
        camel.start();
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("Camel FORTH"), 10000);
        send(": ANSWER 4242 ;");
        QTRY_VERIFY(camel.terminal()->text().contains("OK"));
        send("3 S\" ANSWER.F24\" SAVE");
        QTRY_VERIFY_WITH_TIMEOUT(QFileInfo(dir.filePath("D/answer.f24")).exists(), 5000);
        QCOMPARE(readFile(dir.filePath("D/answer.f24")), QByteArray(": ANSWER 4242 ;\n"));
        QCOMPARE(readFile(dir.filePath("D/keep.f24")), QByteArray(": KEEP 123 ;\n"));
        CpmTerminal cpm;
        cpm.setRoot(dir.path());
        cpm.start();
        QTRY_VERIFY_WITH_TIMEOUT(cpm.terminal()->text().contains("a>"), 10000);
        QTest::keyClicks(cpm.terminal(), "D:");
        QTest::keyClick(cpm.terminal(), Qt::Key_Return);
        QTRY_VERIFY(cpm.terminal()->text().contains("d>"));
        QTest::keyClicks(cpm.terminal(), "DIR");
        QTest::keyClick(cpm.terminal(), Qt::Key_Return);
        QTRY_VERIFY(cpm.terminal()->text().contains("ANSWER"));
        camel.restart();
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("Camel FORTH"), 10000);
        send(": RELOAD 3 S\" ANSWER.F24\" LOAD ;");
        send("RELOAD");
        send("ANSWER .");
        QTRY_VERIFY(camel.terminal()->text().contains("ANSWER . 4242"));
        send("16 S\" BAD.F24\" SAVE");
        QTRY_VERIFY(camel.terminal()->text().contains("DRIVE 0..15"));
        QVERIFY(!QFileInfo(dir.filePath("D/bad.f24")).exists());
        send("3 S\" MISSING.F24\" LOAD");
        QTRY_VERIFY(camel.terminal()->text().contains("FILE ERROR"));
        send("1 2 + .");
        QTRY_VERIFY(camel.terminal()->text().contains("1 2 + . 3"));
        camel.restart();
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("Camel FORTH"), 10000);
        send("3 S\" F24ALL.F24\" LOAD");
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("TESTS 198 FAILURES 0"), 30000);
        QVERIFY2(camel.terminal()->text().contains("TESTS 198 FAILURES 0"),
                 qPrintable(camel.terminal()->text()));
    }
    void camel24ImageFiles() {
        if (QStandardPaths::findExecutable("mkfs.cpm").isEmpty() ||
            QStandardPaths::findExecutable("cpmcp").isEmpty())
            QSKIP("cpmtools unavailable");
        QTemporaryDir dir;
        QVERIFY(QDir(dir.path()).mkdir("A"));
        const QString image = dir.filePath("D.img");
        writeFile(image, QByteArray(4194304, char(0xe5)));
        auto cpmtool = [&](const QString &program, const QStringList &args) {
            QProcess proc;
            proc.setWorkingDirectory(rootPath() + "/images/cpm");
            proc.start(program, program == "cpmcp" ? QStringList{"-T", "logical"} + args : args);
            return proc.waitForFinished(10000) && proc.exitCode() == 0;
        };
        QVERIFY(cpmtool("mkfs.cpm", {"-f", "4mb-hd", image}));
        QVERIFY(cpmtool("cpmcp", {"-f", "4mb-hd", image,
            rootPath() + "/examples/camelf91/f24all.f24", "0:F24ALL.F24"}));
        CamelTerminal camel;
        camel.setDiskDirectory(dir.path());
        auto send = [&](const char *text) {
            QTest::keyClicks(camel.terminal(), text);
            QTest::keyClick(camel.terminal(), Qt::Key_Return);
        };
        camel.start();
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("Camel FORTH"), 10000);
        send("3 S\" F24ALL.F24\" LOAD");
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("TESTS 198 FAILURES 0"), 30000);
        camel.restart();
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("Camel FORTH"), 10000);
        send(": ANSWER 4242 ;");
        send("3 S\" ANSWER.F24\" SAVE");
        send("77 .");
        QTRY_VERIFY2(camel.terminal()->text().contains("77 . 77"),
                     qPrintable(camel.terminal()->text()));
        QVERIFY(cpmtool("cpmcp", {"-f", "4mb-hd", image, "0:ANSWER.F24", dir.filePath("saved.f24")}));
        const auto saved = readFile(dir.filePath("saved.f24"));
        QVERIFY2(saved.startsWith(": ANSWER 4242 ;\n"), qPrintable(QString::fromLatin1(saved.toHex())));
        CpmTerminal cpm;
        cpm.setRoot(dir.path());
        cpm.start();
        QTRY_VERIFY_WITH_TIMEOUT(cpm.terminal()->text().contains("a>"), 10000);
        QTest::keyClicks(cpm.terminal(), "DIR D:");
        QTest::keyClick(cpm.terminal(), Qt::Key_Return);
        QTRY_VERIFY(cpm.terminal()->text().contains("ANSWER"));
        camel.restart();
        QTRY_VERIFY_WITH_TIMEOUT(camel.terminal()->text().contains("Camel FORTH"), 10000);
        send("3 S\" ANSWER.F24\" LOAD");
        send("ANSWER .");
        QTRY_VERIFY(camel.terminal()->text().contains("ANSWER . 4242"));
    }
    void networkTerminals() {
        QTcpServer tcp;
        QVERIFY(tcp.listen(QHostAddress::LocalHost, 0));
        NetworkTerminal cpm(NetworkTerminal::Tcp, tcp.serverPort());
        cpm.setHost("127.0.0.1");
        QVERIFY(!cpm.connected());
        cpm.setActive(true);
        QTRY_VERIFY(tcp.hasPendingConnections());
        auto *peer = tcp.nextPendingConnection();
        QTRY_VERIFY(cpm.connected());
        peer->write("CP/M 2.2\r\nA>");
        QTRY_VERIFY(cpm.terminal()->text().contains("A>"));
        QSignalSpy stop(cpm.terminal(), &Terminal::stopRequested);
        QTest::keyClick(cpm.terminal(), Qt::Key_C, Qt::ControlModifier);
        QTRY_VERIFY(peer->bytesAvailable() > 0);
        QCOMPARE(peer->readAll(), QByteArray("\x03"));
        QCOMPARE(stop.size(), 0);
        cpm.disconnectHost();
        QTRY_COMPARE(peer->state(), QAbstractSocket::UnconnectedState);
        cpm.setActive(false);
        cpm.setActive(true);
        QVERIFY(!cpm.connected() && !cpm.connecting());

        QUdpSocket udp;
        QVERIFY(udp.bind(QHostAddress::LocalHost, 0));
        QList<QByteArray> commands;
        bool respond = true;
        connect(&udp, &QUdpSocket::readyRead, this, [&] {
            while (udp.hasPendingDatagrams()) {
                auto d = udp.receiveDatagram();
                commands << d.data();
                if (!respond && commands.size() < 2)
                    continue;
                udp.writeDatagram("help\nip-config\n", d.senderAddress(), d.senderPort());
                udp.writeDatagram("\r\n", d.senderAddress(), d.senderPort());
            }
        });
        NetworkTerminal cli(NetworkTerminal::Cli, udp.localPort());
        cli.setHost("127.0.0.1");
        cli.setActive(true);
        QTRY_VERIFY(cli.connected());
        auto *terminal = cli.terminal();
        QTest::keyClicks(terminal, "helx");
        QTest::keyClick(terminal, Qt::Key_Backspace);
        QTest::keyClicks(terminal, "p");
        QTest::keyClick(terminal, Qt::Key_Left);
        QTest::keyClick(terminal, Qt::Key_Return);
        QTRY_COMPARE(commands, QList<QByteArray>{"help\n"});
        QTRY_VERIFY(terminal->text().contains("ip-config"));
        QTest::keyClicks(terminal, "discard");
        QTest::keyClick(terminal, Qt::Key_C, Qt::ControlModifier);
        QTest::keyClicks(terminal, "help");
        QTest::keyClick(terminal, Qt::Key_Return);
        QTRY_COMPARE(commands.size(), 2);
        QCOMPARE(commands.last(), QByteArray("help\n"));
        cli.disconnectHost();

        commands.clear();
        respond = false;
        NetworkTerminal monitor(NetworkTerminal::Monitor, udp.localPort());
        monitor.setHost("127.0.0.1");
        monitor.setActive(true);
        QTRY_COMPARE(commands.size(), 2);
        QCOMPARE(commands.first(), QByteArray("\n"));
        QTRY_VERIFY(monitor.terminal()->text().contains("ip-config"));
        QTest::keyClick(monitor.terminal(), Qt::Key_Return);
        QTRY_COMPARE(commands.size(), 3);
        QCOMPARE(commands.last(), QByteArray("\n"));
    }
    void terminalColors() {
        Terminal terminal;
        terminal.show();
        terminal.feed("\x1b[?25l\x1b[41m  \x1b[42m  \x1b[0m  "
                      "\x1b[48;5;196m  \x1b[48;2;12;34;56m  "
                      "\x1b[38;2;17;201;99;4mM");
        auto image = terminal.viewport()->grab().toImage();
        const QFontMetrics metrics(terminal.font());
        auto referenceFont = QFontDatabase::systemFont(QFontDatabase::FixedFont);
        referenceFont.setPointSize(11);
        const int cellWidth = QFontMetrics(referenceFont).horizontalAdvance('M');
        QCOMPARE(qRound(QFontMetricsF(terminal.font()).horizontalAdvance(QString(80, 'M'))),
                 80 * cellWidth);
        auto background = [&](const QImage &picture, int column, int row = 0) {
            return picture.pixelColor(4 + column * cellWidth + 2,
                                      4 + row * metrics.height() + 2);
        };
        QCOMPARE(background(image, 0), QColor("#cd0000"));
        QCOMPARE(background(image, 2), QColor("#00cd00"));
        QCOMPARE(background(image, 4), QColor("#111c22"));
        QCOMPARE(background(image, 6), QColor("#ff0000"));
        QCOMPARE(background(image, 8), QColor(12, 34, 56));
        bool foreground = false;
        for (int y = 0; y < image.height(); ++y)
            for (int x = 0; x < image.width(); ++x)
                foreground |= image.pixelColor(x, y) == QColor(17, 201, 99);
        QVERIFY(foreground);

        terminal.feed("\x1b[H\x1b[0;44m \x1b[0m");
        image = terminal.viewport()->grab().toImage();
        QCOMPARE(background(image, 0), QColor("#0000ee"));
        QCOMPARE(background(image, 1), QColor("#cd0000"));
        terminal.feed("\x1b[2;1H\x1b[31;1;7m \x1b[22m \x1b[27m ");
        image = terminal.viewport()->grab().toImage();
        QCOMPARE(background(image, 0, 1), QColor("#ff0000"));
        QCOMPARE(background(image, 1, 1), QColor("#cd0000"));
        QCOMPARE(background(image, 2, 1), QColor("#111c22"));
        terminal.feed("\x1b[3;1H\x1b[46mtext\x1b[3;2H\x1b[K");
        image = terminal.viewport()->grab().toImage();
        QCOMPARE(background(image, 79, 2), QColor("#00cdcd"));
        terminal.feed("\x1b[4;1H\x1b[44m\0337\x1b[41mX\0338 ");
        image = terminal.viewport()->grab().toImage();
        QCOMPARE(background(image, 0, 3), QColor("#0000ee"));
        terminal.feed("\x1b[5;1H\x1b[48;2;1;");
        terminal.feed("2;3m ");
        image = terminal.viewport()->grab().toImage();
        QCOMPARE(background(image, 0, 4), QColor(1, 2, 3));

        terminal.feed("\x1b[0m\x1b[3J\x1b[H\x1b[41mred\x1b[0m\r\n");
        for (int row = 0; row < 40; ++row)
            terminal.feed("plain\r\n");
        terminal.verticalScrollBar()->setValue(0);
        image = terminal.viewport()->grab().toImage();
        QCOMPARE(background(image, 0), QColor("#cd0000"));

        Terminal monitor(nullptr, QSize(80, 40));
        QCOMPARE(monitor.characterSize(), QSize(80, 40));
        monitor.feed("\x1b[40;80HX");
        QCOMPARE(monitor.text().split('\n').size(), 40);
        QCOMPARE(monitor.text().section('\n', 39, 39).at(79), QChar('X'));
    }
    void locks() {
        QTemporaryDir dir;
        const auto path = dir.filePath("4040.lock");
        {
            PortLock lock(path);
            QVERIFY_EXCEPTION_THROWN(PortLock second(path), std::runtime_error);
        }
        QVERIFY(QFileInfo::exists(path));
        PortLock again(path);
    }
    void links() {
        QTemporaryDir dir;
        auto root = dir.path();
        QDir().mkpath(root + "/br0/brif");
        auto check = [&](int speed, bool full) {
            QCOMPARE(
                hostLinkOptions("br0", root),
                (QStringList{"-global", QString("ez80f91-emac.link-speed=%1").arg(speed), "-global",
                             QString("ez80f91-emac.full-duplex=%1").arg(full ? "on" : "off")}));
        };
        check(100, true);
        QDir().mkpath(root + "/br0/brif/eth0");
        QDir().mkpath(root + "/eth0/device");
        writeFile(root + "/eth0/carrier", "1");
        writeFile(root + "/eth0/speed", "1000");
        writeFile(root + "/eth0/duplex", "full");
        check(100, true);
        writeFile(root + "/eth0/speed", "10");
        writeFile(root + "/eth0/duplex", "half");
        check(10, false);
        writeFile(root + "/eth0/carrier", "0");
        check(100, true);
        writeFile(root + "/br0/brif/eth0/state", "3");
        QVERIFY(bridgeForwarding("br0", {}, root));
        QVERIFY(!bridgeForwarding("br0", {"eth0"}, root));
    }
    void disks() {
        QTemporaryDir dir;
        auto cwd = QDir::currentPath();
        QDir::setCurrent(dir.path());
        auto path = diskDirectory(45454);
        QCOMPARE(digest(path + "/A.img"), digest(rootPath() + "/images/cpm/A.img"));
        writeFile(path + "/A.img", "saved guest data");
        QCOMPARE(diskDirectory(45454), path);
        QCOMPARE(readFile(path + "/A.img"), QByteArray("saved guest data"));
        QVERIFY_EXCEPTION_THROWN(diskDirectory(45454, dir.filePath("missing")), std::runtime_error);
        writeFile(dir.filePath("ez80f91_cs3.45455"), "invalid");
        QVERIFY_EXCEPTION_THROWN(diskDirectory(45455), std::runtime_error);
        QDir::setCurrent(cwd);
    }
    void projects() {
        QTemporaryDir dir;
        Options f24;
        f24.out = dir.filePath("f24");
        f24.zds = dir.filePath("ZDS space");
        QDir().mkpath(f24.out);
        writeFile(f24.out + "/camel.bin", "test ROM");
        writeFile(f24.out + "/camel.lod", "test symbols");
        QJsonObject sources;
        for (auto name : {"kit.inc", "kit_font.inc"}) {
            writeFile(f24.out + '/' + name, readFile(rootPath() + "/examples/camelf91/" + name));
            sources[name] = digest(f24.out + '/' + name);
        }
        writeFile(f24.out + "/camel.json",
                  QJsonDocument(
                      QJsonObject{{"sources", sources},
                                  {"binary_sha256", digest(f24.out + "/camel.bin")},
                                  {"upstream_commit", "af47e6520adc220cef5ee7e9ab96f0c336f7e299"}})
                      .toJson());
        prepareF24(f24);
        auto project = readFile(f24.out + "/camel24.zdsproj");
        QVERIFY(project.contains("QEMU_CAMEL24"));
        QVERIFY(project.contains("FLASHED=0,_EZ80ACCLAIM!=1,_DEBUG"));
        QVERIFY(project.contains("CAMLF91e.asm"));
        QVERIFY(project.contains("OMF695,INTEL32"));
        QVERIFY(readFile(f24.out + "/QEMU_CAMEL24.ztgt")
                    .contains("<externalAutoSelect>false</externalAutoSelect>"));
        QVERIFY(readFile(f24.out + "/start.cmd").contains("F24_READY PC=%x"));
        Options demo;
        demo.out = dir.filePath("demo");
        demo.zds = f24.zds;
        QDir().mkpath(demo.out);
        writeFile(demo.out + "/tcpudp.bin", "test demo ROM");
        writeFile(demo.out + "/build.json",
                  QJsonDocument(
                      QJsonObject{{"filesystem", "ram"},
                                  {"memory_profile", "qemu"},
                                  {"project", demo.zds + "/ZTP2.5.1/ZTP/SamplePrograms/TCPUDPDemo"},
                                  {"sha256", digest(demo.out + "/tcpudp.bin")}})
                      .toJson());
        prepareDemo(demo);
        QCOMPARE(readFile(demo.out + "/tcpudp.bin"), QByteArray("test demo ROM"));
    }
    void dhcp() {
        QTemporaryDir dir;
        QByteArray boot(240, '\0');
        boot[0] = 2;
        boot.replace(16, 4, QByteArray::fromHex("c0a84d10"));
        boot.replace(28, 6, QByteArray::fromHex("009023000101"));
        boot.replace(236, 4, QByteArray::fromHex("63825363"));
        boot += QByteArray::fromHex("3501053604c0a84d01ff");
        QByteArray ip(28, '\0');
        ip[0] = 0x45;
        ip[9] = 17;
        ip.replace(12, 4, QByteArray::fromHex("c0a84d01"));
        qToBigEndian<quint16>(67, ip.data() + 20);
        qToBigEndian<quint16>(68, ip.data() + 22);
        qToBigEndian<quint16>(boot.size() + 8, ip.data() + 24);
        QByteArray frame(14, '\0');
        frame.replace(12, 2, QByteArray::fromHex("0800"));
        frame += ip + boot;
        auto path = dir.filePath("network.pcap");
        for (bool little : {true, false}) {
            QByteArray pcap(24, '\0');
            pcap.replace(0, 4, QByteArray::fromHex(little ? "d4c3b2a1" : "a1b2c3d4"));
            QByteArray header(16, '\0');
            if (little)
                qToLittleEndian<quint32>(frame.size(), header.data() + 8);
            else
                qToBigEndian<quint32>(frame.size(), header.data() + 8);
            pcap += header + frame;
            writeFile(path, pcap.first(pcap.size() - 1));
            QVERIFY(dhcpLeases(path).isEmpty());
            writeFile(path, pcap);
            auto leases = dhcpLeases(path);
            QCOMPARE(leases.size(), 1);
            QCOMPARE(leases[0].toObject()["mac"].toString(), "00:90:23:00:01:01");
            QCOMPARE(leases[0].toObject()["server"].toString(), "192.168.77.1");
            QCOMPARE(leases[0].toObject()["address"].toString(), "192.168.77.16");
            writeFile(path, pcap + header + frame);
            QCOMPARE(dhcpLeases(path).size(), 1);
        }
        writeFile(path, "truncated");
        QVERIFY(dhcpLeases(path).isEmpty());
    }
    void echo() {
        QUdpSocket udp;
        QVERIFY(udp.bind(QHostAddress::LocalHost, 0));
        QTcpServer tcp;
        QVERIFY(tcp.listen(QHostAddress::LocalHost, 0));
        connect(&udp, &QUdpSocket::readyRead, this, [&] {
            while (udp.hasPendingDatagrams()) {
                auto d = udp.receiveDatagram();
                udp.writeDatagram(d.data(), d.senderAddress(), d.senderPort());
            }
        });
        connect(&tcp, &QTcpServer::newConnection, this, [&] {
            auto *socket = tcp.nextPendingConnection();
            connect(socket, &QTcpSocket::readyRead, this,
                    [socket] { socket->write(socket->readAll()); });
        });
        NetworkTest test("127.0.0.1", udp.localPort(), tcp.serverPort());
        QSignalSpy errors(&test, &NetworkTest::failed);
        QJsonArray leases{QJsonObject{
            {"mac", "00:90:23:00:01:01"}, {"server", "127.0.0.1"}, {"address", "127.0.0.1"}}};
        QList<QByteArray> commands;
        auto advance = [&](const QByteArray &output) {
            test.advance(output, leases, [&](QByteArray command) { commands << command; });
        };
        QByteArray output = "Login:";
        advance(output);
        output += "Password:";
        advance(output);
        output += "ZTP ";
        advance(output);
        QTest::qWait(510);
        advance(output);
        output += "Enter the server's port number to listen:";
        advance(output);
        output += "Server is bound to the port 4000";
        advance(output);
        QTRY_VERIFY(test.report()["udp_echo_ok"].toBool());
        output += "Sent 1000 bytes";
        advance(output);
        output += "Enter the server's port number to listen:";
        advance(output);
        output += "Server is Listening on port 4001";
        advance(output);
        QTRY_VERIFY(test.done());
        QVERIFY(test.report()["tcp_echo_ok"].toBool());
        QCOMPARE(commands, (QList<QByteArray>{"anonymous\r", "anonymous\r", "bsdudpserver\r",
                                              "4000\r", "bsdtcpserver\r", "4001\r"}));
        QCOMPARE(errors.size(), 0);
    }
    void qmp() {
        QTemporaryDir dir;
        QLocalServer server;
        QVERIFY(server.listen(dir.filePath("qmp")));
        Qmp client;
        QSignalSpy ready(&client, &Qmp::connected);
        QSignalSpy errors(&client, &Qmp::error);
        QJsonArray requests;
        QPointer<QLocalSocket> peer;
        connect(&server, &QLocalServer::newConnection, this, [&] {
            auto *socket = server.nextPendingConnection();
            peer = socket;
            auto buffer = std::make_shared<QByteArray>();
            socket->write("{\"QMP\":{}}\n");
            connect(socket, &QLocalSocket::readyRead, this, [&, socket, buffer] {
                *buffer += socket->readAll();
                while (buffer->contains('\n')) {
                    int end = buffer->indexOf('\n');
                    auto request = QJsonDocument::fromJson(buffer->left(end)).object();
                    buffer->remove(0, end + 1);
                    requests.append(request);
                    QJsonValue result = QJsonObject();
                    if (request["execute"] == "qom-list")
                        result = QJsonArray{
                            QJsonObject{{"name", "mem"}, {"type", "child<ez80f91-memory>"}}};
                    socket->write("{\"event\":\"STOP\"}\n");
                    socket->write(
                        QJsonDocument(QJsonObject{{"return", result}, {"id", request["id"]}})
                            .toJson(QJsonDocument::Compact) +
                        '\n');
                }
            });
        });
        client.open(server.fullServerName());
        QTRY_COMPARE(ready.size(), 1);
        QTRY_COMPARE(requests.size(), 2);
        QTest::qWait(10);
        client.buttons(5);
        client.buttons(0);
        client.call("system_reset");
        QTRY_COMPARE(requests.size(), 5);
        QCOMPARE(requests[2].toObject()["arguments"].toObject()["value"].toInt(), 5);
        QCOMPARE(requests[3].toObject()["arguments"].toObject()["value"].toInt(), 0);
        QCOMPARE(requests[4].toObject()["execute"].toString(), "system_reset");
        QCOMPARE(errors.size(), 0);
        auto path = dir.filePath("kit.json");
        writeFile(path, "{\"mask\":\"1\",\"enabled\":true,\"anode\":1,\"cathode\":254}");
        Kit kit(path, 4040, &client);
        kit.show();
        auto *tabs = kit.findChild<QTabWidget *>("consoleTabs");
        QVERIFY(tabs);
        QCOMPARE(tabs->count(), 6);
        QCOMPARE(tabs->tabText(1), QString("CP/M 2.2"));
        QCOMPARE(tabs->tabText(2), QString("Monitor"));
        QCOMPARE(tabs->tabText(3), QString("CLI"));
        QCOMPARE(tabs->tabText(5), QString("CAMEL24"));
        for (auto *terminal : kit.findChildren<Terminal *>())
            QCOMPARE(terminal->characterSize(), QSize(80, 40));
        auto *matrix = kit.findChild<QWidget *>("kitMatrix");
        auto *memory = kit.findChild<QLabel *>("memoryStatus");
        QVERIFY(matrix && memory);
        QVERIFY(matrix->width() < 120 && matrix->height() < 160);
        QVERIFY(matrix->geometry().right() < memory->geometry().left());
        auto *sidePanel = kit.findChild<QWidget *>("kitControls");
        QVERIFY(sidePanel);
        QVERIFY(sidePanel->mapTo(&kit, QPoint()).x() >
                tabs->mapTo(&kit, tabs->rect().topRight()).x());
        QVERIFY(sidePanel->isAncestorOf(matrix));
        QVERIFY(sidePanel->isAncestorOf(memory));
        QVERIFY(sidePanel->isAncestorOf(kit.findChild<QPushButton *>("SW4")));
        QVERIFY(sidePanel->isAncestorOf(kit.statusLabel()));
        QJsonObject telemetry{{"mask", "1"}, {"enabled", true}, {"anode", 1}, {"cathode", 254},
            {"host_ns", "1000000000"}, {"virtual_ns", "0"}, {"instructions", "0"},
            {"clock_hz", 50000000}, {"running", true}, {"icount", true},
            {"memory", QJsonArray{QJsonObject{{"name", "CS1"}, {"type", "ram"},
                {"start", 0}, {"end", 0x7ffff}, {"enabled", true}}}}};
        writeFile(path, QJsonDocument(telemetry).toJson());
        kit.refresh();
        telemetry["host_ns"] = "2000000000";
        telemetry["virtual_ns"] = "64000000";
        telemetry["instructions"] = "2000000";
        writeFile(path, QJsonDocument(telemetry).toJson());
        kit.refresh();
        auto *stats = kit.findChild<QLabel *>("clockStatistics");
        QVERIFY(stats->text().contains("Befehlsrate: 2.00 MIPS"));
        QVERIFY(stats->text().contains("Wirksamer Modelltakt: 3.20 MHz"));
        QVERIFY(stats->text().contains("Z80 ≈ 8.00 MHz"));
        QVERIFY(kit.findChild<QLabel *>("memoryConfiguration")->text().contains("000000-07ffff"));
        telemetry["host_ns"] = "3000000000";
        telemetry["running"] = false;
        writeFile(path, QJsonDocument(telemetry).toJson());
        kit.refresh();
        QVERIFY(stats->text().contains("Angehalten"));
        QTest::keyPress(&kit, Qt::Key_1);
        QTest::keyPress(&kit, Qt::Key_2);
        QFocusEvent lostFocus(QEvent::FocusOut);
        QApplication::sendEvent(&kit, &lostFocus);
        QTRY_COMPARE(requests.size(), 8);
        QCOMPARE(requests[5].toObject()["arguments"].toObject()["value"].toInt(), 1);
        QCOMPARE(requests[6].toObject()["arguments"].toObject()["value"].toInt(), 3);
        QCOMPARE(requests[7].toObject()["arguments"].toObject()["value"].toInt(), 0);
        peer->abort();
        QTRY_VERIFY(!client.ready);
        client.buttons(0);
        client.open(server.fullServerName());
        QTRY_COMPARE(ready.size(), 2);
        QTRY_COMPARE(requests.size(), 11);
        QCOMPARE(requests[10].toObject()["execute"].toString(), "qom-set");
        QCOMPARE(requests[10].toObject()["arguments"].toObject()["value"].toInt(), 0);
    }
};
QTEST_MAIN(PlatformTest)
#include "test_platform.moc"
