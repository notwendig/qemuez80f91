#include "common.h"
#include <QTcpServer>
#include <sys/file.h>
#include <unistd.h>

namespace ez80 {
volatile std::sig_atomic_t interrupted = 0;
void fail(const QString &message) { throw std::runtime_error(message.toStdString()); }
QString rootPath() {
    return QDir(qEnvironmentVariable("EZ80_PLATFORM_ROOT", EZ80_SOURCE_DIR)).absolutePath();
}
QString defaultQemu() {
    if (qEnvironmentVariableIsSet("QEMU_EZ80"))
        return qEnvironmentVariable("QEMU_EZ80");
    for (const auto &path : {"/install/bin/qemu-system-ez80", "/build/ez80/qemu-system-ez80"})
        if (QFileInfo(rootPath() + path).isExecutable())
            return rootPath() + path;
    return "/tmp/qemuez80f91-build-baseline/qemu-system-ez80";
}
QString defaultZds() {
    return qEnvironmentVariable("ZDS_HOME",
                                QDir::homePath() + "/.wine/drive_c/Zilog/ZDSII_eZ80Acclaim!_5.3.5");
}
QByteArray readFile(const QString &path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly))
        fail(path + ": " + f.errorString());
    return f.readAll();
}
void writeFile(const QString &path, const QByteArray &bytes) {
    QSaveFile f(path);
    if (!f.open(QIODevice::WriteOnly) || f.write(bytes) != bytes.size() || !f.commit())
        fail(path + ": " + f.errorString());
}
QJsonObject readObject(const QString &path) {
    QJsonParseError error;
    auto doc = QJsonDocument::fromJson(readFile(path), &error);
    if (error.error || !doc.isObject())
        fail("Ungültiges JSON: " + path);
    return doc.object();
}
QString digest(const QString &path) {
    return QCryptographicHash::hash(readFile(path), QCryptographicHash::Sha256).toHex();
}
QString windowsPath(const QString &path) {
    QString absolute = QFileInfo(path).absoluteFilePath();
    return "Z:" + absolute.replace('/', '\\');
}
void stopProcess(QProcess &p) {
    if (p.state() == QProcess::NotRunning)
        return;
    p.terminate();
    if (!p.waitForFinished(10000)) {
        p.kill();
        p.waitForFinished(3000);
    }
}
void runCommand(const QString &program, const QStringList &args, const QString &cwd,
                const QProcessEnvironment &env) {
    QProcess p;
    p.setWorkingDirectory(cwd);
    p.setProcessEnvironment(env);
    p.setProcessChannelMode(QProcess::ForwardedChannels);
    p.start(program, args);
    if (!p.waitForStarted())
        fail(program + ": " + p.errorString());
    while (!p.waitForFinished(100)) {
        if (interrupted) {
            stopProcess(p);
            fail("Aufruf abgebrochen: " + program);
        }
        if (p.state() == QProcess::NotRunning)
            break;
    }
    if (p.exitStatus() != QProcess::NormalExit || p.exitCode())
        fail(program + ": Aufruf fehlgeschlagen");
}
PortLock::PortLock(const QString &path) : file(path) {
    if (!QDir().mkpath(QFileInfo(path).absolutePath()))
        fail("Sperrverzeichnis fehlt: " + path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Append))
        fail(file.errorString());
    if (flock(file.handle(), LOCK_EX | LOCK_NB))
        fail("Instanz läuft bereits: " + path);
    // Keep the same inode: never unlink a lock file on release.
}
PortLock::~PortLock() { file.close(); }
void checkPort(int port) {
    QTcpServer probe;
    if (!probe.listen(QHostAddress::AnyIPv4, quint16(port)))
        fail(QString("Debugport %1 ist belegt: %2").arg(port).arg(probe.errorString()));
}
QString diskDirectory(int port, const QString &supplied) {
    if (!supplied.isEmpty()) {
        QDir dir(supplied);
        if (!dir.exists())
            fail("Disk-Verzeichnis fehlt: " + supplied);
        for (char c = 'A'; c <= 'P'; ++c)
            if (QFileInfo(dir.filePath(QString(c))).isFile() ||
                QFileInfo(dir.filePath(QString(c) + ".img")).isFile())
                return dir.absolutePath();
        fail("Keine Dateien A.img..P.img oder A..P in " + supplied);
    }
    QDir dir(QDir::current().filePath(QString("ez80f91_disks.%1").arg(port)));
    if (!QDir().mkpath(dir.path()))
        fail("Disk-Verzeichnis nicht angelegt: " + dir.path());
    auto source = rootPath() + "/images/cpm/";
    QJsonParseError error;
    auto doc = QJsonDocument::fromJson(readFile(source + "layout.json"), &error);
    if (error.error || !doc.isArray())
        fail("Ungültiges Disk-Layout");
    const auto layout = doc.array();
    auto legacy = QDir::current().filePath(QString("ez80f91_cs3.%1").arg(port));
    bool migrate = QFileInfo::exists(legacy);
    QByteArray raw;
    if (migrate) {
        raw = readFile(legacy);
        qint64 total = 0;
        for (auto disk : layout)
            total += disk.toObject()["size"].toInteger();
        if (raw.size() != total)
            fail("Unerwartete Größe des bisherigen CS3-Images: " + legacy);
    }
    for (auto entry : layout) {
        auto disk = entry.toObject();
        QString name = disk["drive"].toString() + ".img", target = dir.filePath(name);
        if (QFileInfo::exists(target))
            continue;
        writeFile(target, migrate ? raw.mid(disk["offset"].toInteger(), disk["size"].toInteger())
                                  : readFile(source + name));
    }
    return dir.absolutePath();
}
QStringList bridgeMembers(const QString &bridge, const QString &sysfs) {
    QDir dir(sysfs + '/' + bridge + "/brif");
    if (!dir.exists())
        fail("Netzwerkbridge fehlt: " + bridge);
    return dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
}
QStringList hostLinkOptions(const QString &bridge, const QString &sysfs) {
    int speed = 100;
    bool full = true;
    for (const auto &member : bridgeMembers(bridge, sysfs)) {
        QString path = sysfs + '/' + member + '/';
        if (!QFileInfo::exists(path + "device"))
            continue;
        try {
            if (readFile(path + "carrier").trimmed() != "1")
                continue;
            bool ok;
            int rate = readFile(path + "speed").trimmed().toInt(&ok);
            auto duplex = readFile(path + "duplex").trimmed();
            if (!ok || rate <= 0 || (duplex != "full" && duplex != "half"))
                continue;
            speed = qMin(speed, rate >= 100 ? 100 : 10);
            full = full && duplex == "full";
        } catch (const std::exception &) { /* unavailable sysfs value: fallback */
        }
    }
    qInfo().noquote() << QString("EMAC: %1 Mbps, %2-Duplex").arg(speed).arg(full ? "Full" : "Half");
    return {"-global", QString("ez80f91-emac.link-speed=%1").arg(speed), "-global",
            QString("ez80f91-emac.full-duplex=%1").arg(full ? "on" : "off")};
}
QSet<QString> qemuDeviceProperties(const QString &qemu, const QString &type) {
    // Query QOM without creating an F91 board, TAP interface or persistent flash.
    // -device TYPE,help is unsafe for older non-user-creatable F91 devices.
    QTemporaryDir directory;
    if (!directory.isValid())
        fail("Temporäres Verzeichnis für QEMU-Prüfung fehlt");
    QProcess probe;
    probe.setWorkingDirectory(directory.path());
    probe.start(qemu, {"-M", "none", "-display", "none", "-monitor", "none", "-serial", "none",
                       "-nic", "none", "-S", "-qmp", "stdio"});
    if (!probe.waitForStarted(3000))
        fail("QEMU-Eigenschaften nicht lesbar: " + probe.errorString());
    const QList<QJsonObject> commands = {
        {{"execute", "qmp_capabilities"}, {"id", 1}},
        {{"execute", "qom-list-properties"}, {"arguments", QJsonObject{{"typename", type}}}, {"id", 2}},
        {{"execute", "quit"}, {"id", 3}}};
    for (const auto &command : commands)
        probe.write(QJsonDocument(command).toJson(QJsonDocument::Compact) + '\n');
    if (!probe.waitForFinished(10000)) {
        stopProcess(probe);
        fail("QEMU-Eigenschaftsprüfung: Zeitlimit überschritten");
    }
    if (probe.exitStatus() != QProcess::NormalExit || probe.exitCode())
        fail("QEMU-Eigenschaftsprüfung fehlgeschlagen: " +
             QString::fromLocal8Bit(probe.readAllStandardError()));
    for (const auto &line : probe.readAllStandardOutput().split('\n')) {
        const auto response = QJsonDocument::fromJson(line).object();
        if (response.value("id").toInt() != 2)
            continue;
        if (!response.value("return").isArray())
            fail("QEMU unterstützt die Eigenschaftsabfrage nicht: " + type);
        QSet<QString> properties;
        for (const auto &property : response.value("return").toArray())
            properties.insert(property.toObject().value("name").toString());
        return properties;
    }
    fail("QEMU liefert keine Geräteeigenschaften: " + type);
}
QStringList qemuHostLinkOptions(const QString &qemu, const QString &bridge) {
    const auto properties = qemuDeviceProperties(qemu, "ez80f91-emac");
    if (!properties.contains("link-speed") || !properties.contains("full-duplex")) {
        qInfo().noquote() << "QEMU ohne Hostlink-Optionen; verwende EMAC-Standardwerte:" << qemu;
        return {};
    }
    return hostLinkOptions(bridge);
}
bool bridgeForwarding(const QString &bridge, const QStringList &previous, const QString &sysfs) {
    for (const auto &member : bridgeMembers(bridge, sysfs)) {
        if (previous.contains(member))
            continue;
        try {
            if (readFile(sysfs + '/' + bridge + "/brif/" + member + "/state").trimmed() == "3")
                return true;
        } catch (const std::exception &) {
        }
    }
    return false;
}
} // namespace ez80
