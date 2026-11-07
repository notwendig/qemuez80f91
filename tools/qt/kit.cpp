#include "kit.h"
#include "common.h"

namespace ez80 {
namespace {
class Matrix : public QWidget {
  public:
    explicit Matrix(QWidget *parent) : QWidget(parent) {
        setObjectName("kitMatrix");
        setFixedSize(104, 144);
        setToolTip("5 × 7 LED-Matrix · Klicken: Kit-Tasten 1–3");
    }
  protected:
    void paintEvent(QPaintEvent *) override {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        p.setPen(QPen(QColor("#486057"), 2));
        p.setBrush(QColor("#111619"));
        p.drawRoundedRect(rect().adjusted(1, 1, -1, -1), 5, 5);
        const auto mask = property("mask").toULongLong();
        for (int row = 0; row < 7; ++row)
            for (int col = 0; col < 5; ++col) {
                QPoint center(16 + col * 18, 18 + row * 18);
                bool on = mask & (quint64(1) << (row * 5 + col));
                p.setPen(Qt::NoPen);
                p.setBrush(QColor(on ? "#5e2723" : "#181d20"));
                p.drawEllipse(center, 8, 8);
                p.setPen(QColor(on ? "#ffb08b" : "#64302e"));
                p.setBrush(QColor(on ? "#ff5143" : "#392325"));
                p.drawEllipse(center, 5, 5);
            }
    }
};
}
Kit::Kit(const QString &path, int port, Qmp *control, const QString &guestHost, QWidget *parent)
    : QWidget(parent), statePath(path), qmp(control) {
    setWindowTitle(QString("eZ80F91 Development Kit — %1").arg(port));
    setFocusPolicy(Qt::StrongFocus);
    setStyleSheet(
        "Kit {background:#102b25;color:#cfdfd5;}"
        "QLabel {color:#cfdfd5;}"
        "QLineEdit {background:#111c22;color:#d4e5de;padding:4px;border:1px solid #55775b;}"
        "QPushButton {background:#29483f;color:#f0cf69;border:1px solid #55775b;"
        "border-radius:4px;padding:5px 10px;}"
        "QPushButton:pressed {background:#55775b;color:white;}"
        "QPushButton:disabled {color:#82978b;}"
        "QTabWidget::pane {border:1px solid #486057;background:#111c22;}"
        "QTabBar::tab {background:#294039;color:#b3c7bd;padding:7px 18px;}"
        "QTabBar::tab:selected {background:#3b5a4e;color:#f0cf69;}");
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(16, 12, 16, 12);
    layout->setSpacing(10);
    auto *title = new QLabel("<b>ZiLOG eZ80F91</b>  ·  Development Kit", this);
    title->setStyleSheet("color:#f0cf69;font-size:18px;");
    layout->addWidget(title);
    consoles = new ConsoleTabs(guestHost.isEmpty() ? QString("ez80%1").arg(port) : guestHost,
                               this);
    consoles->setDiskDirectory(rootPath() + "/cpm-files");
    auto *content = new QHBoxLayout;
    content->setSpacing(20);
    content->addWidget(consoles, 0, Qt::AlignTop);
    auto *sidePanel = new QWidget(this);
    sidePanel->setObjectName("kitControls");
    sidePanel->setFixedWidth(370);
    auto *side = new QVBoxLayout(sidePanel);
    side->setContentsMargins(0, 0, 0, 0);
    side->setSpacing(16);
    auto *boardPanel = new QWidget(sidePanel);
    boardPanel->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    auto *board = new QHBoxLayout(boardPanel);
    board->setContentsMargins(0, 0, 0, 0);
    board->setSpacing(18);
    matrix = new Matrix(this);
    matrix->setFocusPolicy(Qt::ClickFocus);
    matrix->setFocusProxy(this);
    board->addWidget(matrix, 0, Qt::AlignTop);
    auto *telemetry = new QVBoxLayout;
    telemetry->setSpacing(5);
    auto label = [&](const char *name) {
        auto *value = new QLabel(this);
        value->setObjectName(name);
        telemetry->addWidget(value);
        return value;
    };
    memoryStatus = label("memoryStatus");
    anode = label("anodeStatus");
    cathode = label("cathodeStatus");
    modem = label("modemStatus");
    anode->setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
    cathode->setFont(anode->font());
    modem->setWordWrap(true);
    telemetry->addStretch();
    board->addLayout(telemetry, 1);
    auto *controlsPanel = new QWidget(sidePanel);
    controlsPanel->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    auto *controls = new QVBoxLayout(controlsPanel);
    controls->setContentsMargins(0, 0, 0, 0);
    auto *hint = new QLabel("Kit-Taster · Maus oder Tasten 1–3", this);
    controls->addWidget(hint);
    auto *switches = new QHBoxLayout;
    for (int bit = 0; bit < 3; ++bit) {
        auto *b = new QPushButton(QString("SW%1\nPB%2").arg(bit + 1).arg(bit), this);
        b->setObjectName(QString("SW%1").arg(bit + 1));
        b->setFocusPolicy(Qt::NoFocus);
        switches->addWidget(b);
        connect(b, &QPushButton::pressed, this, [this, bit] { button(bit, true); });
        connect(b, &QPushButton::released, this, [this, bit] { button(bit, false); });
    }
    controls->addLayout(switches);
    auto *reset = new QPushButton("SW4 · Reset", this);
    reset->setObjectName("SW4");
    reset->setFocusPolicy(Qt::NoFocus);
    controls->addWidget(reset);
    buttonsStatus = new QLabel(this);
    buttonsStatus->setObjectName("buttonsStatus");
    controls->addWidget(buttonsStatus);
    side->addWidget(boardPanel);
    side->addWidget(controlsPanel);
    configuration = new QLabel("Speicher: warte auf Telemetrie …", sidePanel);
    configuration->setObjectName("memoryConfiguration");
    auto detailFont = QFontDatabase::systemFont(QFontDatabase::FixedFont);
    detailFont.setPointSize(9);
    configuration->setFont(detailFont);
    side->addWidget(configuration);
    speed = new QLabel("Takt: warte auf Telemetrie …", sidePanel);
    speed->setObjectName("clockStatistics");
    speed->setWordWrap(true);
    speed->setToolTip("MHz-Äquivalente sind Referenzschätzungen: ein Takt pro Befehl für eZ80, "
                      "vier für Z80. Kein zyklusgenauer Taktvergleich. "
                      "Der wirksame Modelltakt ist Modelltakt × Gastzeit/Echtzeit.");
    side->addWidget(speed);
    sessionStatus = new QLabel(this);
    sessionStatus->setObjectName("sessionStatus");
    sessionStatus->setWordWrap(true);
    sessionStatus->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
    sessionStatus->setMaximumHeight(sessionStatus->fontMetrics().height() * 2);
    side->addWidget(sessionStatus);
    side->addStretch();
    content->addWidget(sidePanel);
    layout->addLayout(content);
    connect(reset, &QPushButton::clicked, this, [this] {
        release();
        qmp->call("system_reset");
    });
    connect(qmp, &Qmp::error, this, [this](const QString &error) {
        buttonsStatus->setText(error);
    });
    connect(qApp, &QGuiApplication::applicationStateChanged, this, [this](Qt::ApplicationState s) {
        if (s != Qt::ApplicationActive)
            release();
    });
    connect(&timer, &QTimer::timeout, this, &Kit::refresh);
    timer.start(20);
    refresh();
    layout->setSizeConstraint(QLayout::SetFixedSize);
}
void Kit::button(int bit, bool down) {
    int mask = down ? pressed | (1 << bit) : pressed & ~(1 << bit);
    if (mask == pressed)
        return;
    pressed = mask;
    qmp->buttons(pressed);
}
void Kit::release() {
    if (pressed) {
        pressed = 0;
        qmp->buttons(0);
        qmp->flush();
    }
}
void Kit::refresh() {
    try {
        auto next = readObject(statePath);
        bool ok;
        next["mask"].toString().toULongLong(&ok, 16);
        if (!ok || !next.contains("anode") || !next.contains("cathode") ||
            !next.contains("enabled"))
            fail("Unvollständige Kit-Telemetrie");
        state = next;
        available = true;
        status = state["enabled"].toBool() ? "CS2 freigegeben" : "CS2 nicht freigegeben";
        QStringList names;
        for (int bit = 0; bit < 3; ++bit)
            if (state["buttons"].toInt() & (1 << bit))
                names << QString("SW%1").arg(bit + 1);
        controlStatus = names.isEmpty() ? "SW1–3: offen" : "Gedrückt: " + names.join(", ");
    } catch (const std::exception &) {
        available = false;
        status = "Warte auf Emulator …";
    }
    memoryStatus->setText(status);
    const auto mask = available ? state["mask"].toString().toULongLong(nullptr, 16) : 0;
    if (matrix->property("mask").toULongLong() != mask) {
        matrix->setProperty("mask", QVariant::fromValue(mask));
        matrix->update();
    }
    int a = state["anode"].toInt(), c = state["cathode"].toInt();
    anode->setText(QString("800000h  ANODE    %1").arg(a, 2, 16, QChar('0')).toUpper());
    cathode->setText(QString("800001h  CATHODE  %1").arg(c, 2, 16, QChar('0')).toUpper());
    modem->setText(QString("MODEM RESET %1   TRIG1 %2   TRIG2 %3")
                       .arg((c >> 5) & 1).arg((c >> 6) & 1).arg((c >> 7) & 1));
    buttonsStatus->setText(controlStatus);
    statistics();
}
void Kit::statistics() {
    if (!available || !state.contains("host_ns")) {
        configuration->setText("Speicher/Takt: Telemetrie fehlt\nQEMU neu bauen/starten");
        speed->setText("Messwerte nicht verfügbar");
        sampleHost = 0;
        return;
    }
    QStringList lines{"Speicher · aktuelle Hardware"};
    for (const auto &entry : state["memory"].toArray()) {
        auto item = entry.toObject();
        lines << QString("%1 %2-%3 %4 %5")
                     .arg(item["name"].toString(), -10)
                     .arg(item["start"].toInt(), 6, 16, QChar('0'))
                     .arg(item["end"].toInt(), 6, 16, QChar('0'))
                     .arg(item["enabled"].toBool() ? "an " : "aus")
                     .arg(item["type"].toString());
        if (item.contains("control"))
            lines << QString("           CTL %1 · BMC %2")
                         .arg(item["control"].toInt(), 2, 16, QChar('0'))
                         .arg(item["bus_mode"].toInt(), 2, 16, QChar('0'));
    }
    configuration->setText(lines.join('\n'));
    configuration->setToolTip("Aktuelle QEMU-Register, einschließlich deaktivierter Fenster. "
                              "ZDS-Zieleinstellungen werden erst bei der Zielinitialisierung wirksam. "
                              "Die ROM/RAM-Bereiche des Linkers sind die Programmaufteilung. "
                              "CTL: Control Register; BMC: Bus Mode Control (hex).");
    qint64 host = state["host_ns"].toString().toLongLong();
    qint64 guest = state["virtual_ns"].toString().toLongLong();
    qint64 instructions = state["instructions"].toString().toLongLong();
    double mhz = state["clock_hz"].toDouble() / 1e6;
    if (!sampleHost || host < sampleHost || instructions < sampleInstructions) {
        sampleHost = host;
        sampleGuest = guest;
        sampleInstructions = instructions;
        speed->setText(QString("Modelltakt: %1 MHz\nMessung läuft …").arg(mhz, 0, 'f', 2));
    } else if (host - sampleHost >= 1000000000LL) {
        double elapsed = double(host - sampleHost);
        double mips = (instructions - sampleInstructions) * 1000.0 / elapsed;
        double ratio = (guest - sampleGuest) / elapsed;
        QString text = QString("Modelltakt: %1 MHz\n").arg(mhz, 0, 'f', 2);
        if (!state["running"].toBool())
            text += "Angehalten";
        else if (!state["icount"].toBool())
            text += "Befehlsmessung ohne icount nicht verfügbar";
        else
            text += QString("Befehlsrate: %1 MIPS\nWirksamer Modelltakt: %2 MHz\n"
                            "eZ80 ≈ %3 MHz / Z80 ≈ %4 MHz\n"
                            "Referenz: 1 / 4 T je Befehl\nNicht zyklusgenau; Gastzeit %5×")
                        .arg(mips, 0, 'f', 2).arg(mhz * ratio, 0, 'f', 2)
                        .arg(mips, 0, 'f', 2).arg(mips * 4, 0, 'f', 2)
                        .arg(ratio, 0, 'f', 3);
        speed->setText(text);
        sampleHost = host;
        sampleGuest = guest;
        sampleInstructions = instructions;
    }
}
void Kit::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.fillRect(rect(), QColor("#102b25"));
}
void Kit::keyPressEvent(QKeyEvent *e) {
    if (!e->isAutoRepeat() && e->key() >= Qt::Key_1 && e->key() <= Qt::Key_3)
        button(e->key() - Qt::Key_1, true);
    else
        QWidget::keyPressEvent(e);
}
void Kit::keyReleaseEvent(QKeyEvent *e) {
    if (!e->isAutoRepeat() && e->key() >= Qt::Key_1 && e->key() <= Qt::Key_3)
        button(e->key() - Qt::Key_1, false);
    else
        QWidget::keyReleaseEvent(e);
}
void Kit::focusOutEvent(QFocusEvent *e) {
    release();
    QWidget::focusOutEvent(e);
}
void Kit::closeEvent(QCloseEvent *e) {
    release();
    QWidget::closeEvent(e);
}
} // namespace ez80
