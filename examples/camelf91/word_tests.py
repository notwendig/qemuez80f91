"""24-bit CamelForth tests; export() writes a pasteable, self-checking Forth file."""
from pathlib import Path

SETUP = [
    'DECIMAL',
    'VARIABLE TESTS VARIABLE FAILS VARIABLE AD',
    'CREATE ACTUAL 32 CELLS ALLOT',
    '0 TESTS ! 0 FAILS !',
    ': T{ ;',
    ': BAD 1 FAILS +! ." FAIL " TESTS @ . BEGIN DEPTH WHILE DROP REPEAT ;',
    ': -> DEPTH DUP AD ! ?DUP IF 0 DO ACTUAL I CELLS + ! LOOP THEN ;',
    ': }T 1 TESTS +! DEPTH AD @ <> IF BAD EXIT THEN DEPTH ?DUP IF 0 DO ACTUAL I CELLS + @ <> IF BAD LEAVE THEN LOOP THEN ;',
    ': TEST-REPORT CR ." TESTS " TESTS @ . ." FAILURES " FAILS @ . CR ;',
    'CREATE WB 128 ALLOT CREATE WC 128 ALLOT VARIABLE WV',
]
# Each entry has a command, exact non-echo UART output, and optional raw input.
CASES = []
def command(text, result='', input=''):
    CASES.append(dict(command=text, result=result, input=input))
def check(actual, expected=''):
    command('T{ '+actual+' -> '+expected+' }T')

for a,b in [
 ('1 DUP','1 1'), ('0 ?DUP','0'), ('7 ?DUP','7 7'), ('1 DROP',''),
 ('1 2 SWAP','2 1'), ('1 2 OVER','1 2 1'), ('1 2 3 ROT','2 3 1'),
 ('1 2 NIP','2'), ('1 2 TUCK','2 1 2'), ('1 2 2DUP','1 2 1 2'),
 ('1 2 2DROP',''), ('1 2 3 4 2SWAP','3 4 1 2'),
 ('1 2 3 4 2OVER','1 2 3 4 1 2'), ('DEPTH','0'),
 ('SP@ SP!',''), ('RP@ RP!',''), ('DBG',''),
 ('1 2 +','3'), ('8388607 1 +','-8388608'), ('-1 1 +','0'),
 ('5 9 -','-4'), ('-8388608 1 -','8388607'), ('-5 NEGATE','5'),
 ('-8388608 NEGATE','-8388608'), ('-1 1+','0'), ('0 1-','-1'),
 ('-3 2*','-6'), ('-3 2/','-2'), ('8388607 2*','-2'),
 ('1 23 LSHIFT','-8388608'), ('-1 23 RSHIFT','1'), ('7 0 LSHIFT','7'),
 ('7 0 RSHIFT','7'), ('255 85 AND','85'), ('240 15 OR','255'),
 ('255 85 XOR','170'), ('0 INVERT','-1'), ('-1 INVERT','0'),
 ('0 0=','-1'), ('1 0=','0'), ('-1 0<','-1'), ('0 0<','0'),
 ('5 5 =','-1'), ('5 6 =','0'), ('5 6 <>','-1'), ('5 5 <>','0'),
 ('-1 1 <','-1'), ('1 -1 >','-1'), ('-1 1 U<','0'), ('-1 1 U>','-1'),
 ('-8388608 8388607 <','-1'), ('8388607 -8388608 >','-1'),
 ('5 2 MIN','2'), ('-5 2 MAX','2'), ('-1 1 UMIN','1'), ('-1 1 UMAX','-1'),
 ('5 1 9 WITHIN','-1'), ('9 1 9 WITHIN','0'), ('0 -2 2 WITHIN','-1'),
 ('-7 ABS','7'), ('7 ABS','7'), ('7 0 ?NEGATE','7'), ('7 -1 ?NEGATE','-7'),
 ('-1 S>D','-1 -1'), ('1 S>D','1 0'), ('1 0 DNEGATE','-1 -1'),
 ('-1 -1 DABS','1 0'), ('1 0 0 ?DNEGATE','1 0'), ('1 0 -1 ?DNEGATE','-1 -1'),
 ('-123 45 M*','-5535 -1'), ('123 45 *','5535'),
 ('-7 S>D 3 SM/REM','-1 -2'), ('-7 S>D 3 FM/MOD','2 -3'),
 ('-6 S>D 3 FM/MOD','0 -2'), ('7 -3 /MOD','-2 -3'),
 ('-7 3 /','-3'), ('-7 3 MOD','2'), ('7 5 3 */MOD','2 11'),
 ('7 5 3 */','11'), ('0 1 2 UD/MOD','0 -8388608 0'),
 ('-1 0 2 UD*','-2 1'), ('-1 0 1 M+','0 1'),
 ('-1 -1 UM*','1 -2'), ('0 1 2 UM/MOD','0 -8388608'),
 ('CELL','3'), ('0 CELL+','3'), ('5 CELLS','15'), ('7 CHAR+','8'),
 ('7 CHARS','7'), ('17 ALIGNED','17'), ('ALIGN',''), ('BL','32'),
 ('TIBSIZE','124'), ('BASE @','10'), ('STATE @','0'),
 ('U0 @ U0 =','-1'), ('DP @ HERE =','-1'), ('TIB SOURCE DROP =','-1'),
 ("'SOURCE CELL+ @ TIB =",'-1'), ('SOURCE NIP 0 >','-1'),
 ('>IN @ 0 >','-1'), ('S0 @ SP@ U>','-1'), ('R0 @ RP@ U>','-1'),
 ('HP @ HOLDP @ =','-1'), ('LP @ L0 @ =','-1'), ('PAD @ 0 <>','-1'),
 ('UINIT @ U0 =','-1'), ('#INIT','45'),
 ('123456 WV ! WV @','123456'), ('-1 WV ! WV @','-1'),
 ('42 WV ! 8 WV +! WV @','50'), ('255 WB C! WB C@','255'),
 ('11 22 WB 2! WB 2@','11 22'),
 ('WB 8 90 FILL WB C@ WB 7 + C@','90 90'),
 ('WB 0 0 FILL WB C@','90'),
 ('65 WB C! 66 WB 1 + C! WB WC 2 CMOVE WC C@ WC 1 + C@','65 66'),
 ('WB WB 1+ 2 CMOVE> WB C@ WB 1+ C@ WB 2 + C@','65 65 66'),
 ('WB 1+ WB 2 MOVE WB C@ WB 1+ C@','65 66'),
 ('WB WB 1+ 2 MOVE WB C@ WB 1+ C@ WB 2 + C@','65 65 66'),
 ('WB WC 0 CMOVE',''), ('WB WC 0 CMOVE>',''), ('WB WC 0 MOVE',''),
 ('WB WC 0 S=','0'), ('WB WB 3 S=','0'),
 ('65 WB C! 66 WC C! WB WC 1 S= 0<','-1'),
 ('WC WB 1 S= 0 >','-1'),
 ('WB 5 32 FILL 65 WB 2 + C! WB 5 32 SKIP SWAP WB -','3 2'),
 ('WB 5 65 SCAN SWAP WB -','3 2'),
 ('WB 0 65 SCAN SWAP WB -','0 0'), ('WB 0 32 SKIP SWAP WB -','0 0'),
 ('WB 3 2 /STRING SWAP WB -','1 2'),
 ('HERE 1 ALLOT HERE SWAP -','1'),
 ('HERE 123 , @','123'), ('HERE 65 C, C@','65'),
 ('49 DIGIT?','1 -1'), ('65 DIGIT? NIP','0'),
 ('0 >DIGIT 9 >DIGIT 10 >DIGIT 35 >DIGIT','48 57 65 90'),
 ('123 0 <# #S #> DUP >R WB SWAP CMOVE R> WB C@ WB 2 + C@','3 49 51'),
 ('0 0 <# 65 HOLD #> TYPE',''),
]:
    # This one intentionally emits text; its exact output is checked below.
    if a == '0 0 <# 65 HOLD #> TYPE':
        command('T{ '+a+' -> }T','A')
    else: check(a,b)

command('HEX')
check('123456 ><','125634')
check('BASE @','10')
command('DECIMAL')
check('BASE @','10')
command(': WRRET 10 >R R@ R> ;')
check('WRRET','10 10')
command(': WREXIT 7 EXIT 8 ;')
check('WREXIT','7')
command(': WRIF IF 11 ELSE 22 THEN ;')
check('0 WRIF -1 WRIF','22 11')
command(': WRUNTIL 0 BEGIN 1+ DUP 4 = UNTIL ;')
check('WRUNTIL','4')
command(': WRWHILE 0 BEGIN DUP 4 < WHILE 1+ REPEAT ;')
check('WRWHILE','4')
command(': WRAGAIN 0 BEGIN 1+ DUP 4 = IF EXIT THEN AGAIN ;')
check('WRAGAIN','4')
command(': WRDO 0 5 0 DO I + LOOP ;')
check('WRDO','10')
command(': WRSTEP 0 10 0 DO I + 2 +LOOP ;')
check('WRSTEP','20')
command(': WRNEG 0 0 5 DO I + -1 +LOOP ;')
check('WRNEG','15')
command(': WRLEAVE 0 10 0 DO I 3 = IF LEAVE THEN I + LOOP ;')
check('WRLEAVE','3')
command(': WRUNLOOP 10 0 DO I 3 = IF I UNLOOP EXIT THEN LOOP ;')
check('WRUNLOOP','3')
command(': WRJ 0 3 0 DO 2 0 DO I J + + LOOP LOOP ;')
check('WRJ','9')
command(': WRFAC DUP 1 > IF DUP 1- RECURSE * ELSE DROP 1 THEN ;')
check('6 WRFAC','720')
command(': WRLIT [ 7 8 + ] LITERAL ;')
check('WRLIT','15')
command(': WRTICK [\'] DUP EXECUTE ;')
check('5 WRTICK','5 5')
check("5 ' DUP EXECUTE",'5 5')
check('CHAR Z','90')
command(': WRCHAR [CHAR] Q ;')
check('WRCHAR','81')
command(': WRIMM POSTPONE DUP ; IMMEDIATE')
command(': WRPOST 6 WRIMM + ;')
check('WRPOST','12')
command(': WRTHEN POSTPONE IF POSTPONE THEN ; IMMEDIATE')
command(': WRPOST2 -1 WRTHEN 99 ;')
check('WRPOST2','99')
command('123 CONSTANT WRCONST 6 USER WRBASE VARIABLE WRVAR')
check('WRCONST WRBASE BASE =','123 -1')
check("' WRVAR >BODY WRVAR =",'-1')
command(': WRMAKER CREATE , DOES> @ ; 345 WRMAKER WRMADE')
check('WRMADE','345')
command("CREATE WRCOL !COLON ' lit COMPILE, 42 , ,EXIT REVEAL")
check('WRCOL','42')
command("CREATE WRCOPY 4 ALLOT ' DUP WRCOPY !CF")
# !CF must be validated as bytes, not by executing a CALL to a primitive.
check("WRCOPY C@ WRCOPY 1+ @ ' DUP =",'205 -1')
check("HERE ' DUP COMPILE, @ ' DUP =",'-1')
check("HERE ' branch ,BRANCH @ ' branch =",'-1')
check('HERE 765 ,DEST DUP @ SWAP 987 SWAP !DEST','765')
check('HERE 1- DUP 88 SWAP C! C@','88')
check('11 >L L>','11')
command(': WRSTR S" abc" ;')
check('WRSTR DUP >R WC >COUNTED R> WC C@ WC 1+ C@','3 3 97')
check('WC COUNT SWAP WC -','3 1')
check('WRSTR WB SWAP CMOVE WB WC 1+ 3 S=','0')
command(': WRENV S" UNKNOWN-ENV" ENVIRONMENT? ;')
check('WRENV','0')
command(': WREVAL S" 12 34 +" EVALUATE ;')
check('WREVAL','46')
command(": WRINTERP 'SOURCE 2@ >R >R >IN @ >R S\" 2 3 *\" INTERPRET R> >IN ! R> R> 'SOURCE 2! ;")
check('WRINTERP','6')
command(': WRNUM S" 123" WC >COUNTED WC ?NUMBER ;')
check('WRNUM','123 -1')
command(': WRSIGN S" -12" ?SIGN ROT DROP ;')
check('WRSIGN','2 2')
command(': WRNUMBER 0 0 S" 123x" >NUMBER NIP ;')
check('WRNUMBER','123 0 1')
command(': WRFIND BL WORD FIND ;')
check("WRFIND DUP SWAP ' DUP = SWAP",'-1 -1')
check('WRFIND IF NIP','1')
check('WRFIND NOSUCHWORD NIP','0')
check("LATEST @ DUP NFA>CFA ' WRFIND = SWAP IMMED?",'-1 0')
check('LATEST @ NFA>LFA @ 0 <>','-1')
command(': WRHIDDEN 543 ; HIDE')
check('WRFIND WRHIDDEN NIP','0')
command('REVEAL')
check('WRHIDDEN','543')
command(': WRNOABORT 0 ABORT" should-not-abort" 55 ;')
check('WRNOABORT','55')
check('1 ( ignored text ) 2 +','3')
command('65 EMIT SPACE 2 SPACES CR','A   \r\n')
command('PAGE','\x1b[2J')
command(': WRPRINT ." HELLO" ; WRPRINT','HELLO')
command('-42 6 .R','   -42')
command('-42 -1 7 D.R','    -42')
command('1 2 .S 2DROP','1 2 ')
# Safe peripheral tests use UART0's scratch register and restore it.
command('199 P0@ WV !')
check('85 199 P0! 199 P0@','85')
check('170 199 PC! 199 PC@','170')
check('90 199 P! 199 P@','90')
command('WV @ 199 P0!')
check('KEY?','0')
command('BUTTON-INIT')
check('BUTTONS','0')
check('1 BUTTON? 2 BUTTON? 3 BUTTON?','0 0 0')
check('0 BUTTON? 4 BUTTON? -1 BUTTON?','0 0 0')
check('SW1? SW2? SW3?','0 0 0')
command('MATRIX-INIT CHAR A MATRIX-CHAR')
command('WB 7 17 FILL WB MATRIX! MATRIX-CLEAR MATRIX-OFF')

INTERACTIVE = [
    dict(command='T{ KEY -> 90 }T', input='Z', result=''),
    dict(command='T{ KEY? KEY SWAP 0 <> -> 81 -1 }T', input='Q', result=''),
    dict(command='T{ WB 4 ACCEPT -> 4 }T', input='ABCD\r', result='ABCD'),
]


def export(path=None):
    path = path or Path(__file__).with_name('all-words.fth')
    lines = ['( CAMELF91 24-bit word tests. Load one line at a time. )',
             '( TEST-REPORT prints the assertion and failure counts. )',
             '( Port tests save and restore UART0 scratch register C7h. )']
    lines += SETUP + [c['command'] for c in CASES] + ['TEST-REPORT']
    assert max(map(len,lines)) <= 124
    path.write_text('\n'.join(lines)+'\n')
    return path

if __name__ == '__main__':
    print(export())
