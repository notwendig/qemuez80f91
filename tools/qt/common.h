#pragma once
#include <QtCore>
#include <memory>
#include <stdexcept>
#include <csignal>

namespace ez80 {
extern volatile std::sig_atomic_t interrupted;
[[noreturn]] void fail(const QString &message);
QString rootPath();
QString defaultQemu();
QString defaultZds();
QByteArray readFile(const QString &path);
void writeFile(const QString &path, const QByteArray &bytes);
QJsonObject readObject(const QString &path);
QString digest(const QString &path);
QString windowsPath(const QString &path);
void runCommand(const QString &program, const QStringList &args, const QString &cwd = {},
                const QProcessEnvironment &env = QProcessEnvironment::systemEnvironment());
void stopProcess(QProcess &process);
void checkPort(int port);
QString diskDirectory(int port, const QString &supplied = {});
QStringList hostLinkOptions(const QString &bridge, const QString &sysfs = "/sys/class/net");
QSet<QString> qemuDeviceProperties(const QString &qemu, const QString &type);
QStringList qemuHostLinkOptions(const QString &qemu, const QString &bridge);
QStringList bridgeMembers(const QString &bridge, const QString &sysfs = "/sys/class/net");
bool bridgeForwarding(const QString &bridge, const QStringList &previous,
                      const QString &sysfs = "/sys/class/net");
class PortLock {
    QFile file;

  public:
    explicit PortLock(const QString &path);
    int handle() const { return file.handle(); }
    ~PortLock();
    PortLock(const PortLock &) = delete;
    PortLock &operator=(const PortLock &) = delete;
};
} // namespace ez80
