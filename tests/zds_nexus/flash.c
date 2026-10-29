#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#define CPPUNIT_NXAPI
#include "nxapi.h"
static int failures;
static void check(const char *name, int ok) { printf("%s: %s\n", ok ? "PASS" : "FAIL",name); fflush(stdout); if(!ok) failures++; }
static void error_callback(const char *s) { printf("DLL: %s\n",s); fflush(stdout); }
int main(int argc,char **argv) {
    nxt_TargetSpec spec; nxt_Status status=99; nxt_Handle *h;
    HMODULE dll;
    if(argc < 3) { fprintf(stderr,"usage: flash.exe DLL ALGO_INI [PORT]\n");return 2; }
    dll=LoadLibraryA(argv[1]);
    nxt_Handle *(*open_fn)(const nxt_TargetSpec*,void(*)(const char*),nxt_Status*);
    nxt_Status (*close_fn)(nxt_Handle*);
    nxt_Status (*control_fn)(nxt_Handle*,nxt_CtrlData);
    if(!dll) { printf("load error %lu\n",GetLastError());return 1; }
    open_fn=(void*)GetProcAddress(dll,"nx_Open");
    close_fn=(void*)GetProcAddress(dll,"nx_Close");
    control_fn=(void*)GetProcAddress(dll,"nx_Control");
    memset(&spec,0,sizeof(spec)); spec.accessPort=NX_PORT_TYPE_OTHER;
    spec.targetEndian=NX_ENDIAN_LITTLE;
    spec.vendorTargetSpec.pOpenParameters=argv[2];
    spec.vendorTargetSpec.comminfo.type=NXV_COMM_TYPE_ETHERNET;
    strcpy(spec.vendorTargetSpec.comminfo.u.ethernet.addr,"127.0.0.1");
    spec.vendorTargetSpec.comminfo.u.ethernet.port=argc>3?atoi(argv[3]):4040;
    printf("open spec=%u ctrl=%u vendor=%u\n",(unsigned)sizeof(spec),(unsigned)sizeof(nxt_CtrlData),(unsigned)offsetof(nxt_CtrlData,vendorDefinedCtrlData));fflush(stdout);
    h=open_fn(&spec,error_callback,&status);
    printf("open handle=%p status=%d\n",h,status);fflush(stdout);
    check("open", h && status==0);
    if(h) {
        nxt_CtrlData c;unsigned long pc=0xabcdef;
        memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_INITIALIZE_TARGET;
        strcpy(c.vendorDefinedCtrlData.u.initializeTarget.cpuName,"eZ80F91");
        c.vendorDefinedCtrlData.u.initializeTarget.systemClockFreq=10000000;
        c.vendorDefinedCtrlData.u.initializeTarget.targetClockFreq=10000000;
        c.vendorDefinedCtrlData.u.initializeTarget.internalROMSize=0x40000;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.adl=1;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.flashLoaderRAM=0xffe000;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.flashLoaderRAMSize=0x2000;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.internalFlash.enable=1;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.chipSelects[0].lBound=0x10;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.chipSelects[0].uBound=0x1f;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.chipSelects[0].control=8;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.spl=0xfffff0;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.sps=0xffff;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.internalRAM.enable=1;
        c.vendorDefinedCtrlData.u.initializeTarget.u.eZ80.internalRAM.page=0xff;
        /* ZDS 5.3.5 adds a size DWORD absent from the SDK 1.1 headers.
         * Its driver explicitly checks size == 0x470 (PE32, pack 4). */
        { unsigned char cfg[0x470] = {0}; unsigned long size=sizeof(cfg); memcpy(cfg,&size,4); memcpy(cfg+4,&c.vendorDefinedCtrlData.u.initializeTarget,sizeof(cfg)-4); memcpy(&c.vendorDefinedCtrlData.u.initializeTarget,cfg,sizeof(cfg)); }
        check("initialize",control_fn(h,c)==0);
        memset(&c,0,sizeof(c));c.cTag=NX_CTRL_RESETORHALT;
        c.u.resetOrHalt.performResetSequence=1;
        c.u.resetOrHalt.haltState=1;
        check("halt",control_fn(h,c)==0);
        memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_GET_REGISTER;
        c.vendorDefinedCtrlData.u.getRegister.type=NXV_REGISTER_STANDARD;
        c.vendorDefinedCtrlData.u.getRegister.address=21;
        c.vendorDefinedCtrlData.u.getRegister.pValue=&pc;
        status=control_fn(h,c);printf("get pc status=%d pc=%06lx\n",status,pc);fflush(stdout);
        check("initial PC",status==0 && pc==0);
        {
            unsigned char pattern[10240], readback[10240];
            void *destination=readback;
            unsigned i;
            nxt_Status (*read_mem)(nxt_Handle*,int,int,unsigned long,size_t,int,void*)=(void*)GetProcAddress(dll,"nx_ReadMem");
            for(i=0;i<sizeof(pattern);i++) pattern[i]=(i*37+(i>>8))&255;
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_ERASE_INT_PROGRAM;
            c.vendorDefinedCtrlData.u.eraseIntProgram.startPage=0;
            c.vendorDefinedCtrlData.u.eraseIntProgram.numberOfPages=-1;
            check("mass erase internal",control_fn(h,c)==0);
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_SET_INT_PROGRAM;
            c.vendorDefinedCtrlData.u.setIntProgram.address=0;
            c.vendorDefinedCtrlData.u.setIntProgram.pData=pattern;
            c.vendorDefinedCtrlData.u.setIntProgram.numberOfBytes=sizeof(pattern);
            check("program internal multiple RAM blocks",control_fn(h,c)==0);
            memset(readback,0,sizeof(readback));
            destination=readback;
            check("read internal",read_mem(h,1,0,0,sizeof(readback),0,&destination)==0);
            check("verify internal",memcmp(pattern,readback,sizeof(pattern))==0);
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_ERASE_INT_PROGRAM;
            c.vendorDefinedCtrlData.u.eraseIntProgram.startPage=1;
            c.vendorDefinedCtrlData.u.eraseIntProgram.numberOfPages=2;
            check("page erase internal",control_fn(h,c)==0);
            status=0;
            for(i=0;i<sizeof(readback);i+=1024) {
                destination=readback+i;
                status|=read_mem(h,1,0,i,1024,0,&destination);
            }
            check("read erased pages",status==0);
            memset(pattern+2048,255,4096);
            check("verify page erase boundaries",memcmp(pattern,readback,sizeof(pattern))==0);
        }
        {
            unsigned char pattern[512], readback[512];
            unsigned char erase[]={0xaa,0x55,0x80,0xaa,0x55,0x30};
            unsigned long erase_addr[]={0x100555,0x1002aa,0x100555,0x100555,0x1002aa,0x100000};
            unsigned long sectors[]={0x100000};
            unsigned char unlock[]={0xaa,0x55,0xa0};
            unsigned long unlock_addr[]={0x100555,0x1002aa,0x100555};
            unsigned i;void *destination=readback;
            nxt_Status (*read_mem)(nxt_Handle*,int,int,unsigned long,size_t,int,void*)=(void*)GetProcAddress(dll,"nx_ReadMem");
            for(i=0;i<sizeof(pattern);i++)pattern[i]=(i*13+7)&255;
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_ERASE_EXT_PROGRAM;
            c.vendorDefinedCtrlData.u.eraseExtProgram.pBlockAddressList=sectors;
            c.vendorDefinedCtrlData.u.eraseExtProgram.numberOfBlocks=1;
            c.vendorDefinedCtrlData.u.eraseExtProgram.pDataEraseSeq=erase;
            c.vendorDefinedCtrlData.u.eraseExtProgram.pAddrEraseSeq=erase_addr;
            c.vendorDefinedCtrlData.u.eraseExtProgram.seqSize=6;
            c.vendorDefinedCtrlData.u.eraseExtProgram.verifyValue=0x80;
            c.vendorDefinedCtrlData.u.eraseExtProgram.verifyMask=0x80;
            check("erase external AMD",control_fn(h,c)==0);
            memset(&c,0,sizeof(c));c.cTag=NXV_CTRL_SET_EXT_PROGRAM;
            c.vendorDefinedCtrlData.u.setExtProgram.address=0x100000;
            c.vendorDefinedCtrlData.u.setExtProgram.pData=pattern;
            c.vendorDefinedCtrlData.u.setExtProgram.numberOfBytes=sizeof(pattern);
            c.vendorDefinedCtrlData.u.setExtProgram.pDataUnlockSeq=unlock;
            c.vendorDefinedCtrlData.u.setExtProgram.pAddrUnlockSeq=unlock_addr;
            c.vendorDefinedCtrlData.u.setExtProgram.seqSize=3;
            c.vendorDefinedCtrlData.u.setExtProgram.verifyMask=0x80;
            c.vendorDefinedCtrlData.u.setExtProgram.verifyValue=0x80;
            check("program external AMD",control_fn(h,c)==0);
            check("read external AMD",read_mem(h,1,0,0x100000,sizeof(readback),0,&destination)==0);
            check("verify external AMD",memcmp(pattern,readback,sizeof(pattern))==0);
        }
        close_fn(h);
    }
    return failures?1:0;
}
