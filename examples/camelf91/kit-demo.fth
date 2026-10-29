( Load one line at a time. Start the kit window with ./start.sh --kit. )
( BTN-DEMO shows the pressed-button mask as 0..7; any UART key exits. )
: BTN-DEMO BEGIN BUTTONS 48 + MATRIX-CHAR KEY? UNTIL KEY DROP MATRIX-OFF ;
CHAR A MATRIX-CHAR
