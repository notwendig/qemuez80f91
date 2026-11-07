#pragma once
#include "projects.h"
#include "qmp.h"
#include "terminal.h"
#include "kit.h"
#include "network.h"
#include <QLocalServer>
#include <QSocketNotifier>
#include <csignal>
#include <termios.h>

namespace ez80 {
class Session : public QObject {
    Q_OBJECT
    Options o;
    QProcess process, ide, views;
    QLocalServer uartServer;
    QPointer<QLocalSocket> uart;
    Qmp qmp;
    std::unique_ptr<PortLock> portLock, projectLock;
    std::unique_ptr<QWidget> window;
    std::unique_ptr<Kit> kit;
    Terminal *terminal = nullptr;
    QLabel *status = nullptr;
    std::unique_ptr<QSocketNotifier> stdinNotifier;
    std::unique_ptr<NetworkTest> networkTest;
    QFile uartLog;
    QByteArray output;
    QString runtime, qmpPath, uartPath, kitPath;
    QStringList previousPorts;
    QTimer poll;
    QElapsedTimer elapsed, running;
    bool qmpOpening = false, resumed = false, resumePending = false, stopping = false,
         ideStarted = false, ideReady = false;
    bool rawTerminal = false;
    struct termios *savedTerminal = nullptr;
    void tick();
    void message(const QString &text);
    void startIde();
    void data(const QByteArray &bytes);
    bool eventFilter(QObject *object, QEvent *event) override;

  public:
    explicit Session(Options options);
    ~Session() override;
    void start();
    void finish(int code = 0, const QString &error = {});
};
} // namespace ez80
