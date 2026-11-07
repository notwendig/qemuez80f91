#pragma once
#include "terminal.h"
#include <QtNetwork>

namespace ez80 {
class CamelTerminal : public QWidget {
    Q_OBJECT
    Terminal *display;
    QProcess process;
    QTemporaryDir workspace;
    QString statusText = "CAMEL24 · noch nicht gestartet";
    QString disks;
    QByteArray bootOutput, banner;
    QList<QByteArray> bootstrap;
    bool ready = false, bootStarted = false;
    void output(const QByteArray &bytes);
    void changed(const QString &message);

  public:
    explicit CamelTerminal(QWidget *parent = nullptr);
    ~CamelTerminal() override;
    Terminal *terminal() const { return display; }
    QString status() const { return statusText; }
    void start();
    void restart();
    void setDiskDirectory(const QString &path) { disks = QDir(path).absolutePath(); }

  signals:
    void stateChanged();
};

class CpmTerminal : public QWidget {
    Q_OBJECT
    Terminal *display;
    QProcess process;
    QTemporaryDir workspace;
    QString root, statusText = "CP/M · noch nicht gestartet";

  public:
    explicit CpmTerminal(QWidget *parent = nullptr);
    ~CpmTerminal() override;
    Terminal *terminal() const { return display; }
    QString status() const { return statusText; }
    void setRoot(const QString &path) { root = QDir(path).absolutePath(); }
    void start();
    void restart();

  signals:
    void stateChanged();
};

class NetworkTerminal : public QWidget {
    Q_OBJECT
  public:
    enum Protocol { Tcp, Monitor, Cli };
    NetworkTerminal(Protocol protocol, quint16 port, QWidget *parent = nullptr);
    ~NetworkTerminal() override;
    Terminal *terminal() const { return display; }
    QString status() const { return statusText; }
    bool connected() const;
    bool connecting() const;
    void setHost(const QString &host);
    void setActive(bool active);
    void connectHost();
    void disconnectHost();

  private:
    Protocol protocol;
    quint16 port;
    QString host, statusText = "Noch nicht verbunden";
    Terminal *display;
    QAbstractSocket *socket;
    QTimer retry, probe;
    QByteArray line;
    bool active = false, visited = false, wanted = false;
    void input(const QByteArray &bytes);
    void receive();
    void changed(const QString &message);

  signals:
    void stateChanged();
};

class ConsoleTabs : public QWidget {
    Q_OBJECT
    QTabWidget *tabs;
    QLineEdit *host;
    QPushButton *connection;
    QLabel *status;
    Terminal *uart;
    CamelTerminal *camel;
    CpmTerminal *cpm;
    QList<NetworkTerminal *> guests;
    NetworkTerminal *current() const;
    void refresh();
    void changeHost();

  public:
    explicit ConsoleTabs(const QString &guestHost, QWidget *parent = nullptr);
    Terminal *uartTerminal() const { return uart; }
    void hideUart();
    void setDiskDirectory(const QString &path) {
        camel->setDiskDirectory(path);
        cpm->setRoot(path);
    }
};
} // namespace ez80
