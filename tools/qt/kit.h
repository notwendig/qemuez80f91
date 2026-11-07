#pragma once
#include "qmp.h"
#include "consoles.h"
#include <QtWidgets>

namespace ez80 {
class Kit : public QWidget {
    Q_OBJECT
    QString statePath;
    Qmp *qmp;
    QTimer timer;
    QJsonObject state;
    QString status = "Warte auf Emulator …", controlStatus = "SW1–3: offen";
    int pressed = 0;
    bool available = false;
    ConsoleTabs *consoles;
    QWidget *matrix;
    QLabel *memoryStatus, *anode, *cathode, *modem, *buttonsStatus, *sessionStatus;
    QLabel *configuration, *speed;
    qint64 sampleHost = 0, sampleGuest = 0, sampleInstructions = 0;
    void statistics();
    void button(int bit, bool down);

  protected:
    void paintEvent(QPaintEvent *) override;
    void keyPressEvent(QKeyEvent *) override;
    void keyReleaseEvent(QKeyEvent *) override;
    void focusOutEvent(QFocusEvent *) override;
    void closeEvent(QCloseEvent *) override;

  public:
    Kit(const QString &statePath, int port, Qmp *qmp, const QString &guestHost = {},
        QWidget *parent = nullptr);
    Terminal *uartTerminal() const { return consoles->uartTerminal(); }
    QLabel *statusLabel() const { return sessionStatus; }
    void hideUart() { consoles->hideUart(); }
    void setDiskDirectory(const QString &path) { consoles->setDiskDirectory(path); }
    void refresh();
    void release();
};
} // namespace ez80
